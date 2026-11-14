"""Pulse resistance of 254 Samsung INR21700-50E cells from former mobility applications
(University of Wuppertal, "Feature Engineered Dataset from HPPC Files for Lithium-Ion Battery
Cells", Zenodo 13730404, CC BY 4.0; data/popp2024/README.md).

Each file of the archive holds one pulse pair at 25 °C: 10 s rest, 10 s charge at 0.75C
(3.675 A), 40 s rest, 10 s discharge at 1C (4.9 A), 40 s rest, sampled at 1 kHz. The archive
has no capacity test, so the resistance cannot be set against each cell's state of health
(the raw capacity tests are in Zenodo 10891871, not used here); it gives the spread of the
resistance among retired cells. Resistance = voltage step over the 10 s pulse / pulse
current, from the last second of the rest before the pulse to the last 0.1 s of the pulse.

Run:  python scripts/extract_hppc_resistance.py <path to HPPCs_FE_Cleaned.zip>
      (about 15 minutes; writes data/popp2024/hppc_pulse_resistance.csv)
"""
import sys
import zipfile

import numpy as np
import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "popp2024" / "hppc_pulse_resistance.csv"
RATE_HZ = 1000


def pulse(d, target):
    """(rest voltage before, resistance in mOhm) of the pulse with this target current."""
    on = np.flatnonzero(np.isclose(d.Itarget.to_numpy(), target, atol=0.05))
    start, end = on[0], on[-1]
    before = d.U.iloc[max(0, start - RATE_HZ):start - 5].mean()     # last second of rest
    during = d.iloc[end - RATE_HZ // 10:end]                          # last 0.1 s of the pulse
    return before, 1000 * (during.U.mean() - before) / during.I.mean()


def cell_rows(zip_path):
    z = zipfile.ZipFile(zip_path)
    for name in sorted(n for n in z.namelist() if n.endswith(".csv") and not n.startswith("__")):
        with z.open(name) as f:
            d = pd.read_csv(f, usecols=["Itarget", "I", "U"])
        batch, file = name.split("/")[-2:]
        ocv, r_dis = pulse(d, -4.9)
        _, r_cha = pulse(d, 3.675)
        yield {"batch": batch, "mcu": file.split("_MCU")[1].split("_")[0],
               "file": file.replace("Engineered_Cleaned_", ""),
               "rest_voltage_v": round(ocv, 4), "r_discharge_1c_10s_mohm": round(r_dis, 2),
               "r_charge_075c_10s_mohm": round(r_cha, 2)}


if __name__ == "__main__":
    rows = pd.DataFrame(cell_rows(sys.argv[1]))
    rows.to_csv(OUT, index=False)
    r = rows.r_discharge_1c_10s_mohm
    print(f"{len(rows)} cells; 1C 10 s discharge resistance: median {r.median():.1f} mOhm, "
          f"5-95 % {r.quantile(0.05):.1f}-{r.quantile(0.95):.1f}, "
          f"coefficient of variation {100 * r.std() / r.mean():.1f} %; "
          f"rest voltage {rows.rest_voltage_v.min():.3f}-{rows.rest_voltage_v.max():.3f} V")
