"""Capacity at every check-up of the 20 A123 LFP cells of Wheeler et al. (2025):
data/wheeler2025/capacity.csv (data/wheeler2025/README.md).

Data: W. Wheeler, P. Venet, Y. Bultel, A. Sari, "Aging study on twenty A123 18650 Graphite/LFP
1.1 Ah cells", Recherche Data Gouv (2025), doi 10.57745/OLBXKT; paper: Scientific Data 12, 392
(2025). The authors' extractedData.mat holds, per cell, the C/3 charge capacity at each 50 °C
check-up (every 100 ageing cycles) and the full equivalent cycles (FEC) of each ageing block.

Run:  python scripts/extract_wheeler2025.py "<path to extractedData.mat>"
"""
import sys

import numpy as np
import pandas as pd
from scipy.io import loadmat

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "wheeler2025" / "capacity.csv"


def number(x):
    """A MATLAB scalar, or NaN for an empty field (one check-up of cell 3a)."""
    a = np.ravel(np.asarray(x, dtype=float))
    return float(a[0]) if a.size else np.nan


if __name__ == "__main__":
    rows = []
    for cell in loadmat(sys.argv[1], squeeze_me=True, struct_as_record=False)["cell"]:
        fec = {int(number(b.lastCycle)): number(b.FEC) for b in np.atleast_1d(cell.aging)}
        fec[0] = 0.0
        for c in np.atleast_1d(cell.charac):
            n = int(number(c.cycle))
            rows.append({"cell": cell.name[4:], "group": int(cell.name[4]), "cycle": n,
                         "efc": round(fec.get(n, np.nan), 1),
                         "q_ah": round(number(c.chargecapacity), 5)})
    d = pd.DataFrame(rows).dropna(subset=["q_ah"])     # check-ups without a capacity
    OUT.parent.mkdir(exist_ok=True)
    d.to_csv(OUT, index=False)
    print(f"{d.cell.nunique()} cells, {len(d)} check-ups -> {OUT}")
