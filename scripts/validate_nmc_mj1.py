"""NMC ageing model (ageing.NmcRefit, not refitted here) against 42 LG INR18650 MJ1 cells
(NMC / graphite-SiOx, 3.4 Ah) of the TUM multi-stage ageing study: 10, 20 and 30 °C, depth of
discharge 10-100 % around 50 % SOC, charge 0.33-1C (data/tum_mj1_2024/README.md).

Each cell's test is rebuilt as a repeating cycle (CC discharge at 1C, CC charge, over its SOC
window), stretched to the pace the cell actually cycled at (EFC per day between check-ups),
so the calendar loss of the test is included. The model's prediction at each check-up is
compared with the measured capacity; nothing is fitted. The 10 s pulse resistance at each
check-up checks the resistance growth the aged physics windows assume.

Run:  python scripts/validate_nmc_mj1.py          (a few seconds)
"""
import numpy as np
import pandas as pd

from battery_twin.ageing import add_rest, predict_capacity
from battery_twin.constants import DATA_DIR

DATA = DATA_DIR / "tum_mj1_2024" / "mj1_rpt.csv"
RATED_CHARGE_C = 0.5           # the MJ1's standard charge (LG data sheet: 1.7 A)


def test_cycle(soc_low, soc_high, c_charge, c_discharge=1.0):
    dod = soc_high - soc_low
    t_dis, t_cha = 3600 * dod / c_discharge, 3600 * dod / c_charge
    t = np.concatenate([np.linspace(0, t_dis, 20), t_dis + 1 + np.linspace(0, t_cha, 20),
                        [t_dis + t_cha + 2]])
    soc = np.concatenate([np.linspace(soc_high, soc_low, 20), np.linspace(soc_low, soc_high, 20),
                          [soc_high]])
    return t, soc


def cell_result(g):
    """Measured and model relative capacity at each check-up of one cell."""
    lo, hi = g.soc_low_pct.iloc[0] / 100, g.soc_high_pct.iloc[0] / 100
    temp = float(g.temp_c.iloc[0])
    dod = hi - lo
    cycles = g.efc.to_numpy() / dod
    per_year = cycles[-1] / max(g.days.iloc[-1], 1.0) * 365
    t, soc = test_cycle(lo, hi, float(g.c_charge.iloc[0]))
    t, soc, temps, _ = add_rest(t, soc, np.full(len(t), temp), per_year, temp)
    q = predict_capacity("NMC", t, soc, temps, int(cycles[-1]) + 1)
    model = np.where(cycles >= 1, q[np.maximum(cycles.astype(int) - 1, 0)], 1.0)
    measured = (g.capacity_mah / g.capacity_mah.iloc[0]).to_numpy()
    return measured, model


def evaluate():
    """One row per cell: conditions, last check-up, measured and model capacity [%]."""
    rows = []
    for cell, g in pd.read_csv(DATA).groupby("cell", sort=False):
        measured, model = cell_result(g)
        rows.append({"cell": cell, "temp_c": g.temp_c.iloc[0],
                     "dod_pct": g.soc_high_pct.iloc[0] - g.soc_low_pct.iloc[0],
                     "c_charge": g.c_charge.iloc[0], "efc": g.efc.iloc[-1],
                     "measured_pct": 100 * measured[-1], "model_pct": 100 * model[-1],
                     "rms_pts": 100 * float(np.sqrt(np.mean((model - measured) ** 2)))})
    return pd.DataFrame(rows)


def resistance_growth():
    """Median 10 s pulse resistance relative to new, per band of remaining capacity, next to
    1 / capacity, the growth the aged physics windows get (chemistry.run_aged_window shrinks
    the electrode area, so the resistance rises as 1 / capacity)."""
    d = pd.read_csv(DATA).dropna(subset=["r10s_mohm"])
    first = d.groupby("cell").transform("first")
    q, r = d.capacity_mah / first.capacity_mah, d.r10s_mohm / first.r10s_mohm
    band = pd.cut(q, [0.5, 0.7, 0.8, 0.85, 0.9, 0.95, 1.01])
    return pd.DataFrame({"measured R / R new": r.groupby(band, observed=True).median(),
                         "1 / capacity": (1 / q).groupby(band, observed=True).median(),
                         "check-ups": r.groupby(band, observed=True).size()})


def summary(cells):
    within = cells[cells.c_charge <= RATED_CHARGE_C]
    beyond = cells[(cells.c_charge > RATED_CHARGE_C) & (cells.dod_pct >= 50)]
    return {"cells charged at the rated rate or slower": len(within),
            "RMS error over their check-ups [%-points]":
                float(np.sqrt(np.mean(within.rms_pts ** 2))),
            "10 % depth cells, mean error at the end [%-points]":
                float((within.model_pct - within.measured_pct)[within.dod_pct <= 10].mean()),
            "faster charge, depth 50 % or more: cells": len(beyond),
            "  measured capacity at the end, median [%]": float(beyond.measured_pct.median()),
            "  model capacity at the end, median [%]": float(beyond.model_pct.median())}


if __name__ == "__main__":
    cells = evaluate()
    pd.set_option("display.width", 160)
    print(cells.round(1).to_string(index=False))
    for k, v in summary(cells).items():
        print(f"{k}: {v:.1f}" if isinstance(v, float) else f"{k}: {v}")
    print("\nResistance growth by remaining capacity:")
    print(resistance_growth().round(2).to_string())
