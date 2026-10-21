"""Cycle-by-cycle capacities of eight Samsung INR21700-50E cells (the cell of the NCA physics
model) cycled with four charge/discharge strategies: data/rebelion2024/nca_50e_cycling.csv.

Data: UNED / REBELION project (Horizon Europe 101104241), "Aging of Samsung INR21700-50E
Li-ion cells", e-cienciaDatos, doi 10.21950/HZ7YOP, superseded by 10.21950/GT4LKX (CC BY 4.0).
The part used here is the G20 group: folders G20_<strategy>_<cell>/Cycles, one Neware .xlsx
per test file, whose "step" sheet lists every step with its start time and capacity.

Strategies (read from the step types): CC = CC charge at 2.45 A (0.5C) to 4.2 V, CC discharge
at 4.9 A (1C) to 2.5 V; CVC = CC-CV charge, CC discharge; CCV = CC charge, CC-CV discharge;
CVCV = CC-CV charge and discharge. 10 s rests between steps.

One row per discharge step: strategy, cell, start time, discharge capacity, the capacity of
the charge before it, and whether the discharge reached 2.5 V.

Run:  python scripts/extract_rebelion.py "<folder holding the G20_* folders>"
"""
import glob
import sys
import warnings

import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "rebelion2024" / "nca_50e_cycling.csv"


def steps(folder):
    rows = []
    for f in sorted(glob.glob(f"{folder}/Cycles/*.xlsx")):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")              # openpyxl: no default style
            rows.append(pd.read_excel(f, sheet_name="step"))
    return pd.concat(rows).sort_values("Oneset Date").reset_index(drop=True)


def summary(folder):
    s = steps(folder)
    _, strategy, cell = folder.rstrip("/").split("/")[-1].split("_")
    charge = s["Capacity(Ah)"].where(s["Step Type"].str.contains(" Chg")).ffill()
    dis = s[s["Step Type"].str.contains("DChg")]
    return pd.DataFrame({"strategy": strategy, "cell": cell, "time": dis["Oneset Date"],
                         "discharge_ah": dis["Capacity(Ah)"],
                         "charge_ah": charge[dis.index],
                         "to_2v5": dis["End Voltage(V)"] < 2.52})


if __name__ == "__main__":
    folders = sorted(glob.glob(f"{sys.argv[1]}/G20_*"))
    out = pd.concat([summary(f) for f in folders])
    OUT.parent.mkdir(exist_ok=True)
    out.round(4).to_csv(OUT, index=False)
    print(f"{len(out)} discharges from {len(folders)} cells -> {OUT}")
