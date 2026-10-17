"""Compare the SHAPE of the LFP capacity curve with Severson et al. (2019), cell by cell.

The LFP fast-charge factor was fitted to Severson's cycle lives only (fit_ageing.py).
Here the whole measured curve of each cell is compared with the model run at the same
charging policy and 30 °C.

Capacities are compared in Ah: the model's relative capacity times the cell's first
measured capacity. Life is Severson's definition, 0.88 Ah (80 % of the nominal 1.1 Ah).

Shape: "fraction of the fade done" at a fraction x of the cell's life,
    f(x) = (Q_first - Q(x * life)) / (Q_first - 0.88).
A straight-line fade gives f(x) = x; a late knee gives f(x) far below x until near the end.
This compares the shape independently of whether the predicted life itself is right.

Data: Severson et al. 2019; per-cycle curves from acthelen/battery_digital_twin
(MIT, Thelen et al. 2023). Writes results/lfp_shape_severson.csv and
docs/lfp_shape_severson.png.

Run:  python scripts/validate_lfp_shape.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from battery_twin.ageing import cycles_to
from battery_twin.severson import EXCLUDED_BATCH, NOMINAL_AH, load_cells, load_curves, model_curve

ROOT = Path(__file__).parents[1]
(ROOT / "results").mkdir(exist_ok=True)
X = np.array([0.25, 0.5, 0.75])
LIFE_AH = 0.8 * NOMINAL_AH


def fade_done(cycle, capacity_ah, life):
    """f(x) at the fractions X of life (linear interpolation of the curve)."""
    q_first = capacity_ah[0]
    q_at = np.interp(X * life, cycle, capacity_ah)
    return (q_first - q_at) / (q_first - LIFE_AH)


curves = load_curves()
model_curves = {}                       # model capacity [Ah] of each cell, reused for the figure
rows = []
for cell in load_cells().itertuples():
    if cell.barcode not in curves:
        continue
    cycle, soh = curves[cell.barcode]
    capacity = soh * NOMINAL_AH
    life = cell.cycle_life
    n_model = int(max(4 * life, cycle[-1]))
    model_ah = capacity[0] * model_curve(cell.charging_policy, n_model)
    model_curves[cell.barcode] = model_ah
    model_life = cycles_to(model_ah, LIFE_AH)
    model_cycle = np.arange(1, n_model + 1)
    measured_window = cycle <= life
    error = model_ah[cycle[measured_window] - 1] - capacity[measured_window]
    f_meas = fade_done(cycle, capacity, life)
    f_model = fade_done(model_cycle, model_ah, model_life) if np.isfinite(model_life) \
        else np.full(len(X), np.nan)
    rows.append({"barcode": cell.barcode, "batch": cell.batch_date, "policy": cell.charging_policy,
                 "life_measured": life, "life_model": model_life,
                 "life_ratio": model_life / life,
                 "rmse_pct_nominal": 100 * np.sqrt(np.mean(error ** 2)) / NOMINAL_AH,
                 **{f"f_meas_{x:g}": v for x, v in zip(X, f_meas)},
                 **{f"f_model_{x:g}": v for x, v in zip(X, f_model)}})

df = pd.DataFrame(rows)
df.to_csv(ROOT / "results" / "lfp_shape_severson.csv", index=False)

for label, g in (("fit batches", df[df.batch != EXCLUDED_BATCH]),
                 (f"batch {EXCLUDED_BATCH} (not used in the fit)", df[df.batch == EXCLUDED_BATCH])):
    ratio = g.life_ratio.to_numpy()
    print(f"\n{label}: {len(g)} cells")
    print(f"  cycle life (0.88 Ah): typical error x{np.exp(np.sqrt(np.mean(np.log(ratio) ** 2))):.2f}, "
          f"median model/measured {np.median(ratio):.2f}")
    print(f"  capacity error over the measured life: median RMSE "
          f"{np.median(g.rmse_pct_nominal):.1f} %-points of nominal")
    for x in X:
        print(f"  fade done at {x:.0%} of life: measured median {np.median(g[f'f_meas_{x:g}']):.2f}, "
              f"model median {np.nanmedian(g[f'f_model_{x:g}']):.2f}")

# --- Figure: shape (left) and three example cells (right) --------------------------------
fit = df[df.batch != EXCLUDED_BATCH]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
xs = np.concatenate([[0], X, [1]])
for prefix, label, style in (("f_meas", "Measured (median of cells)", "o-"),
                             ("f_model", "Model (median)", "s--")):
    med = [0] + [np.nanmedian(fit[f"{prefix}_{x:g}"]) for x in X] + [1]
    ax1.plot(xs, med, style, label=label)
ax1.plot([0, 1], [0, 1], ":", color="grey", label="Straight-line fade")
ax1.set_xlabel("Fraction of the cell's life")
ax1.set_ylabel("Fraction of the fade to 0.88 Ah done")
ax1.set_title(f"Shape of the fade, {len(fit)} Severson cells")
ax1.legend()

examples = fit.sort_values("life_measured").iloc[[5, len(fit) // 2, -5]]
for k, cell in enumerate(examples.itertuples()):
    cycle, soh = curves[cell.barcode]
    model_ah = model_curves[cell.barcode]
    colour = f"C{k}"
    ax2.plot(cycle, soh * NOMINAL_AH, color=colour, label=f"{cell.policy}, measured")
    ax2.plot(np.arange(1, len(model_ah) + 1), model_ah, "--", color=colour, label="model")
ax2.axhline(LIFE_AH, color="grey", lw=0.8)
ax2.set_xlim(0, 1.3 * examples.life_measured.max())
ax2.set_ylim(0.8, 1.12)
ax2.set_xlabel("Cycle")
ax2.set_ylabel("Discharge capacity [Ah]")
ax2.set_title("Examples (dashed: model)")
ax2.legend(fontsize=7)
fig.text(0.01, 0.01, "Data: Severson et al. 2019, per-cycle files via "
         "acthelen/battery_digital_twin (Thelen et al. 2023)", fontsize=7)
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(ROOT / "docs" / "lfp_shape_severson.png", dpi=130)
print("\nWrote results/lfp_shape_severson.csv and docs/lfp_shape_severson.png")
