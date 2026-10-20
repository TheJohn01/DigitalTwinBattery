"""Make the small files in data/gray2026/ from the Zenodo dataset of Gray & Vagg (2026),
"280 Ah prismatic LFP cell: characterisation and aging data", doi:10.5281/zenodo.20813753
(CC BY 4.0).

Run: python scripts/extract_gray2026.py capacity_hppc_entropy.zip aging.zip data_folder

- The published analyses (capacity vs temperature, HPPC resistances, entropy coefficient,
  capacity and resistance at each check-up of the ageing test) are copied unchanged.
- discharge_C10_25C.csv: the 25 °C capacity-test discharge (28 A, about C/10), one row a minute.
- capacity_test_25C.csv: charge and discharge capacity and energy of that test.
- pseudo_ocv_25C.csv: mean of that charge and discharge voltage at the same SOC (5-95 %), and
  half their difference (hysteresis plus overpotential).
- ageing_conditions.csv: mean cell temperature while cycling at 1C and while resting,
  and the cycling rate in days, from the raw ageing data (1.1 GB, read in chunks).
"""
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

char_zip, ageing_zip, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)

with zipfile.ZipFile(char_zip) as z:
    for name in ("LIC_capacity_analysis.csv", "LIC_hppc_analysis.csv", "LIC_entropy_analysis.csv"):
        (out / name).write_bytes(z.read(f"capacity_hppc_entropy/{name}"))
    with z.open("capacity_hppc_entropy/25C_capacity.csv") as f:
        d = pd.read_csv(f)

# the charge and discharge are the long segments with positive and negative current
segment = (np.sign(d["Current_A"].round(0)) != np.sign(d["Current_A"].round(0)).shift()).cumsum()
dis = max((g for _, g in d.groupby(segment) if g["Current_A"].mean() < -1), key=len)
cha = max((g for _, g in d.groupby(segment) if g["Current_A"].mean() > 1), key=len)


def soc_curve(g):
    """(fraction of the step's charge, voltage); 1-second rows."""
    q = np.cumsum(np.abs(g["Current_A"].to_numpy()))
    return q / q[-1], g["Voltage_V"].to_numpy()


def ah_wh(g):
    t, i, v = g["Time_s"].to_numpy(), np.abs(g["Current_A"].to_numpy()), g["Voltage_V"].to_numpy()
    return np.trapezoid(i, t) / 3600, np.trapezoid(i * v, t) / 3600


(q_ch, e_ch), (q_dis, e_dis) = ah_wh(cha), ah_wh(dis)
pd.DataFrame({"step": ["charge", "discharge"], "current_A": [cha["Current_A"].mean(), dis["Current_A"].mean()],
              "capacity_Ah": [q_ch, q_dis], "energy_Wh": [e_ch, e_dis]}).round(3).to_csv(
    out / "capacity_test_25C.csv", index=False)

soc = np.round(np.linspace(0.05, 0.95, 91), 3)
q_c, v_c = soc_curve(cha)
q_d, v_d = soc_curve(dis)
v_charge, v_discharge = np.interp(soc, q_c, v_c), np.interp(1 - soc, q_d, v_d)
pd.DataFrame({"soc": soc, "pseudo_ocv_V": (v_charge + v_discharge) / 2,
              "half_gap_V": (v_charge - v_discharge) / 2}).round(5).to_csv(
    out / "pseudo_ocv_25C.csv", index=False)
t = dis["Time_s"].to_numpy() - dis["Time_s"].iloc[0]
q = np.concatenate([[0], np.cumsum(-0.5 * (dis["Current_A"].to_numpy()[1:]
                                          + dis["Current_A"].to_numpy()[:-1]) * np.diff(t))]) / 3600
keep = np.arange(0, len(t), 60)
pd.DataFrame({"time_s": t[keep], "discharged_Ah": q[keep],
              "voltage_V": dis["Voltage_V"].to_numpy()[keep],
              "temperature_C": dis["Temperature_K"].to_numpy()[keep] - 273.15}
             ).round(5).to_csv(out / "discharge_C10_25C.csv", index=False)

with zipfile.ZipFile(ageing_zip) as z:
    (out / "LIC_aging_analysed.csv").write_bytes(z.read("LIC_aging/LIC_aging_analysed.csv"))
    sums = {"cycling": [0.0, 0], "rest": [0.0, 0]}
    t_end = 0.0
    with z.open("LIC_aging/LIC_aging_data.csv") as f:
        for chunk in pd.read_csv(f, chunksize=2_000_000):
            cycling = chunk["current"].abs() > 200          # 1C = 280 A
            rest = chunk["current"].abs() < 1
            for key, rows in (("cycling", cycling), ("rest", rest)):
                sums[key][0] += chunk.loc[rows, "midT"].sum()
                sums[key][1] += int(rows.sum())
            t_end = float(chunk["time"].iloc[-1])
pd.DataFrame({"quantity": ["mean cell temperature at 1C [C]", "mean cell temperature at rest [C]",
                           "test duration [days]"],
              "value": [sums["cycling"][0] / sums["cycling"][1], sums["rest"][0] / sums["rest"][1],
                        t_end / 86400]}).round(2).to_csv(out / "ageing_conditions.csv", index=False)
print("written to", out)
