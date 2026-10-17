"""Does updating the twin with measured capacity improve its forecast?

Protocol (from otwin-core/otwin-hybrid, Apache-2.0, J. Marin 2026): forecasting, not
interpolation. Each method sees only the first N cycles of a cell and predicts the rest.
Every method is compared with two baselines that know nothing about batteries:
- persistence: the capacity stays at its last measured value;
- linear drift: a straight line through the measured capacities.
Scores: error in the predicted end of life (the question an operator asks) and RMSE of the
capacity over the cycles not seen, also as a skill = RMSE / RMSE of persistence (< 1 beats it).

Methods:
- twin: the program's prediction, no measurements used;
- twin + update: battery_twin.update (the twin's loss times a factor k fitted to the data);
- power law: 1 - c * n**z fitted to the data alone, in log space (otwin-hybrid; Wang et al.
  2011), using only points that have faded by more than 0.5 %.

1. Severson et al. 2019, A123 LFP: end of life = Severson's cycle life (0.88 Ah).
   The update's noise setting is chosen on the "Train" cells; results are for the test cells.
2. Kirkaldy et al. 2024, LG M50T NMC, 70-85 % cycling: the cells never reached 80 %, so only
   the RMSE over the second half of each test is scored.

Run:  python scripts/evaluate_update.py      (writes results/update_evaluation.csv)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from battery_twin.ageing import cycles_to, predict_capacity
from battery_twin.calibration import kirkaldy_cycle, load_cells as load_kirkaldy
from battery_twin.severson import load_cells, load_curves, model_curve
from battery_twin.update import update_scale, updated_curve

ROOT = Path(__file__).parents[1]
WINDOWS = (100, 200, 300, 500)
NOISES = (0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0)
HORIZON = 20000


def power_law_forecast(n, soh, n_out):
    ok = soh < 0.995
    if ok.sum() < 5:
        return np.full(len(n_out), soh[-1])          # nothing to fit yet: persistence
    z = np.polyfit(np.log(n[ok]), np.log(1 - soh[ok]), 1)[0]
    z = float(np.clip(z, 0.3, 1.5))                  # bounds as in otwin-hybrid
    log_c = float(np.mean(np.log(1 - soh[ok]) - z * np.log(n[ok])))   # refit for clipped z
    return 1 - np.exp(log_c) * n_out ** z


def linear_forecast(n, soh, n_out):
    slope, intercept = np.polyfit(n, soh, 1)
    return intercept + slope * n_out


def forecasts(n_seen, soh_seen, model, noise):
    """All methods' capacity on cycles 1..HORIZON."""
    n_all = np.arange(1, len(model) + 1)
    k = update_scale(n_seen, soh_seen, model, noise=noise)
    return {"twin": model,
            "twin + update": updated_curve(model, k),
            "power law": power_law_forecast(n_seen, soh_seen, n_all),
            "linear drift": linear_forecast(n_seen, soh_seen, n_all),
            "persistence": np.full(len(model), soh_seen[-1])}, k


def score(curves_out, n_test, soh_test, level, life):
    rows = {}
    for name, curve in curves_out.items():
        rmse = np.sqrt(np.mean((curve[n_test - 1] - soh_test) ** 2))
        eol = cycles_to(curve, level)
        rows[name] = (rmse, eol / life if life else np.nan)
    return rows


# --- 1. Severson LFP -----------------------------------------------------------------------
cells = load_cells().set_index("barcode")
curves = load_curves()
models = {b: model_curve(cells.loc[b, "charging_policy"], HORIZON) for b in curves}
records = []
for noise in NOISES:
    for barcode, (n, soh_nominal) in curves.items():
        cell = cells.loc[barcode]
        life = float(cell.cycle_life)
        soh = soh_nominal / soh_nominal[0]               # relative to the first measurement
        level = 0.8 / soh_nominal[0]                     # 0.88 Ah, relative to the first
        for window in WINDOWS:
            seen, unseen = n <= window, (n > window) & (n <= life)
            if window >= life or unseen.sum() < 3:
                continue
            out, k = forecasts(n[seen], soh[seen], models[barcode], noise)
            for name, (rmse, eol_ratio) in score(out, n[unseen], soh[unseen], level, life).items():
                records.append({"data": "Severson LFP", "set": cell.dataset, "noise": noise,
                                "cell": barcode, "seen": window, "method": name, "k": k,
                                "rmse": rmse, "eol_ratio": eol_ratio})
sev = pd.DataFrame(records)


def summary(df):
    g = df.copy()
    persistence = g[g.method == "persistence"].set_index(["cell", "seen"]).rmse
    g["skill"] = g.rmse.to_numpy() / persistence.reindex(
        pd.MultiIndex.from_frame(g[["cell", "seen"]])).to_numpy()
    g["log_eol"] = np.abs(np.log(g.eol_ratio.replace(0, np.nan)))
    out = g.groupby(["seen", "method"]).agg(
        cells=("cell", "nunique"),
        eol_error=("log_eol", lambda s: np.exp(np.median(s))),   # never reached = inf
        eol_found=("log_eol", lambda s: np.mean(np.isfinite(s))),
        rmse_pct=("rmse", lambda s: 100 * np.median(s)),
        skill=("skill", "median"))
    return out


train = sev[sev.set == "Train"]
print("Choice of the noise setting on the Severson TRAIN cells: lowest median RMSE over the "
      "unseen cycles (the update is for tracking the curve; its EOL error is shown too):")
best_noise, best_err = None, np.inf
for noise, g in train[train.method == "twin + update"].groupby("noise"):
    err = np.exp(np.median(np.abs(np.log(g.eol_ratio))))
    print(f"  noise {noise:<5}: x{err:.3f}, median RMSE {100 * np.median(g.rmse):.2f} %-points")
    if np.median(g.rmse) < best_err:
        best_noise, best_err = noise, np.median(g.rmse)
print(f"  -> noise = {best_noise}\n")

test = sev[(sev.set != "Train") & (sev.noise == best_noise)]
pd.set_option("display.width", 120)
print(f"Severson TEST cells ({test.cell.nunique()}): eol_error = median factor between predicted "
      "and measured cycle life (inf if most never reach 0.88 Ah); eol_found = share of cells for which the method reaches 0.88 Ah; "
      "rmse_pct = median RMSE over the unseen cycles [%-points]; skill < 1 beats persistence")
print(summary(test).round(3).to_string())

# --- 2. Kirkaldy NMC --------------------------------------------------------------------------
t, soc = kirkaldy_cycle()                  # the same test cycle as scripts/validate.py
period = t[-1]
records = []
for cell in load_kirkaldy():
    n = np.maximum((cell["days"] * 86400 / period).astype(int), 1)
    soh = cell["soh"] / 100.0
    model = predict_capacity("NMC", t, soc, np.full(len(t), cell["surface_T"]), int(n.max()))
    half = len(n) // 2
    out, k = forecasts(n[:half], soh[:half], model, best_noise)
    for name, curve in out.items():
        rmse = np.sqrt(np.mean((curve[n[half:] - 1] - soh[half:]) ** 2))
        records.append({"data": "Kirkaldy NMC", "set": f"{cell['chamber']} °C", "noise": best_noise,
                        "cell": cell["name"], "seen": int(n[half - 1]), "method": name, "k": k,
                        "rmse": rmse, "eol_ratio": np.nan})
kir = pd.DataFrame(records)
print(f"\nKirkaldy NMC ({kir.cell.nunique()} cells), first half of each test seen, "
      "median RMSE over the second half [%-points]:")
print((100 * kir.groupby("method").rmse.median()).round(2).to_string())
print("update factor k per cell: "
      + ", ".join(f"{c} {k:.2f}" for c, k in kir.groupby("cell").k.first().items()))

(ROOT / "results").mkdir(exist_ok=True)
pd.concat([sev, kir]).to_csv(ROOT / "results" / "update_evaluation.csv", index=False)
print("\nWrote results/update_evaluation.csv")
