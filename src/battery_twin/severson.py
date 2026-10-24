"""Severson et al. (2019) A123 LFP cells: test cycle, measured curves and model curves.

Data: Severson et al., Nature Energy 4, 383 (2019); credit belongs to the authors.
- data/severson2019_cycle_life.csv: Supplementary Table 9 (cycle life, charging policy).
- data/severson2019_capacity.csv: measured capacity every 10th cycle, taken from the copy
  in https://github.com/acthelen/battery_digital_twin (MIT, (c) 2022 Adam Thelen; Thelen
  et al., Struct. Multidisc. Optim. 66, 1, 2023). See scripts/import_severson_curves.py.

Severson defines cycle life as the cycle at which the capacity reaches 80 % of the
nominal 1.1 Ah (0.88 Ah). The cells were tested at 30 °C in a chamber.
"""
import re

import numpy as np
import pandas as pd

from .ageing import FIT, lfp_level, predict_capacity
from .constants import DATA_DIR

NOMINAL_AH = 1.1
CHAMBER_C = 30.0
EXCLUDED_BATCH = "2017-06-30"   # same policies gave much shorter lives (see fit_ageing.py)
# Life level of the A123 cells relative to the program's LFP level (Ohneseit 21700),
# fitted together with the fast-charge factor by scripts/fit_ageing.py (step 2).
A123_LEVEL = FIT["A123_LEVEL"]


def severson_cycle(policy):
    """One Severson test cycle: two-step fast charge 0-80 %, 1C to 100 %, 4C discharge."""
    c1, q1, c2 = re.match(r"([\d.]+)C\(([\d.]+)%\)-([\d.]+)C", policy).groups()
    c1, q1, c2 = float(c1), float(q1) / 100, float(c2)
    steps = [(-4.0, 1.0, 0.0), (c1, 0.0, q1), (c2, q1, 0.8), (1.0, 0.8, 1.0)]
    t, soc = [0.0], [1.0]
    for rate, s0, s1 in steps:
        if s1 != s0:
            t.append(t[-1] + 3600 * abs(s1 - s0) / abs(rate))
            soc.append(s1)
        t.append(t[-1] + 60)                        # short rest
        soc.append(soc[-1])
    return np.array(t), np.array(soc)


def load_cells():
    """One row per cell (barcode, dataset, batch_date, cycle_life, charging_policy)."""
    return pd.read_csv(DATA_DIR / "severson2019_cycle_life.csv")


def load_curves():
    """{barcode: (cycle, SOH)} with SOH = capacity / nominal 1.1 Ah, as in Severson."""
    df = pd.read_csv(DATA_DIR / "severson2019_capacity.csv")
    return {b: (g.cycle.to_numpy(), g.capacity_ah.to_numpy() / NOMINAL_AH)
            for b, g in df.groupby("barcode")}


def model_curve(policy, n_cycles, a123_level=True):
    """The program's LFP model for that charging policy: SOH after cycles 1..n_cycles.

    a123_level=True multiplies the cycling term by A123_LEVEL, as in the fit of the
    fast-charge factor: Severson's A123 cells outlast the Ohneseit cell that sets the
    program's LFP level. False gives the program's own (Ohneseit) level."""
    t, soc = severson_cycle(policy)
    with lfp_level(A123_LEVEL if a123_level else 1.0):
        return predict_capacity("LFP", t, soc, np.full(len(t), CHAMBER_C), int(n_cycles))
