"""LFP ageing model (ageing.LfpAdjusted, not refitted here) against 20 A123 APR18650M1A cells
(LFP / graphite, 1.1 Ah) aged at 50 °C down to 31-64 % capacity (Wheeler et al. 2025,
data/wheeler2025/README.md): the shape of the fade below 80 %, which a second life runs
through, and the level at 50 °C, above the model's 20-40 °C data.

Shape: R = cycles from 70 to 60 % / cycles from 90 to 80 %. R near 1 is a steady fade, R
below 1 a fade that speeds up (a knee), R above 1 one that slows down. The first 10 % (a
quick drop in every cell) is left out. Level: cycles to 80 %, the model at the A123 cell's
own level (A123_LEVEL, fitted to Severson's and Preger's A123 cells at 25-30 °C).

Each group's test is rebuilt as a repeating cycle (constant-current discharge at the WLTP
profile's mean C/3 or at 2C, 30 min rest, charge to full, 30 min rest) at the pace the cells
cycled: 100 cycles, then a check-up of about 3 days, all at 50 °C (group 6: 3,614 cycles a
year measured from the raw files, 3,584 rebuilt).

Run:  python scripts/validate_lfp_wheeler.py          (a few seconds)
"""
import numpy as np
import pandas as pd

from battery_twin.ageing import add_rest, cycles_to, lfp_level, predict_capacity
from battery_twin.constants import DATA_DIR
from battery_twin.severson import A123_LEVEL

DATA = DATA_DIR / "wheeler2025" / "capacity.csv"
CHAMBER_C = 50.0
CHECKUP_DAYS = 3.1                         # median gap between ageing blocks (cell 6a)
# group: (charge C-rate, discharge C-rate, depth of discharge, duty)
GROUPS = {1: (1 / 3, 1 / 3, 0.7, "C/3 charge to 3.65 V, WLTP"),
          2: (1 / 3, 1 / 3, 0.7, "C/3 charge to 3.55 V, WLTP"),
          3: (1 / 3, 1 / 3, 0.7, "C/3 charge, no CV, WLTP"),
          4: (2.0, 1 / 3, 0.7, "2C charge to 3.65 V, WLTP"),
          5: (2.0, 1 / 3, 0.7, "2C charge to 3.55 V, WLTP"),
          6: (2.0, 2.0, 0.7, "2C charge, 2C discharge"),
          7: (1 / 3, 1 / 3, 1.0, "C/3 charge, no CV, WLTP, full depth")}


def cycles_at(cycles, rel, level):
    """Cycle at which the capacity first falls below `level` (linear between check-ups)."""
    below = np.flatnonzero(rel < level)
    if not len(below) or below[0] == 0:
        return np.nan
    j = below[0]
    return float(np.interp(level, [rel[j], rel[j - 1]], [cycles[j], cycles[j - 1]]))


def shape_ratio(cycles, rel):
    """R = cycles from 70 to 60 % / cycles from 90 to 80 %."""
    c90, c80, c70, c60 = (cycles_at(cycles, rel, x) for x in (0.9, 0.8, 0.7, 0.6))
    return (c60 - c70) / (c80 - c90)


def measured():
    """One row per cell: group, cycles to 80/70/60 % and R (3-check-up running median)."""
    rows = []
    for cell, g in pd.read_csv(DATA).groupby("cell"):
        rel = (g.q_ah / g.q_ah.iloc[0]).rolling(3, center=True, min_periods=1).median().to_numpy()
        n = g.cycle.to_numpy()
        rows.append({"cell": cell, "group": g.group.iloc[0], "last cycle": n[-1],
                     "capacity at the end [%]": 100 * rel[-1],
                     **{f"to {x:.0%}": cycles_at(n, rel, x) for x in (0.8, 0.7, 0.6)},
                     "R": shape_ratio(n, rel)})
    return pd.DataFrame(rows)


def model_curve(group, n_cycles):
    """The program's LFP model at the A123 level for one group's test: SOH after 1..n."""
    c_ch, c_dis, dod, _ = GROUPS[group]
    t_dis, t_ch = 3600 * dod / c_dis, 3600 * dod / c_ch
    t = np.array([0, t_dis, t_dis + 1800, t_dis + 1800 + t_ch, t_dis + 3600 + t_ch])
    soc = np.array([1, 1 - dod, 1 - dod, 1, 1])
    per_year = 365 * 100 / (100 * t[-1] / 86400 + CHECKUP_DAYS)
    t, soc, temp, _ = add_rest(t, soc, np.full(len(t), CHAMBER_C), per_year, CHAMBER_C)
    with lfp_level(A123_LEVEL):
        return predict_capacity("LFP", t, soc, temp, int(n_cycles))


def by_group(cells):
    """Measured medians per group next to the model's cycles to 80 % and R."""
    rows = []
    for group, g in cells.groupby("group"):
        q = model_curve(group, 12_000)
        n = np.arange(1, len(q) + 1)
        rows.append({"group": group, "duty": GROUPS[group][3], "cells": len(g),
                     "measured to 80 %": g["to 80%"].median(), "model to 80 %": cycles_to(q, 0.8),
                     "measured R (range)": f"{g.R.median():.2f} ({g.R.min():.2f}-{g.R.max():.2f})",
                     "model R": shape_ratio(n, q)})
    return pd.DataFrame(rows)


def default_storage_r(dod=0.8, temp_c=20.0):
    """R of the program's LFP model on a storage-like cycle: 1C discharge, 0.3C charge,
    depth `dod` around 50 % SOC, one cycle a day (the dashboard's defaults)."""
    t = np.array([0, 3600 * dod, 3600 * dod + 3600 * dod / 0.3])
    soc = np.array([0.5 + dod / 2, 0.5 - dod / 2, 0.5 + dod / 2])
    t, soc, temp, _ = add_rest(t, soc, np.full(3, temp_c), 365, temp_c)
    q = predict_capacity("LFP", t, soc, temp, 15_000)
    return shape_ratio(np.arange(1, len(q) + 1), q)


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    cells = measured()
    print(cells.round(2).to_string(index=False))
    print()
    print(by_group(cells).round(2).to_string(index=False))
    print(f"\nProgram's LFP model, storage cycle at the defaults (80 % depth, 20 °C): "
          f"R = {default_storage_r():.2f}")
