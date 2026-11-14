"""LFP second life (ageing.second_life_curve, not refitted) against two UConn-MathWorks cells
(LithiumWerks 18650, the A123 cell's successor, 1.2 Ah; data/uconn2025): fast-charged to
70-76 % (4.8C or 1C charge, 3-4C discharge, about 2-3 months), then cycled at 0.5C over the
full depth (2.0-3.6 V) to 47 %.

The model goes on from the retirement capacity on the second-life cycle at the A123 cell's
level (A123_LEVEL), the way the dashboard carries a car battery into storage: the loss is
matched on the second-life curve (all of it as cycling loss; the first life's 2-3 months of
calendar loss is small).
shortcut: the chamber temperature is not stated ("controlled"); 25 °C is assumed (30 °C
changes the model by under 0.5 points).

Second check, slow LFP below 80 % at a stated temperature: Cao et al. (2024)'s 100 Ah LFP cells
(data/cao2024), two new and two retired from forklifts at 88-89 %, cycled for 4,500-11,900
cycles at 23 °C (0.56C charge, 0.93C discharge, part depth) to 48-78 %. The model starts at
each cell's starting capacity on the same matched-loss curve, at the default LFP level (no
A123 scaling), with no rest between cycles. Only the start and end of each test are published.

Run:  python scripts/validate_lfp_second_life.py          (a few seconds)
"""
import numpy as np
import pandas as pd

from battery_twin.ageing import add_rest, lfp_level, second_life_curve
from battery_twin.constants import DATA_DIR
from battery_twin.severson import A123_LEVEL

DATA = DATA_DIR / "uconn2025" / "second_life.csv"
TEMP_C = 25.0
CYCLES_PER_YEAR = 365 * 45 / 6             # about 45 cycles per 6-day block


def model(rel_start, n_cycles):
    """Model capacity after 1..n_cycles at 0.5C full depth, starting at rel_start."""
    t = np.array([0.0, 7200, 7500, 14700, 15000])
    soc = np.array([1.0, 0.0, 0.0, 1.0, 1.0])
    t, soc, temp, _ = add_rest(t, soc, np.full(5, TEMP_C), CYCLES_PER_YEAR, TEMP_C)
    with lfp_level(A123_LEVEL):
        return second_life_curve("LFP", t, soc, temp, int(n_cycles), (0.0, 1 - rel_start),
                                 field=False)


def compare():
    """One row per cell: second-life cycles, measured and model capacity at the end."""
    rows = []
    for cell, g in pd.read_csv(DATA).groupby("cell"):
        rel = g.q_ah / g.q_ah.iloc[0]
        start = g[g.life == "first"].index[-1]              # last reference test of the first life
        n = int(g.cycles.iloc[-1] - g.cycles[start])
        q = model(rel[start], n)
        rows.append({"cell": cell, "first-life cycles": int(g.cycles[start]),
                     "retired at [%]": 100 * rel[start], "second-life cycles": n,
                     "measured at the end [%]": 100 * rel.iloc[-1], "model [%]": 100 * q[-1],
                     "measured loss / model loss": (rel[start] - rel.iloc[-1]) / (rel[start] - q[-1])})
    return pd.DataFrame(rows)


CAO = DATA_DIR / "cao2024" / "cells.csv"
CAO_DEPTH = 0.77            # cell 02 gives no full equivalent cycles: cell 01's depth


def cao_model(start, n_cycles, depth):
    """Model capacity after n_cycles at 0.56C charge / 0.93C discharge over `depth` below a
    95 % top, back to back at 23 °C, starting at capacity fraction `start`."""
    t_dis, t_cha = 3600 * depth / 0.93, 3600 * depth / 0.56
    t = np.array([0.0, t_dis, t_dis + 60, t_dis + 60 + t_cha, t_dis + 120 + t_cha])
    soc = np.array([0.95, 0.95 - depth, 0.95 - depth, 0.95, 0.95])
    t, soc, temp, _ = add_rest(t, soc, np.full(5, 23.0), 1e9, 23.0)      # no rest
    return second_life_curve("LFP", t, soc, temp, int(n_cycles), (0.0, 1 - start),
                             field=False)[-1]


def compare_cao():
    rows = []
    for c in pd.read_csv(CAO, dtype={"cell": str}).itertuples():
        depth = c.fec / c.cycles if c.fec == c.fec else CAO_DEPTH
        q = cao_model(c.start_pct / 100, c.cycles, depth)
        rows.append({"cell": c.cell, "origin": c.origin, "cycles": c.cycles,
                     "start [%]": c.start_pct, "measured at the end [%]": c.end_pct,
                     "model [%]": 100 * q,
                     "measured loss per 1,000 cycles [%-points]":
                         1000 * (c.start_pct - c.end_pct) / c.cycles,
                     "measured loss / model loss": (c.start_pct - c.end_pct)
                                                   / (c.start_pct - 100 * q)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    print(compare().round(1).to_string(index=False))
    print("\nCao et al. 2024, 100 Ah LFP (cell 03 partly at a higher, unstated temperature):")
    print(compare_cao().round(2).to_string(index=False))
