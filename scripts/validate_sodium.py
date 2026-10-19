"""Check the sodium-ion physics model (Schneider et al. 2025 parameters) against measurements
of the same commercial cell, Mushang NA18650-1250:
1. discharge voltage and surface temperature at C/100-5C, 25 °C (Schneider et al. 2025,
   Figs. 15 and 16; data/schneider2025/measured_*.csv). Protocol: CC-CV charge at C/3 to
   3.8 V until C/100, 1 h rest, discharge to 1.5 V. h = 10 W/m2K reproduces their chamber.
2. round-trip energy efficiency at 25 °C (Rehm et al. 2025, J. Power Sources 633, 236290:
   93.6 % at 0.67C for this cell; 89-92 % at 1C for the three cells they tested).
Writes results/sodium_validation.csv and docs/sodium_validation.png.

Run: python scripts/validate_sodium.py   (about one minute)
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm

from battery_twin.chemistry import build_model, mesh_settings
from battery_twin.constants import DATA_DIR

FOLDER = DATA_DIR / "schneider2025"
volt = pd.read_csv(FOLDER / "measured_discharge_voltage.csv")
temp = pd.read_csv(FOLDER / "measured_surface_temperature.csv")
H_CHAMBER = 10.0


def simulate(steps, n_cycles=1):
    model, pv, _ = build_model("Na-ion", "DFN", 25.0, H_CHAMBER)
    sim = pybamm.Simulation(model, parameter_values=pv,
                            experiment=pybamm.Experiment([tuple(steps)] * n_cycles),
                            **mesh_settings(model, 2.0))
    return sim.solve()


rows = []
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
for k, c_rate in enumerate(sorted(volt["c_rate"].unique())):
    sol = simulate(["Charge at C/3 until 3.8 V", "Hold at 3.8 V until C/100", "Rest for 1 hour",
                    f"Discharge at {c_rate}C until 1.5 V"])
    step = sol.cycles[0].steps[-1]
    q = 1000 * (step["Discharge capacity [A.h]"].entries - step["Discharge capacity [A.h]"].entries[0])
    v = step["Voltage [V]"].entries
    t_cell = step["X-averaged cell temperature [C]"].entries
    m = volt[volt["c_rate"] == c_rate]
    inside = m["discharge_capacity_mAh"] <= q.max()
    err = np.interp(m["discharge_capacity_mAh"][inside], q, v) - m["voltage_V"][inside]
    mt = temp[temp["c_rate"] == c_rate]
    rows.append({"C-rate": c_rate,
                 "Capacity model [mAh]": q.max(), "Capacity measured [mAh]": m["discharge_capacity_mAh"].max(),
                 "Voltage RMSE [mV]": 1000 * float(np.sqrt(np.mean(err ** 2))),
                 "Temperature rise model [K]": t_cell.max() - t_cell[0],
                 "Temperature rise measured [K]": mt["surface_temperature_C"].max()
                 - mt["surface_temperature_C"].iloc[:3].mean()})
    color = f"C{k}"
    ax[0].plot(q, v, color=color, label=f"{c_rate:g}C")
    ax[0].plot(m["discharge_capacity_mAh"], m["voltage_V"], "--", color=color)
    ax[1].plot(q, t_cell, color=color)
    ax[1].plot(mt["discharge_capacity_mAh"], mt["surface_temperature_C"], "--", color=color)

ax[0].set(xlabel="Discharge capacity [mAh]", ylabel="Voltage [V]",
          title="Lines: model, dashed: measured (Schneider 2025)")
ax[1].set(xlabel="Discharge capacity [mAh]", ylabel="Cell temperature [°C]")
ax[0].legend()
fig.tight_layout()
Path("docs").mkdir(exist_ok=True)
fig.savefig("docs/sodium_validation.png", dpi=120)

for c_rate, measured in [(0.67, "93.6 % (this cell)"), (1.0, "89-92 % (three cells)")]:
    sol = simulate([f"Discharge at {c_rate}C until 1.5 V", "Rest for 1 hour",
                    f"Charge at {c_rate}C until 3.8 V", "Hold at 3.8 V until 0.05C",
                    "Rest for 1 hour"], n_cycles=2)
    cyc = sol.cycles[-1]
    p = cyc["Voltage [V]"].entries * cyc["Current [A]"].entries
    t = cyc["Time [s]"].entries
    eff = 100 * np.trapezoid(np.clip(p, 0, None), t) / np.trapezoid(np.clip(-p, 0, None), t)
    print(f"Round-trip efficiency {c_rate:g}C, 25 °C: model {eff:.1f} %, measured {measured}")

df = pd.DataFrame(rows)
print(df.round(1).to_string(index=False))
Path("results").mkdir(exist_ok=True)
df.to_csv("results/sodium_validation.csv", index=False)
