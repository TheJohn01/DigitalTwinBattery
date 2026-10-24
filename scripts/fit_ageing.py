"""Fit the NCA cycling term, the NMC depth-of-discharge factor and the LFP knee to published data.

The data (data/published_ageing.csv) were read from the figures and text of:
- Preger et al., J. Electrochem. Soc. 167, 120532 (2020): Fig. 2a and Fig. 3
- Wittman et al., J. Electrochem. Soc. 170, 120538 (2023): text (checks only)
- Ohneseit et al., Batteries & Supercaps (2025), doi 10.1002/batt.202400713: Fig. 5 and 6
- Luh & Blank, Scientific Data 11, 1004 (2024): Fig. 12 (cycles to 80 % read from the
  figure's pixels, median of the three cells per condition)
- Huang et al., Electronics 15, 2563 (2026): Fig. 5b (Samsung 50E fade per 50 cycles, read
  from the figure, data/huang2026)
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

from battery_twin.ageing import LfpAdjusted, NcaRefit, NmcRefit, add_rest, predict_capacity
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


NcaRefit.LEVEL_50E = 1.0                      # Preger's Panasonic cell at its own level


def nca_residuals(x):
    NcaRefit.A, NcaRefit.B_DOD, NcaRefit.C_RATE, NcaRefit.P = np.exp(x[0]), x[1], x[2], x[3]
    NcaRefit.DIS_RATE = NcaRefit.C_RATE           # Preger's discharge effect, Panasonic only
    return residuals(nca)


fit = least_squares(nca_residuals, x0=[np.log(1e-3), 1.0, 0.5, 0.8])
nca_residuals(fit.x)
print("NCA cycling term:")
print(f"  A = {NcaRefit.A:.4g}, B_DOD = {NcaRefit.B_DOD:.3f}, "
      f"C_RATE = {NcaRefit.C_RATE:.3f}, P = {NcaRefit.P:.3f}")
print(f"  RMS error {np.sqrt(np.mean(fit.fun ** 2)):.2f} %-points of capacity "
      f"over {len(nca)} points")

# --- NCA step 2: level of the Samsung 50E (the physics model's cell), REBELION --------
# Two cells cycled 0-100 % (CC-CV charge 0.5C, CC discharge 1C, 10 s rests) for about 530
# EFC in 200 days; the cycle is stretched to that pace so the calendar loss is included.
# Room temperature is not recorded: 25 °C assumed. A discharge more than 3 % off the
# median of its 9 neighbours (an interrupted test) is left out. The CC-CV discharge cells
# (CVCV) are a check, not fitted.
rebelion = pd.read_csv(DATA_DIR / "rebelion2024" / "nca_50e_cycling.csv", parse_dates=["time"])


def rebelion_cell(g):
    """(model cal, model cyc at LEVEL 1, measured relative capacity, mask of kept points)."""
    q = g.discharge_ah.to_numpy()
    rel = q / np.median(q[:5])
    kept = np.abs(rel - pd.Series(rel).rolling(9, center=True, min_periods=1).median()) < 0.03
    days = (g.time.iloc[-1] - g.time.iloc[0]).total_seconds() / 86400
    t, soc = test_cycle(0.0, 1.0, 0.5, 1.0, 0)
    t, soc, temp, _ = add_rest(t, soc, np.full(len(t), 25.0), len(q) / days * 365, 25.0)
    cal, cyc = predict_capacity("NCA", t, soc, temp, len(q), parts=True)
    return cal, cyc, rel, kept.to_numpy()


def rebelion_rmse(level, strategy):
    errors = []
    for _, g in rebelion[rebelion.strategy == strategy].groupby("cell"):
        cal, cyc, rel, kept = rebelion_cell(g)
        errors.append(((1 - cal - level * cyc) - rel)[kept])
    return float(np.sqrt(np.mean(np.concatenate(errors) ** 2)))


level_fit = minimize_scalar(lambda x: rebelion_rmse(x, "CVC"), bounds=(0.05, 3), method="bounded")
print(f"NCA level of the Samsung 50E (REBELION):\n  LEVEL_50E = {level_fit.x:.3f}; RMS error "
      f"{100 * level_fit.fun:.2f} %-points over the CVC cells (Panasonic level: "
      f"{100 * rebelion_rmse(1.0, 'CVC'):.2f}); check, CC-CV discharge cells: "
      f"{100 * rebelion_rmse(level_fit.x, 'CVCV'):.2f}")
NcaRefit.LEVEL_50E = level_fit.x           # set last: predict_capacity applies it
NcaRefit.DIS_RATE = 0.0                    # the 50E: no discharge effect (step 3)

# --- NCA step 3: charge rate of the 50E (Huang et al. 2026, Fig. 5b) ------------------
# 0-100 % (CC-CV charge at 0.5 or 1C, 5 min rest, discharge at 1 or 2C, 25 min rest), 23 and
# 40 °C; the fade read from the figure, mean of three cells. 0 °C (15-28 % lost in 30-50
# cycles, plating at every rate) is left out: outside the model's 15-35 °C, with a warning.
huang = pd.read_csv(DATA_DIR / "huang2026" / "nca_50e_fade.csv")
huang = huang[huang.temp_c > 0]
huang_rows = [(r.temp_c, r.c_charge, r.c_discharge, g)
              for r, g in ((g.iloc[0], g) for _, g in
                           huang.groupby(["temp_c", "c_charge", "c_discharge"]))]


def huang_residuals(x):
    NcaRefit.K_CH, NcaRefit.T_CH = np.exp(x[0]), x[1]
    errors = []
    for temp, c_ch, c_dis, g in huang_rows:
        t, soc = test_cycle(0.0, 1.0, c_ch, c_dis, 15)
        q = predict_capacity("NCA", t, soc, np.full(len(t), float(temp)), int(g.cycle.max()))
        errors.append(100 * (1 - q[g.cycle.to_numpy() - 1]) - g.fade_pct.to_numpy())
    return np.concatenate(errors)


fit = least_squares(huang_residuals, x0=[0.0, 10.0], bounds=([-10, 1.0], [10, 200]))
huang_residuals(fit.x)
print(f"NCA charge rate of the 50E (Huang et al.):\n  K_CH = {NcaRefit.K_CH:.3f}, "
      f"T_CH = {NcaRefit.T_CH:.2f}; RMS error {np.sqrt(np.mean(fit.fun ** 2)):.2f} %-points "
      f"over {len(fit.fun)} points")

# --- NMC: cycling term with lithium plating, all NMC rows ------------------------------
# LG HG2 (Luh & Blank, Preger, Wittman) and Ohneseit's NMC811+Si 21700, fitted together.
nmc = data[data.chemistry == "NMC"]


# Heat: Zhu et al. (2022) cycled NCM 18650 cells (0.5C charge, 1C discharge, full cycles) at
# 35 and 45 °C (data/zhu2022): median 1,037 and 634 cycles to 80 %. Their ratio (the cells'
# own level cancels) sets K_HOT, the extra base wear per kelvin above T_HOT = 35 °C.
zhu = pd.read_csv(DATA_DIR / "zhu2022" / "cycles.csv")


def zhu_life(temp):
    """Median cycles to 80 % of Zhu's NCM cells at one chamber temperature."""
    lives = []
    for _, g in zhu[(zhu.chemistry == "NMC") & (zhu.temp_c == temp)].groupby("cell"):
        rel = g.q_mah.to_numpy() / np.median(g.q_mah.to_numpy()[1:6])
        smooth = pd.Series(rel).rolling(5, center=True, min_periods=1).median().to_numpy()
        below = np.flatnonzero(smooth < 0.8)
        if len(below):
            lives.append(g.cycle.to_numpy()[below[0]])
    return float(np.median(lives))


ZHU_RATIO = zhu_life(45) / zhu_life(35)
ZHU_ROWS = [pd.Series({"chemistry": "NMC", "soc_low": 0.0, "soc_high": 1.0, "c_charge": 0.5,
                       "c_discharge": 1.0, "rest_min": 15, "temp_c": t}) for t in (35, 45)]


def zhu_residual():
    m35, m45 = (efc_to_80(r) for r in ZHU_ROWS)
    return np.log((m45 / m35) / ZHU_RATIO)


def nmc_residuals(x):
    NmcRefit.K_BASE, NmcRefit.K_PL, NmcRefit.N_CH, NmcRefit.T_PL, NmcRefit.B_DOD = (
        np.exp(x[0]), np.exp(x[1]), x[2], x[3], x[4])
    NmcRefit.K_HOT = x[5]
    return np.append(log_residuals(nmc), 3 * zhu_residual())   # 31 cells, one ratio


# P is fixed at BLAST-Lite's LG M50 value (0.442): the data here are cycles to 80 % only,
# which do not pin down the curve shape. Luh & Blank's curves (fast loss in the first
# ~100 cycles, then slower) and Preger's NMC curves give a similar exponent (0.4-0.5).
NmcRefit.P = 0.442
fit = least_squares(nmc_residuals, x0=[np.log(5e-3), np.log(5e-3), 1.0, 10.0, 0.5, 0.05],
                    bounds=([-15, -15, 0.3, 2.0, 0.0, 0.0], [0, 0, 4.0, 50.0, 2.0, 1.0]))
nmc_residuals(fit.x)
print("NMC cycling term:")
print(f"  K_BASE = {NmcRefit.K_BASE:.4g}, K_PL = {NmcRefit.K_PL:.4g}, N_CH = {NmcRefit.N_CH:.3f}, "
      f"T_PL = {NmcRefit.T_PL:.3f}, P = {NmcRefit.P:.3f}, B_DOD = {NmcRefit.B_DOD:.3f}, "
      f"K_HOT = {NmcRefit.K_HOT:.3f}")
print(f"  typical error in cycles to 80 %: x{np.exp(np.sqrt(np.mean(fit.fun[:-1] ** 2))):.2f} "
      f"over {len(nmc)} points; Zhu 45/35 °C life ratio: measured {ZHU_RATIO:.2f}, model "
      f"{ZHU_RATIO * np.exp(fit.fun[-1] / 3):.2f}")

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

# --- LFP step 3: heat, Offenburg 200 Ah stationary cells cycled at 36.5 and 52 °C ---------
# Full cycles at C/4 (data/yagci2025), at the pace each cell cycled (days to each check-up).
# The cell's own level (cycling factor) comes from the two 35 °C cells with no heat term;
# K_HOT, the extra wear per kelvin above T_HOT = 40 °C while charging, from the 50 °C cells.
ofb = pd.read_csv(DATA_DIR / "yagci2025" / "checkups.csv", dtype={"cell": str})
ofb["rel"] = ofb.q_ah / ofb.groupby("cell").q_ah.transform("first")
ofb = ofb[(ofb.condition == "cycling") & (ofb.checkup > 0)]


def ofb_model(row, level, k_hot):
    t = np.array([0.0, 4 * 3600, 4.1 * 3600, 8.1 * 3600])
    soc = np.array([1.0, 0.0, 0.0, 1.0])
    t, soc, temp, _ = add_rest(t, soc, np.full(4, row.cycling_cell_c),
                               row.checkup / row.days * 365, row.cycling_cell_c)
    scale, hot = LfpAdjusted.SCALE, LfpAdjusted.K_HOT
    try:
        LfpAdjusted.SCALE, LfpAdjusted.K_HOT = scale * level, k_hot
        return predict_capacity("LFP", t, soc, temp, int(row.checkup))[-1]
    finally:
        LfpAdjusted.SCALE, LfpAdjusted.K_HOT = scale, hot


c35, c50 = ofb[ofb.chamber_c == 35], ofb[ofb.chamber_c == 50]
ofb_level = least_squares(lambda x: [ofb_model(r, x[0], 0.0) - r.rel for r in c35.itertuples()],
                          [0.5], bounds=([0.01], [10])).x[0]
fit = least_squares(lambda x: [ofb_model(r, ofb_level, x[0]) - r.rel for r in c50.itertuples()],
                    [0.1], bounds=([0.0], [5.0]))
LfpAdjusted.K_HOT = fit.x[0]
no_heat = [ofb_model(r, ofb_level, 0.0) - r.rel for r in c50.itertuples()]
print(f"LFP heat term: K_HOT = {LfpAdjusted.K_HOT:.3f} per K above {LfpAdjusted.T_HOT:g} °C "
      f"(Offenburg cell level "
      f"x{ofb_level:.3f}); 50 °C cells RMS {100 * np.sqrt(np.mean(fit.fun ** 2)):.1f} %-points "
      f"(without the term {100 * np.sqrt(np.mean(np.square(no_heat))):.1f})")

# --- Comparison table --------------------------------------------------------------------
level_50e = NcaRefit.LEVEL_50E
NcaRefit.LEVEL_50E = 1.0                     # Preger's rows are the Panasonic cell
NcaRefit.DIS_RATE = NcaRefit.C_RATE
print("\nCycles to 80 %: measured vs refitted model (NCA rows at the Panasonic level)")
for r in data[data.capacity_pct == 80].itertuples():
    print(f"  {r.chemistry:4} {r.source:20} {r.temp_c:>3.0f} °C  "
          f"{100 * r.soc_low:3.0f}-{100 * r.soc_high:3.0f} %  +{r.c_charge:g}C/-{r.c_discharge:g}C:  "
          f"measured {r.efc:5.0f}   model {efc_to_80(r):6.0f}"
          + ("   (A123 cell: own level, see step 2)" if r.cell.startswith("A123") else ""))


NcaRefit.LEVEL_50E = level_50e
NcaRefit.DIS_RATE = 0.0

# --- Save, rounded as printed above (the precision the fit supports) --------------------
FACTORS = ("A", "K_BASE", "K_PL", "SCALE")      # 4 significant figures; the rest 3 decimals


def rounded(cls, names):
    values = {k: float(getattr(cls, k)) for k in names}
    return {k: float(f"{v:.4g}") if k in FACTORS else round(v, 3) for k, v in values.items()}


fitted = {"NCA": rounded(NcaRefit, ("A", "B_DOD", "C_RATE", "P", "LEVEL_50E", "K_CH", "T_CH")),
          "NMC": rounded(NmcRefit, ("K_BASE", "K_PL", "N_CH", "T_PL", "P", "B_DOD", "K_HOT")),
          "LFP": rounded(LfpAdjusted, ("SCALE", "C_TH", "M_CH", "KNEE", "K_HOT")),
          "A123_LEVEL": float(f"{a123_level:.4g}")}
OUT.parent.mkdir(exist_ok=True)
with open(OUT, "w") as f:
    json.dump(fitted, f, indent=2)
print(f"\nWrote {OUT}")
