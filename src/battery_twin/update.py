"""Update the twin's capacity prediction with measured capacities.

The twin's predicted capacity loss is multiplied by one factor k, estimated from the
measurements. k starts at 1 (the twin as it is) and moves only as far as the data justify:

    cost(k) = sum((measured - (1 - k * loss_model)) ** 2) / noise ** 2
              + (log k) ** 2 / prior_sd ** 2

This is the most likely k given Gaussian measurement errors and a log-normal prior on k
(a one-parameter Bayesian update; the particle filter of Thelen et al. 2023 does the same
for a power law, but starts from no model at all).

Why the twin is the prior: on Severson's LFP test cells, a curve fitted to the first
100-300 cycles alone (power law or straight line) does not reach end of life at all for most
cells, while the twin alone is within x1.33 (scripts/evaluate_update.py, README section 10).

What the update does and does not do (Severson LFP test cells, Kirkaldy NMC cells):
- it tracks the measured capacity better than the twin or the baselines (LFP: RMSE over the
  unseen cycles 3.5-5.3 %-points, against 6.9-8.8 for the twin; NMC: 0.61 against 1.43);
- for LFP it makes the predicted LIFE TOO LONG (x1.6-2.6 after 200-500 cycles), because
  these cells fade little until a late knee that the early data cannot show.

prior_sd = 0.24 is the typical error of the LFP fast-charge fit (x1.27 in cycle life).
The twin's fade is close to linear in cycles, so an error of x1.27 in life is about x1.27 in k.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

PRIOR_SD = float(np.log(1.27))
NOISE = 0.02   # chosen on Severson's training cells (scripts/evaluate_update.py)


def update_scale(cycles, soh_measured, soh_model, noise=NOISE, prior_sd=PRIOR_SD):
    """Factor k on the predicted loss that best fits the measurements.

    cycles: measured cycle numbers (1-based), soh_measured: relative capacity at those
    cycles (1 = new), soh_model: the twin's relative capacity after cycles 1, 2, 3, ...
    """
    cycles = np.asarray(cycles, dtype=int)
    measured = np.asarray(soh_measured, dtype=float)
    loss = 1.0 - np.asarray(soh_model, dtype=float)[cycles - 1]

    def cost(log_k):
        residual = measured - (1.0 - np.exp(log_k) * loss)
        return np.sum(residual ** 2) / noise ** 2 + log_k ** 2 / prior_sd ** 2

    best = minimize_scalar(cost, bounds=(-3.0, 3.0), method="bounded")
    return float(np.exp(best.x))


def updated_curve(soh_model, k):
    """The twin's curve with its loss multiplied by k."""
    return np.clip(1.0 - k * (1.0 - np.asarray(soh_model, dtype=float)), 0.0, 1.0)


def read_measurements(df, max_cycle):
    """(cycles, relative capacity) from a table whose first two columns are the cycle
    number and the capacity, either relative (0-1) or in % of the capacity when new.
    Rows that are not numbers, or outside cycles 1..max_cycle, are dropped."""
    if df.shape[1] < 2:
        return np.array([], dtype=int), np.array([])
    data = df.iloc[:, :2].apply(pd.to_numeric, errors="coerce").dropna()
    cycles = data.iloc[:, 0].round().astype(int).to_numpy()
    soh = data.iloc[:, 1].to_numpy(dtype=float)
    if len(soh) and np.nanmax(soh) > 1.5:          # given in %
        soh = soh / 100.0
    keep = (cycles >= 1) & (cycles <= max_cycle)
    order = np.argsort(cycles[keep])
    return cycles[keep][order], soh[keep][order]

