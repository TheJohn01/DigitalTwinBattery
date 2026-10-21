"""Fit the NCA cycling term, the NMC depth-of-discharge factor and the LFP knee to published data.

The data (data/published_ageing.csv) were read from the figures and text of:
- Preger et al., J. Electrochem. Soc. 167, 120532 (2020): Fig. 2a and Fig. 3
- Wittman et al., J. Electrochem. Soc. 170, 120538 (2023): text (checks only)
- Ohneseit et al., Batteries & Supercaps (2025), doi 10.1002/batt.202400713: Fig. 5 and 6
- Luh & Blank, Scientific Data 11, 1004 (2024): Fig. 12 (cycles to 80 % read from the
  figure's pixels, median of the three cells per condition)
- Severson et al., Nature Energy 4, 383 (2019): Supplementary Table 9, copied into
  data/severson2019_cycle_life.csv (cycle life and charging policy of all 124 cells)

Each row is one point: after `efc` equivalent full cycles in the stated test, the cell
had `capacity_pct` of its initial capacity. The tests cycled back to back, so each test is
rebuilt as a repeating cycle and run through predict_capacity, which also adds the
calendar ageing that happened during the test.

Run:  python scripts/fit_ageing.py      (about 10 s; writes results/ageing_fit.json)
To use the new values, copy results/ageing_fit.json over src/battery_twin/data/ageing_fit.json;
ageing.py and severson.py read them from there (as chemistry.py reads calibration.json).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import least_squares, minimize_scalar

from battery_twin.ageing import LfpAdjusted, NcaRefit, NmcRefit, predict_capacity
from battery_twin.constants import DATA_DIR
from battery_twin.severson import (EXCLUDED_BATCH, load_cells, load_curves, model_curve,
                                   severson_cycle)

DATA = DATA_DIR / "published_ageing.csv"
SEVERSON = DATA_DIR / "severson2019_cycle_life.csv"
OUT = Path("results") / "ageing_fit.json"


def test_cycle(soc_low, soc_high, c_charge, c_discharge, rest_min):
    """One cycle of a laboratory test: CC discharge, rest, CC charge (+30 min CV at 100 %), rest."""
    dod = soc_high - soc_low
    t_dis = 3600 * dod / c_discharge
    t_cha = 3600 * dod / c_charge
    t_cv = 1800 if soc_high >= 1 else 1          # 1 s instead of 0 keeps the times increasing
    rest = rest_min * 60 + 1
    t = np.concatenate([np.linspace(0, t_dis, 20),
                        t_dis + rest + np.linspace(0, t_cha, 20),
                        [t_dis + rest + t_cha + t_cv, t_dis + 2 * rest + t_cha + t_cv]])
    soc = np.concatenate([np.linspace(soc_high, soc_low, 20), np.linspace(soc_low, soc_high, 20),
                          [soc_high, soc_high]])
    return t, soc


def model_capacity(row):
    """Capacity [%] the model gives after row.efc equivalent full cycles of that test."""
    t, soc = test_cycle(row.soc_low, row.soc_high, row.c_charge, row.c_discharge, row.rest_min)
    dod = row.soc_high - row.soc_low
    n = int(round(row.efc / dod))
    q = predict_capacity(row.chemistry, t, soc, np.full(len(t), float(row.temp_c)), n)
    return 100 * q[-1]


def efc_to_80(row):
    """Equivalent full cycles until the model reaches 80 % in that test."""
    t, soc = test_cycle(row.soc_low, row.soc_high, row.c_charge, row.c_discharge, row.rest_min)
    dod = row.soc_high - row.soc_low
    q = predict_capacity(row.chemistry, t, soc, np.full(len(t), float(row.temp_c)), 40000)
    return cycles_to(q, 0.8) * dod


def cycles_to(q, level):
    """Cycles until capacity q (per cycle) falls to level, interpolated between cycles so
    that the result changes smoothly with the model parameters (the fit needs that). This is
    why the fit does not use battery_twin.ageing.cycles_to, which returns whole cycles."""
    q = np.concatenate([[1.0], q])
    below = np.flatnonzero(q < level)
    if not len(below):
        return np.inf
    i = below[0]
    return i - 1 + (q[i - 1] - level) / (q[i - 1] - q[i])


def log_residuals(rows):
    """log(model / measured) cycles to 80 %, for rows measured at 80 %."""
    return np.array([np.log(min(efc_to_80(r), 40000) / r.efc) for r in rows.itertuples()])


def residuals(rows):
    return np.array([model_capacity(r) - r.capacity_pct for r in rows.itertuples()])


data = pd.read_csv(DATA)

# --- NCA: all rows are Preger's Panasonic NCR18650B -----------------------------------
nca = data[data.chemistry == "NCA"]


def nca_residuals(x):
    NcaRefit.A, NcaRefit.B_DOD, NcaRefit.C_RATE, NcaRefit.P = np.exp(x[0]), x[1], x[2], x[3]
    return residuals(nca)


fit = least_squares(nca_residuals, x0=[np.log(1e-3), 1.0, 0.5, 0.8])
nca_residuals(fit.x)
print("NCA cycling term:")
print(f"  A = {NcaRefit.A:.4g}, B_DOD = {NcaRefit.B_DOD:.3f}, "
      f"C_RATE = {NcaRefit.C_RATE:.3f}, P = {NcaRefit.P:.3f}")
print(f"  RMS error {np.sqrt(np.mean(fit.fun ** 2)):.2f} %-points of capacity "
      f"over {len(nca)} points")

# --- NMC: cycling term with lithium plating, all NMC rows ------------------------------
# LG HG2 (Luh & Blank, Preger, Wittman) and Ohneseit's NMC811+Si 21700, fitted together.
nmc = data[data.chemistry == "NMC"]


def nmc_residuals(x):
    NmcRefit.K_BASE, NmcRefit.K_PL, NmcRefit.N_CH, NmcRefit.T_PL, NmcRefit.B_DOD = (
        np.exp(x[0]), np.exp(x[1]), x[2], x[3], x[4])
    return log_residuals(nmc)


# P is fixed at BLAST-Lite's LG M50 value (0.442): the data here are cycles to 80 % only,
# which do not pin down the curve shape. Luh & Blank's curves (fast loss in the first
# ~100 cycles, then slower) and Preger's NMC curves give a similar exponent (0.4-0.5).
NmcRefit.P = 0.442
fit = least_squares(nmc_residuals, x0=[np.log(5e-3), np.log(5e-3), 1.0, 10.0, 0.5],
                    bounds=([-15, -15, 0.3, 2.0, 0.0], [0, 0, 4.0, 50.0, 2.0]))
nmc_residuals(fit.x)
print("NMC cycling term:")
print(f"  K_BASE = {NmcRefit.K_BASE:.4g}, K_PL = {NmcRefit.K_PL:.4g}, N_CH = {NmcRefit.N_CH:.3f}, "
      f"T_PL = {NmcRefit.T_PL:.3f}, P = {NmcRefit.P:.3f}, B_DOD = {NmcRefit.B_DOD:.3f}")
print(f"  typical error in cycles to 80 %: x{np.exp(np.sqrt(np.mean(fit.fun ** 2))):.2f} "
      f"over {len(nmc)} points")

# --- LFP step 0: knee, the shape of the curve, from Severson's per-cycle capacities -----
# (fast-charged cells; see ageing.KNEE_LOSS for slow charging). KNEE bends the cycling loss around KNEE_LOSS (20 %), so cycle life barely moves and steps 1
# and 2 still fit the level; the shape uses the levels already in ageing_fit.json (run the
# script twice after a big change). Criterion: median over the cells of the RMS capacity
# error over each cell's measured life.
curves = load_curves()
shape_cells = [r for r in load_cells().itertuples()
               if r.batch_date != EXCLUDED_BATCH and r.barcode in curves]


def knee_error(knee):
    LfpAdjusted.KNEE = knee
    errors = []
    for r in shape_cells:
        cycle, soh = curves[r.barcode]
        lived = cycle <= r.cycle_life
        model = soh[0] * model_curve(r.charging_policy, cycle[lived][-1])
        errors.append(np.sqrt(np.mean((model[cycle[lived] - 1] - soh[lived]) ** 2)))
    return float(np.median(errors))


knee_fit = minimize_scalar(knee_error, bounds=(1.0, 6.0), method="bounded",
                           options={"xatol": 0.05})
LfpAdjusted.KNEE = knee_fit.x
print(f"LFP knee:\n  KNEE = {knee_fit.x:.3f}; median capacity error over the measured life "
      f"{100 * knee_fit.fun:.1f} %-points of nominal (no knee: {100 * knee_error(1.0):.1f})")
LfpAdjusted.KNEE = knee_fit.x

# --- LFP step 1: level from Ohneseit 1C, 20 °C, 0-100 % (same study as NMC data) -------
ohneseit_lfp = data[(data.chemistry == "LFP") & data.source.str.startswith("Ohneseit")
                    & (data.c_discharge == 1)]


def lfp_scale_residuals(x):
    LfpAdjusted.SCALE = np.exp(x[0])
    return residuals(ohneseit_lfp)


LfpAdjusted.C_TH, LfpAdjusted.M_CH = 100.0, 0.0      # no fast-charge effect at 0.5C
least_squares(lfp_scale_residuals, x0=[0.0])
lfp_scale = LfpAdjusted.SCALE
print(f"LFP cycling factor:\n  SCALE = {lfp_scale:.4g}")

# --- LFP step 2: fast charging, A123 APR18650M1A (Severson 2019 + Preger 2020) ---------
# The A123 cell lasts longer than Ohneseit's cell, so this group gets its own level
# (A123_LEVEL, used only here). Only C_TH and M_CH go into the program.
# Severson's 2017-06-30 batch is left out: the same policies gave much shorter lives
# than in the other two batches (e.g. 4.8C: ~470 vs ~750 cycles).
severson = pd.read_csv(SEVERSON)
severson = severson[severson.batch_date != EXCLUDED_BATCH]
preger_a123 = data[(data.chemistry == "LFP") & data.source.str.startswith("Preger")]


def a123_residuals(x):
    LfpAdjusted.SCALE = lfp_scale * np.exp(x[0])
    LfpAdjusted.C_TH, LfpAdjusted.M_CH = x[1], x[2]
    res = list(log_residuals(preger_a123))
    for r in severson.itertuples():
        t, soc = severson_cycle(r.charging_policy)
        q = predict_capacity("LFP", t, soc, np.full(len(t), 30.0), 6000)
        life = min(cycles_to(q, 0.8), 6000)
        res.append(np.log(life / r.cycle_life))
    return np.array(res)


fit = least_squares(a123_residuals, x0=[0.0, 3.0, 3.0], bounds=([-3, 0.5, 0.1], [3, 3.6, 20]))
a123_residuals(fit.x)
c_th, m_ch = LfpAdjusted.C_TH, LfpAdjusted.M_CH
a123_level = float(np.exp(fit.x[0]))
print(f"LFP fast-charge factor (A123 level x{a123_level:.4g}, used only in "
      "battery_twin/severson.py as A123_LEVEL):")
print(f"  C_TH = {c_th:.3f}, M_CH = {m_ch:.3f}; typical error in cycle life: "
      f"x{np.exp(np.sqrt(np.mean(fit.fun ** 2))):.2f} over {len(fit.fun)} cells")
LfpAdjusted.SCALE = lfp_scale

# --- Comparison table --------------------------------------------------------------------
print("\nCycles to 80 %: measured vs refitted model")
for r in data[data.capacity_pct == 80].itertuples():
    print(f"  {r.chemistry:4} {r.source:20} {r.temp_c:>3.0f} °C  "
          f"{100 * r.soc_low:3.0f}-{100 * r.soc_high:3.0f} %  +{r.c_charge:g}C/-{r.c_discharge:g}C:  "
          f"measured {r.efc:5.0f}   model {efc_to_80(r):6.0f}"
          + ("   (A123 cell: own level, see step 2)" if r.cell.startswith("A123") else ""))


# --- Save, rounded as printed above (the precision the fit supports) --------------------
FACTORS = ("A", "K_BASE", "K_PL", "SCALE")      # 4 significant figures; the rest 3 decimals


def rounded(cls, names):
    values = {k: float(getattr(cls, k)) for k in names}
    return {k: float(f"{v:.4g}") if k in FACTORS else round(v, 3) for k, v in values.items()}


fitted = {"NCA": rounded(NcaRefit, ("A", "B_DOD", "C_RATE", "P")),
          "NMC": rounded(NmcRefit, ("K_BASE", "K_PL", "N_CH", "T_PL", "P", "B_DOD")),
          "LFP": rounded(LfpAdjusted, ("SCALE", "C_TH", "M_CH", "KNEE")),
          "A123_LEVEL": float(f"{a123_level:.4g}")}
OUT.parent.mkdir(exist_ok=True)
with open(OUT, "w") as f:
    json.dump(fitted, f, indent=2)
print(f"\nWrote {OUT}")
