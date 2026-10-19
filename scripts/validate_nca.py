"""Check the NCA physics model (Schmitt et al. 2023 parameters) against measurements of the same
commercial cell, Samsung INR21700-50E: discharges at 0.04C, 0.5C and 1C after a 0.5C CC-CV
charge, 25 °C (Schmitt et al. 2023, Fig. 14a; data/schmitt2023/measured_discharge_voltage.csv).
The paper's own model was isothermal; here the program's lumped thermal model is used with
h = 10 W/m2K (climate chamber), because the cell warms by several kelvin at 1C.
Writes results/nca_validation.csv and docs/nca_validation.png.

Run: python scripts/validate_nca.py   (under a minute)
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm

from battery_twin.chemistry import build_model
from battery_twin.constants import DATA_DIR
from battery_twin.nca_params import ELECTRODE_AREA

measured = pd.read_csv(DATA_DIR / "schmitt2023" / "measured_discharge_voltage.csv")
H_CHAMBER = 10.0
MAH_CM2_PER_AH = 1000 / (ELECTRODE_AREA * 1e4)

rows = []
fig, ax = plt.subplots(figsize=(6, 4))
for k, c_rate in enumerate(sorted(measured["c_rate"].unique())):
    model, pv, _ = build_model("NCA", "DFN", 25.0, H_CHAMBER)
    steps = ("Charge at 0.5C until 4.2 V", "Hold at 4.2 V until C/50", "Rest for 1 hour",
             f"Discharge at {c_rate}C until 2.5 V")
    sol = pybamm.Simulation(model, parameter_values=pv,
                            experiment=pybamm.Experiment([steps])).solve(initial_soc=0.5)
    step = sol.cycles[0].steps[-1]
    q_ah = step["Discharge capacity [A.h]"].entries - step["Discharge capacity [A.h]"].entries[0]
    q, v = q_ah * MAH_CM2_PER_AH, step["Voltage [V]"].entries
    m = measured[measured["c_rate"] == c_rate]
    body = m["voltage_V"] > 2.6                    # the curve; the last row is the 2.5 V end point
    err = np.interp(m["discharge_capacity_mAh_cm2"][body], q, v) - m["voltage_V"][body]
    t_cell = step["X-averaged cell temperature [C]"].entries
    rows.append({"C-rate": c_rate,
                 "Capacity model [mAh/cm2]": q.max(),
                 "Capacity measured [mAh/cm2]": m["discharge_capacity_mAh_cm2"].max(),
                 "Capacity error [%]": 100 * (q.max() / m["discharge_capacity_mAh_cm2"].max() - 1),
                 "Voltage RMSE [mV]": 1000 * float(np.sqrt(np.mean(err ** 2))),
                 "Temperature rise model [K]": t_cell.max() - t_cell[0]})
    ax.plot(q, v, color=f"C{k}", label=f"{c_rate:g}C model")
    ax.plot(m["discharge_capacity_mAh_cm2"][body], m["voltage_V"][body], ".", ms=2,
            color=f"C{k}", label=f"{c_rate:g}C measured")
ax.set(xlabel="Discharge capacity [mAh/cm²]", ylabel="Voltage [V]", ylim=(2.5, 4.25),
       title="Samsung INR21700-50E: model vs Schmitt et al. (2023)")
ax.legend(fontsize=8)
fig.tight_layout()
Path("docs").mkdir(exist_ok=True)
fig.savefig("docs/nca_validation.png", dpi=120)

df = pd.DataFrame(rows)
print(df.round(2).to_string(index=False))
Path("results").mkdir(exist_ok=True)
df.to_csv("results/nca_validation.csv", index=False)
