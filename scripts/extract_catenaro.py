"""Small summary of the Catenaro & Onori (2021) NMC tests: data/catenaro2021/nmc_tests.csv.

Data: Catenaro E., Onori S., Data in Brief 35 (2021) 106894, doi 10.1016/j.dib.2021.106894;
files on Mendeley Data, doi 10.17632/kxsbr4x3j2 (CC BY 4.0). Six LG INR21700-M50 cells (the
cell of the NMC physics model) in a 5, 25 or 35 °C chamber. Each file: 1 h rest, CC charge at
0.3C to 4.2 V, CV hold, 1 h rest, CC discharge at the test rate to 2.5 V, 1 h rest; surface
temperature at mid-height, 1 s sampling.

One row per file: chamber, cell, rate; voltage at the start of the file (some tests start
part-charged, so their charge is incomplete); charge and discharge capacity and energy;
voltage at the end of the discharge (above 2.5 V: the tester stopped it early, at its
temperature limit); surface temperature at the start of the discharge, its largest value and
the value at the end.

Run:  python scripts/extract_catenaro.py "<folder that holds NMC/05degC, NMC/25degC, ...>"
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "catenaro2021" / "nmc_tests.csv"


def summary(path):
    d = pd.read_excel(path)
    cell, rate, chamber = re.search(r"NMC_k(\d)_([\d_]+)C_(\d+)degC", path.name).groups()
    t, v, i = d["Test_Time(s)"].to_numpy(), d["Voltage(V)"].to_numpy(), d["Current(A)"].to_numpy()
    temp = d["Surface_Temp(degC)"].to_numpy()
    median = d.groupby("Step_Index")["Current(A)"].transform("median").to_numpy()
    out = {"chamber_c": int(chamber), "cell": int(cell), "c_rate": float(rate.replace("_", ".")),
           "v_start": v[0]}
    for name, mask in (("charge", median > 0), ("discharge", median < 0)):
        k = np.flatnonzero(mask)
        dt = np.diff(t[k], prepend=t[k[0]])
        dt[np.r_[False, np.diff(k) > 1]] = 0            # no time across a gap between steps
        out[f"{name}_ah"] = float(np.sum(np.abs(i[k]) * dt) / 3600)
        out[f"{name}_wh"] = float(np.sum(np.abs(i[k] * v[k]) * dt) / 3600)
        if name == "discharge":
            out["t_start_c"], out["t_max_c"], out["t_end_c"] = temp[k[0]], temp[k].max(), temp[k[-1]]
            out["discharge_h"] = float((t[k[-1]] - t[k[0]]) / 3600)
            out["v_end_discharge"] = v[k[-1]]
    return out


if __name__ == "__main__":
    files = sorted(Path(sys.argv[1]).glob("NMC/*degC/NMC_k*_*C_*degC.xlsx"))
    rows = [summary(f) for f in files if "_0_05C_" not in f.name]   # C/20 tests: no heating
    OUT.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).sort_values(["chamber_c", "c_rate", "cell"]).round(4).to_csv(OUT, index=False)
    print(f"{len(rows)} tests -> {OUT}")
