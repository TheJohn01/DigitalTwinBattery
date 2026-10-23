"""Discharge capacity of every cycle of the NCA and NCM 18650 cells of Zhu et al. (2022):
data/zhu2022/cycles.csv (data/zhu2022/README.md).

Data: Zhu J. et al., "Data-driven capacity estimation of commercial lithium-ion batteries
from voltage relaxation", Nature Communications 13, 2261 (2022); Zenodo 6405084 (CC BY 4.0),
Dataset_1_NCA_battery and Dataset_2_NCM_battery. File names CY<T>-<charge>_<discharge>-#<cell>
give the chamber temperature [°C] and the charge and discharge rates (025 = 0.25C, 05 = 0.5C).

One row per cycle: chemistry, temperature, charge and discharge rate, cell, cycle number,
discharge capacity [mAh] and the time at the end of the cycle [h].

Run:  python scripts/extract_zhu2022.py "<folder with the unpacked Dataset_* folders>"
"""
import glob
import re
import sys

import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "zhu2022" / "cycles.csv"


def rate(text):
    return float("0." + text[1:]) if text.startswith("0") else float(text)


def cell_cycles(path):
    parts = []
    for c in pd.read_csv(path, usecols=["time/s", "Q discharge/mA.h", "cycle number"],
                         chunksize=2_000_000):
        parts.append(c.groupby("cycle number").agg(q=("Q discharge/mA.h", "max"),
                                                   t=("time/s", "max")))
    d = pd.concat(parts).groupby(level=0).agg(q=("q", "max"), t=("t", "max"))
    return d[d.q > 100]                         # drop empty or interrupted cycles


if __name__ == "__main__":
    rows = []
    for path in sorted(glob.glob(f"{sys.argv[1]}/Dataset_*/*.csv")):
        chem = "NCA" if "NCA" in path else "NMC"
        temp, ch, dis, cell = re.search(r"CY(\d+)-(\d+)_(\d+)-#(\d+)\.csv", path).groups()
        d = cell_cycles(path)
        rows.append(pd.DataFrame({"chemistry": chem, "temp_c": int(temp), "c_charge": rate(ch),
                                  "c_discharge": rate(dis), "cell": int(cell),
                                  "cycle": d.index.astype(int), "q_mah": d.q.round(1),
                                  "time_h": (d.t / 3600).round(2)}))
    OUT.parent.mkdir(exist_ok=True)
    pd.concat(rows).to_csv(OUT, index=False)
    print(f"{len(rows)} cells -> {OUT}")
