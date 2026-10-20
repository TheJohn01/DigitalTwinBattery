"""Check the LFP model (BYD Blade, lfp_blade_params.py) against measurements.

No electrochemical tests of the Blade itself are published beyond its capacity, so the
checks use three sources:
1. Gorsch et al. 2025 (the Blade): capacity, energy and mean voltage at C/10.
2. Liu et al. 2025 (BYD 4680 LFP, same maker, same 70 um cathode coating): 10 s 1C pulse
   resistance per electrode area, 6-17 Ohm cm2 between 80 % and 20 % SOC (Fig. 6c). The
   impedance and rate test of the same paper were used in the fit (fit_blade.py), so the
   rate test is shown but is not an independent check.
3. Gray & Vagg 2026 (280 Ah LFP storage cell, data/gray2026): the C/10 discharge curve (its
   mean with the charge curve set the LFP OCP shift, so this checks the overpotential), the
   change of capacity and resistance with temperature (15-35 °C) and the capacity fade over
   700 cycles at 1C, which checks the empirical LFP ageing model (ageing.py). A different
   cell of the same chemistry: the curve shapes and the temperature trends are compared,
   not the absolute resistance.

Writes results/blade_validation.csv and docs/blade_validation.png.
Run: python scripts/validate_blade.py   (a few minutes)
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm

from battery_twin import lfp_blade_params as blade
from battery_twin.ageing import add_rest, predict_capacity
from battery_twin.chemistry import standard_profile
from battery_twin.constants import DATA_DIR

sys.path.insert(0, str(Path(__file__).parent))
from fit_blade import blade_pulse_resistance, parameter_values, rate_test  # noqa: E402

GRAY = DATA_DIR / "gray2026"
H_CHAMBER = 10.0
MODEL = pybamm.lithium_ion.DFN({"thermal": "lumped", **blade.MODEL_OPTIONS})
rows = []


def solve(pv, steps, initial_soc):
    return pybamm.Simulation(MODEL, parameter_values=pv,
                             experiment=pybamm.Experiment([tuple(steps)])).solve(
        initial_soc=initial_soc)


def step_capacity(step):
    q = step["Discharge capacity [A.h]"].entries
    return abs(float(q[-1] - q[0]))


# 1. Blade at C/10 (Gorsch et al.: CC-CV both ways, CV to C/20, average of the two) --------
pv = parameter_values("Blade", h=H_CHAMBER)
sol = solve(pv, ["Charge at C/10 until 3.65 V", "Hold at 3.65 V until C/20", "Rest for 1 hour",
                 "Discharge at C/10 until 2.6 V", "Hold at 2.6 V until C/20"], 0.0)
st = sol.cycles[0].steps
q_charge = step_capacity(st[0]) + step_capacity(st[1])
q_discharge = step_capacity(st[3]) + step_capacity(st[4])
energy = sum(np.trapezoid(s["Voltage [V]"].entries * s["Current [A]"].entries,
                          s["Time [s]"].entries) / 3600 for s in (st[3], st[4]))
rows += [{"Check": "Blade C/10 capacity [Ah]", "Model": (q_charge + q_discharge) / 2,
          "Measured": 135.0, "Source": "Gorsch 2025 (set by the electrode balance)"},
         {"Check": "Blade C/10 discharge energy [Wh]", "Model": energy, "Measured": 432.0,
          "Source": "Gorsch 2025 (nominal energy)"},
         {"Check": "Blade mean discharge voltage [V]", "Model": energy / q_discharge,
          "Measured": 3.2, "Source": "Gorsch 2025 (nominal voltage)"}]

# heat capacity of the lumped thermal model, per kg of cell (Blade 2.7 kg)
layers = ["Negative electrode", "Separator", "Positive electrode",
          "Negative current collector", "Positive current collector"]
rho_cp = sum(pv[f"{k} density [kg.m-3]"] * pv[f"{k} specific heat capacity [J.kg-1.K-1]"]
             * pv[f"{k} thickness [m]"] for k in layers) / sum(pv[f"{k} thickness [m]"] for k in layers)
rows.append({"Check": "Blade heat capacity [J/(kg K)]", "Model": rho_cp * pv["Cell volume [m3]"] / 2.7,
             "Measured": 67.2 / 0.076,
             "Source": "A123 26650 LFP cell, 67.2 J/K (Lin et al. 2014) over its 76 g"})

# Blade 18 s 1C pulses at 20 °C (Gorsch Fig. 8C): the mean level set the contact resistance,
# so only the change with SOC is a check
dcr = pd.read_csv(DATA_DIR / "gorsch2025" / "blade_dcr_20C.csv").sort_values("soc_pct", ascending=False)
dcr["model_mOhm"] = 1000 * blade_pulse_resistance(parameter_values("Blade", ambient_c=20.0),
                                                  tuple(dcr["soc_pct"]))
rows.append({"Check": "Blade 18 s pulse resistance, 20 % / 90 % SOC (fitted level)",
             "Model": dcr["model_mOhm"].iloc[-1] / dcr["model_mOhm"].iloc[0],
             "Measured": dcr["resistance_mOhm"].iloc[-1] / dcr["resistance_mOhm"].iloc[0],
             "Source": "Gorsch 2025, Fig. 8C"})
rows.append({"Check": "Blade 18 s pulse resistance RMSE, 20-90 % SOC [mOhm]",
             "Model": float(np.sqrt(np.mean((dcr["model_mOhm"] - dcr["resistance_mOhm"]) ** 2))),
             "Measured": 0.0, "Source": "Gorsch 2025, Fig. 8C"})

# 2. BYD 4680: rate test (fitted) and 10 s 1C pulses (Liu et al. protocol) -------------------
pv4680 = parameter_values("BYD4680")
cap = rate_test(pv4680)
rows.append({"Check": "BYD 4680 C/2 discharge capacity [Ah]", "Model": cap["C/2"],
             "Measured": 15.00, "Source": "Liu 2025 (text: about 15.00 Ah at C/2)"})
for rate, measured in (("1C", 94.7), ("2C", 87.9)):
    rows.append({"Check": f"BYD 4680 {rate} / C/2 discharge capacity [%] (fitted)",
                 "Model": 100 * cap[rate] / cap["C/2"], "Measured": measured,
                 "Source": "Liu 2025, Fig. 7"})
steps = ["Charge at C/5 until 3.65 V", "Hold at 3.65 V until C/60", "Rest for 1 hour"]
pulse = ["Discharge at C/2 for 24 minutes", "Rest for 3 hours", "Discharge at 1C for 10 seconds",
         "Rest for 10 minutes", "Charge at 1C for 10 seconds", "Rest for 10 minutes"]
sol = solve(pv4680, steps + pulse * 4, 0.0)
area_cm2 = blade.electrode_fractions("BYD4680")[0] * 1e4
asr = []
for k in range(4):
    base = 3 + 6 * k
    v_rest = sol.cycles[0].steps[base + 1]["Voltage [V]"].entries[-1]
    for name, idx in (("discharge", base + 2), ("charge", base + 4)):
        s = sol.cycles[0].steps[idx]
        v, i = s["Voltage [V]"].entries[1:], s["Current [A]"].entries[1:]
        asr.append({"SOC [%]": 80 - 20 * k, "Direction": name,
                    "ASR [Ohm cm2]": float(np.mean((v_rest - v) / i)) * area_cm2})
asr = pd.DataFrame(asr)
rows.append({"Check": "BYD 4680 10 s pulse resistance, 80-20 % SOC [Ohm cm2]",
             "Model": f"{asr['ASR [Ohm cm2]'].min():.1f}-{asr['ASR [Ohm cm2]'].max():.1f}",
             "Measured": "6-17", "Source": "Liu 2025, Fig. 6c"})

# 3a. Gray & Vagg: C/10 discharge curve (28 A on 302 Ah) at 25 °C ---------------------------
measured = pd.read_csv(GRAY / "discharge_C10_25C.csv")
c_rate = 28.0 / 302.3
sol = solve(parameter_values("Blade", h=H_CHAMBER),
            [f"Charge at {c_rate:.4f}C until 3.65 V", "Rest for 15 minutes",
             f"Discharge at {c_rate:.4f}C until 2.6 V"], 0.0)
energy = {}
for name, idx in (("charge", 0), ("discharge", 2)):
    s = sol.cycles[0].steps[idx]
    energy[name] = abs(np.trapezoid(s["Voltage [V]"].entries * s["Current [A]"].entries,
                                    s["Time [s]"].entries)) / 3600
gray_test = pd.read_csv(GRAY / "capacity_test_25C.csv").set_index("step")["energy_Wh"]
rows.append({"Check": "Energy efficiency at C/10, 25 °C [%] (uses the fitted hysteresis)",
             "Model": 100 * energy["discharge"] / energy["charge"],
             "Measured": 100 * gray_test["discharge"] / gray_test["charge"],
             "Source": "Gray & Vagg 2026 (280 Ah LFP cell)"})
s = sol.cycles[0].steps[2]
q_model = s["Discharge capacity [A.h]"].entries - s["Discharge capacity [A.h]"].entries[0]
dod_model, v_model = q_model / q_model[-1], s["Voltage [V]"].entries
dod_meas = measured["discharged_Ah"] / measured["discharged_Ah"].iloc[-1]
inside = (dod_meas > 0.1) & (dod_meas < 0.9)
err = np.interp(dod_meas[inside], dod_model, v_model) - measured["voltage_V"][inside]
rows.append({"Check": "C/10 discharge voltage vs 280 Ah LFP cell, 10-90 % DOD, RMSE [mV]",
             "Model": 1000 * float(np.sqrt(np.mean(err ** 2))), "Measured": 0.0,
             "Source": "Gray & Vagg 2026 (different cell)"})

# 3b. temperature: C/10 capacity and 30 s 0.5C pulse resistance at 50 % SOC vs 25 °C -------
gray_cap = pd.read_csv(GRAY / "LIC_capacity_analysis.csv").set_index("Temperature_C")["Capacity_Ah"]
gray_r = pd.read_csv(GRAY / "LIC_hppc_analysis.csv")
gray_r["R"] = gray_r["R0_Ohm"] + gray_r["R1_Ohm"]
gray_r = gray_r.groupby("Temperature_C")["R"].mean()
temperature = []
for t_c in gray_cap.index:
    pv_t = parameter_values("Blade", ambient_c=float(t_c), h=H_CHAMBER)
    sol = solve(pv_t, [f"Charge at {c_rate:.4f}C until 3.65 V", "Rest for 15 minutes",
                       f"Discharge at {c_rate:.4f}C until 2.6 V"], 0.0)
    q = step_capacity(sol.cycles[0].steps[2])
    sol = solve(pv_t, ["Rest for 1 hour", "Discharge at 0.5C for 30 seconds"], 0.5)
    v = sol.cycles[0].steps[0]["Voltage [V]"].entries[-1]
    s = sol.cycles[0].steps[1]
    r = (v - s["Voltage [V]"].entries[-1]) / s["Current [A]"].entries[-1]
    temperature.append({"Temperature [C]": t_c, "Capacity model": q, "Resistance model": r,
                        "Capacity measured": gray_cap[t_c], "Resistance measured": gray_r[t_c]})
temperature = pd.DataFrame(temperature).set_index("Temperature [C]")
for col in ("Capacity model", "Resistance model", "Capacity measured", "Resistance measured"):
    temperature[col + " / 25 C"] = temperature[col] / temperature.loc[25, col]
for kind in ("Capacity", "Resistance"):
    for t_c in (15, 35):
        rows.append({"Check": f"{kind} at {t_c} °C / at 25 °C",
                     "Model": temperature.loc[t_c, f"{kind} model / 25 C"],
                     "Measured": temperature.loc[t_c, f"{kind} measured / 25 C"],
                     "Source": "Gray & Vagg 2026 (R = R0 + R1 of their HPPC fit, mean over SOC)"})

# 3c. ageing: 700 cycles at 1C, cell at 39.6 °C while cycling (data/gray2026) ---------------
rpt = pd.read_csv(GRAY / "LIC_aging_analysed.csv")
cond = pd.read_csv(GRAY / "ageing_conditions.csv").set_index("quantity")["value"]
cycles_per_year = 700 / cond["test duration [days]"] * 365
t, soc = standard_profile(1.0, 1.0)
t, soc, temp, _ = add_rest(t, soc, np.full(len(t), cond["mean cell temperature at 1C [C]"]),
                           cycles_per_year, cond["mean cell temperature at rest [C]"])
q_age = predict_capacity("LFP", t, soc, temp, 700)
soh_model = np.interp(rpt["Total_cycles"], np.arange(1, 701), q_age, left=1.0)
rows.append({"Check": "LFP ageing model: capacity after 700 cycles at 1C [%]",
             "Model": 100 * q_age[-1], "Measured": 100 * rpt["SoH"].iloc[-1],
             "Source": "Gray & Vagg 2026 (280 Ah LFP storage cell, about 40 °C)"})
rows.append({"Check": "LFP ageing model: RMSE over the 14 check-ups [%-points]",
             "Model": 100 * float(np.sqrt(np.mean((soh_model - rpt["SoH"]) ** 2))), "Measured": 0.0,
             "Source": "Gray & Vagg 2026"})

# --- output ------------------------------------------------------------------------------
results = pd.DataFrame(rows)
pd.set_option("display.width", 200)
print(results.round(3).to_string(index=False))
print(asr.round(1).to_string(index=False))
Path("results").mkdir(exist_ok=True)
results.to_csv("results/blade_validation.csv", index=False)

fig, ax = plt.subplots(3, 2, figsize=(10, 10.5))
ax[2, 0].plot(dcr["soc_pct"], dcr["resistance_mOhm"], "o", label="BYD Blade (Gorsch et al., Fig. 8C)")
ax[2, 0].plot(dcr["soc_pct"], dcr["model_mOhm"], "-", label="model (mean level fitted)")
ax[2, 0].set(xlabel="SOC [%]", ylabel="18 s pulse resistance [mΩ]", ylim=(0, 1.5),
             title="BYD Blade, 1C pulses, 20 °C")
ax[2, 0].legend(fontsize=8)
ax[2, 1].axis("off")
ax[0, 0].plot(100 * dod_meas, measured["voltage_V"], ".", ms=2, label="280 Ah LFP cell (Gray & Vagg)")
ax[0, 0].plot(100 * dod_model, v_model, label="model (BYD Blade)")
ax[0, 0].set(xlabel="Depth of discharge [%]", ylabel="Voltage [V]", ylim=(2.6, 3.5),
             title="C/10 discharge, 25 °C")
ax[0, 0].legend(fontsize=8)
for kind, colour in (("Capacity", "C0"), ("Resistance", "C1")):
    ax[0, 1].plot(temperature.index, temperature[f"{kind} measured / 25 C"], "o", color=colour,
                  label=f"{kind}, 280 Ah cell")
    ax[0, 1].plot(temperature.index, temperature[f"{kind} model / 25 C"], "-", color=colour,
                  label=f"{kind}, model")
ax[0, 1].set(xlabel="Temperature [°C]", ylabel="Relative to 25 °C", title="Temperature dependence")
ax[0, 1].legend(fontsize=8)
for name, marker in (("discharge", "o"), ("charge", "s")):
    a = asr[asr["Direction"] == name]
    ax[1, 0].plot(a["SOC [%]"], a["ASR [Ohm cm2]"], marker + "-", label=f"model, {name}")
ax[1, 0].axhspan(6, 17, color="grey", alpha=0.2, label="measured range (Liu et al.)")
ax[1, 0].set(xlabel="SOC [%]", ylabel="10 s pulse resistance [Ω cm²]", ylim=(0, 25),
             title="BYD 4680 LFP, 1C pulses, 25 °C")
ax[1, 0].legend(fontsize=8)
ax[1, 1].plot(rpt["Total_cycles"], 100 * rpt["SoH"], "o", label="280 Ah cell (Gray & Vagg)")
ax[1, 1].plot(np.arange(1, 701), 100 * q_age, label="LFP ageing model (ageing.py)")
ax[1, 1].set(xlabel="Cycles (1C, about 40 °C)", ylabel="Capacity [%]", title="Capacity fade")
ax[1, 1].legend(fontsize=8)
fig.tight_layout()
Path("docs").mkdir(exist_ok=True)
fig.savefig("docs/blade_validation.png", dpi=120)
