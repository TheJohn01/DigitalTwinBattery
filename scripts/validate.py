"""Compare both NMC models with the measured LG M50T data (Kirkaldy et al. 2024):
1. the physics model's SEI growth (calibrated on this data), as lithium loss;
2. the empirical ageing model (fitted to other, full-depth data), as capacity.
The test cycled the cells between 70 and 85 % state of charge.
Writes results/model_vs_measured.csv."""
from pathlib import Path

import numpy as np
import pandas as pd

from battery_twin.ageing import predict_capacity
from battery_twin.calibration import load_cells, make_storage_sim, simulated_lli
from battery_twin.chemistry import CHEMISTRIES

nmc = CHEMISTRIES["NMC"]["updates"]
x = [np.log10(nmc["SEI solvent diffusivity [m2.s-1]"]),
     nmc["SEI growth activation energy [J.mol-1]"] / 1000]
sim = make_storage_sim(nmc["Initial concentration in negative electrode [mol.m-3]"])

# One test cycle: 1C discharge 85 -> 70 %, 0.3C charge back, then rest
# (6,204 cycles took 258 days, so each cycle lasted about one hour including check-ups)
period = 258 * 86400 / 6204
t = np.array([0, 540, 2340, period])
soc = np.array([0.85, 0.70, 0.85, 0.85])

rows = []
for cell in load_cells():
    lli = simulated_lli(sim, x, cell["surface_T"], cell["days"])
    n = np.maximum((cell["days"] * 86400 / period).astype(int), 1)
    q = predict_capacity("NMC", t, soc, np.full(len(t), cell["surface_T"]), int(n.max()))
    for k in range(len(n)):
        rows.append({"Cell": cell["name"], "Chamber [°C]": cell["chamber"], "Day": cell["days"][k],
                     "Measured LLI [%]": cell["lli"][k], "Physics LLI [%]": lli[k],
                     "Measured SOH [%]": cell["soh"][k], "Empirical SOH [%]": 100 * q[n[k] - 1]})
df = pd.DataFrame(rows)

for chamber, g in df.groupby("Chamber [°C]"):
    rmse_phys = np.sqrt(np.mean((g["Physics LLI [%]"] - g["Measured LLI [%]"]) ** 2))
    rmse_emp = np.sqrt(np.mean((g["Empirical SOH [%]"] - g["Measured SOH [%]"]) ** 2))
    print(f"{chamber} °C chamber: physics LLI RMSE {rmse_phys:.2f} %-points | "
          f"empirical SOH RMSE {rmse_emp:.2f} %-points")
Path("results").mkdir(exist_ok=True)
df.to_csv("results/model_vs_measured.csv", index=False)
print("Saved results/model_vs_measured.csv")
