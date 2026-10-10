"""Calibrate the NMC (LG M50 / Chen 2020) model against measured ageing data.

Data: Kirkaldy et al., J. Power Sources 603 (2024) 234185 (see data/kirkaldy2024/README.md).
Three quantities are fitted, one at a time:
  1. Lithium inventory, so the C/10 capacity matches the measured 4.857 Ah.
  2. SEI growth (solvent diffusivity and activation energy), fitted to the measured
     loss of lithium inventory (LLI) of the 25 °C and 40 °C cells. The 10 °C cells are
     kept aside to test the fit.
  3. The cooling coefficient h, so self-heating matches the measured cell temperature
     in the 25 °C chamber.
The results are printed and saved to results/calibration.json. To use them, copy that file
over src/battery_twin/data/calibration.json; chemistry.py reads it from there.

Run: python scripts/calibrate.py   (takes a few minutes)
"""
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pybamm
from scipy.optimize import least_squares

from .chemistry import build_model

DATA = Path(__file__).parent / "data"
MEASURED_C10_CAPACITY_AH = 4.857   # mean of 40 cells, Kirkaldy et al. 2024, Table 7
C_N_KEY = "Initial concentration in negative electrode [mol.m-3]"
D_KEY = "SEI solvent diffusivity [m2.s-1]"
E_KEY = "SEI growth activation energy [J.mol-1]"


# ---------------------------------------------------------------------------
# Measured data
# ---------------------------------------------------------------------------
def load_cells():
    folder = DATA / "kirkaldy2024"
    paths = sorted(folder.glob("Expt 2,2 - cell * - Processed Data.csv"))
    if len(paths) != 6:
        raise FileNotFoundError(
            f"Expected the 6 measured-data files in {folder}, found {len(paths)}.\n"
            "Copy the files 'Expt 2,2 - cell A (10degC) - Processed Data.csv' ... 'cell F (40degC)' "
            "into that folder, without renaming them (see its README.md).")
    cells = []
    for path in paths:
        name, chamber = re.search(r"cell (\w) \((\d+)degC\)", path.name).groups()
        df = pd.read_csv(path).iloc[1:]          # first row is beginning of life (LLI = 0)
        cells.append({
            "name": name,
            "chamber": int(chamber),
            "surface_T": df["Age set av. temperature [°C]"].mean(),
            "days": df["Days of degradation"].to_numpy(),
            "lli": 100 * df["LLI"].to_numpy(),
            "soh": 100 * df["SoH"].to_numpy(),
        })
    return cells


# ---------------------------------------------------------------------------
# 1. Lithium inventory -> C/10 capacity
# ---------------------------------------------------------------------------
def simulated_c10_capacity(c_n):
    pv = pybamm.ParameterValues("Chen2020")
    pv.update({C_N_KEY: c_n})
    rpt = pybamm.Experiment([("Charge at 0.3C until 4.2 V", "Hold at 4.2 V until C/100",
                              "Rest for 1 hour", "Discharge at C/10 until 2.5 V")])
    sol = pybamm.Simulation(pybamm.lithium_ion.SPMe(), parameter_values=pv, experiment=rpt).solve()
    q = sol.cycles[0].steps[3]["Discharge capacity [A.h]"].entries
    return float(q[-1] - q[0])


def fit_capacity():
    # Capacity is linear in the lithium inventory, so a few secant steps are enough.
    c_a, c_b = 29866.0, 28000.0
    q_a, q_b = simulated_c10_capacity(c_a), simulated_c10_capacity(c_b)
    print(f"Default Chen2020 C/10 capacity: {q_a:.3f} Ah (measured {MEASURED_C10_CAPACITY_AH} Ah)")
    for _ in range(3):
        c_new = c_b + (MEASURED_C10_CAPACITY_AH - q_b) * (c_b - c_a) / (q_b - q_a)
        c_a, q_a = c_b, q_b
        c_b, q_b = c_new, simulated_c10_capacity(c_new)
    print(f"Calibrated: {C_N_KEY} = {c_b:.0f} -> C/10 capacity {q_b:.3f} Ah")
    return c_b, q_a


# ---------------------------------------------------------------------------
# 2. SEI growth -> loss of lithium inventory
# ---------------------------------------------------------------------------
# The solvent-diffusion SEI model does not depend on current, so cycling ages the
# model exactly like storage for the same time at the same temperature. Storage is
# much faster to simulate. check_storage_shortcut() verifies this assumption.
def make_storage_sim(c_n):
    pv = pybamm.ParameterValues("Chen2020")
    pv.update({C_N_KEY: c_n, "Current function [A]": 0, D_KEY: "[input]", E_KEY: "[input]",
               "Ambient temperature [K]": "[input]", "Initial temperature [K]": "[input]"})
    model = pybamm.lithium_ion.SPM({"SEI": "solvent-diffusion limited"})
    return pybamm.Simulation(model, parameter_values=pv,
                             solver=pybamm.IDAKLUSolver(rtol=1e-8, atol=1e-10))


def simulated_lli(sim, x, temp_c, days):
    """x = [log10 of SEI solvent diffusivity, activation energy in kJ/mol]"""
    temp_k = temp_c + 273.15
    inputs = {D_KEY: 10 ** x[0], E_KEY: 1000 * x[1],
              "Ambient temperature [K]": temp_k, "Initial temperature [K]": temp_k}
    sol = sim.solve([0, 86400 * max(days)], inputs=inputs, initial_soc=0.775)  # middle of 70-85 %
    return np.atleast_1d(sol["Loss of lithium inventory [%]"](86400 * np.asarray(days)))


def residuals(x, sim, cells):
    return np.concatenate([simulated_lli(sim, x, c["surface_T"], c["days"]) - c["lli"] for c in cells])


def rmse(x, sim, cells):
    return float(np.sqrt(np.mean(residuals(x, sim, cells) ** 2)))


def check_storage_shortcut(c_n, x):
    """20 real 70-85 % cycles must lose the same lithium as storage for the same time."""
    pv = pybamm.ParameterValues("Chen2020")
    pv.update({C_N_KEY: c_n, D_KEY: 10 ** x[0], E_KEY: 1000 * x[1]})
    model = pybamm.lithium_ion.SPM({"SEI": "solvent-diffusion limited"})
    cycling = pybamm.Experiment([("Discharge at 1C for 9 minutes", "Charge at 0.3C for 30 minutes")] * 20)
    sol = pybamm.Simulation(model, parameter_values=pv, experiment=cycling).solve(initial_soc=0.85)
    lli_cycling = sol["Loss of lithium inventory [%]"].entries[-1]
    lli_storage = simulated_lli(make_storage_sim(c_n), x, 25.0, [sol["Time [s]"].entries[-1] / 86400])[0]
    print(f"Shortcut check: 20 cycles give {lli_cycling:.4f} % LLI, storage gives {lli_storage:.4f} %")
    return abs(lli_cycling / lli_storage - 1) < 0.02


def fit_sei(c_n, cells):
    sim = make_storage_sim(c_n)
    train = [c for c in cells if c["chamber"] != 10]
    test = [c for c in cells if c["chamber"] == 10]
    default = [np.log10(2.5e-22), 38.0]
    fit = least_squares(residuals, x0=[-19.5, 38.0], args=(sim, train),
                        bounds=([-24, 0], [-16, 150]), diff_step=1e-4)
    x = fit.x
    print(f"Default SEI parameters: RMSE {rmse(default, sim, train):.2f} %-points LLI (25/40 °C cells)")
    print(f"Fitted:  SEI solvent diffusivity = {10 ** x[0]:.3e} m2/s, activation energy = {x[1]:.1f} kJ/mol")
    print(f"         RMSE training cells (25/40 °C): {rmse(x, sim, train):.2f} %-points LLI")
    print(f"         RMSE test cells (10 °C, not used in fit): {rmse(x, sim, test):.2f} %-points LLI")
    return x, sim, default


# ---------------------------------------------------------------------------
# 3. Cooling coefficient -> self-heating
# ---------------------------------------------------------------------------
def mean_temperature_rise(ambient_c, h, c_n):
    model, pv, _ = build_model("NMC", "SPMe", ambient_c, h)
    pv.update({C_N_KEY: c_n})
    protocol = pybamm.Experiment([("Discharge at 1C for 9 minutes", "Charge at 0.3C for 30 minutes")] * 8)
    sol = pybamm.Simulation(model, parameter_values=pv, experiment=protocol).solve(initial_soc=0.85)
    t = sol["Time [s]"].entries
    temp = sol["X-averaged cell temperature [C]"].entries
    late = t > t[-1] / 2                       # second half: close to steady state
    return float(np.trapezoid(temp[late], t[late]) / (t[late][-1] - t[late][0]) - ambient_c)


def fit_cooling(cells, c_n):
    target = np.mean([c["surface_T"] for c in cells if c["chamber"] == 25]) - 25.0
    low, high = 5.0, 60.0                      # rise falls as h grows: bisection
    for _ in range(12):
        h = 0.5 * (low + high)
        if mean_temperature_rise(25.0, h, c_n) > target:
            low = h
        else:
            high = h
    h = 0.5 * (low + high)
    print(f"Cooling coefficient h = {h:.1f} W/m2K (measured rise in 25 °C chamber: {target:.1f} °C)")
    for chamber in (10, 40):
        measured = np.mean([c["surface_T"] for c in cells if c["chamber"] == chamber]) - chamber
        print(f"  {chamber} °C chamber: model rise {mean_temperature_rise(chamber, h, c_n):.1f} °C, "
              f"measured {measured:.1f} °C")
    return h


# ---------------------------------------------------------------------------
def plot(cells, sim, x, default, out_dir):
    colours = {10: "tab:blue", 25: "tab:green", 40: "tab:red"}
    days = np.linspace(1, 260, 120)
    fig, ax = plt.subplots(figsize=(8, 5))
    for chamber in (10, 25, 40):
        group = [c for c in cells if c["chamber"] == chamber]
        temp = np.mean([c["surface_T"] for c in group])
        for c in group:
            ax.plot(c["days"], c["lli"], "o", color=colours[chamber])
        label = "predicted (not fitted)" if chamber == 10 else "fitted"
        ax.plot(days, simulated_lli(sim, x, temp, days), "-", color=colours[chamber],
                label=f"{chamber} °C chamber ({temp:.0f} °C cell): {label}")
        ax.plot(days, simulated_lli(sim, default, temp, days), ":", color=colours[chamber])
    ax.plot([], [], "k:", label="default PyBaMM SEI parameters")
    ax.plot([], [], "ko", label="measured (Kirkaldy et al. 2024)")
    ax.set(xlabel="Time [days]", ylabel="Loss of lithium inventory [%]",
           title="SEI model vs measured LG M50T ageing (70-85 % SoC)")
    ax.legend(fontsize=8)
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(Path(out_dir) / "calibration_fit.png", dpi=120)


def main(out_dir="results"):
    """Run the full calibration and write calibration.json and a plot to out_dir."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    cells = load_cells()
    c_n, default_capacity = fit_capacity()
    x, sim, default = fit_sei(c_n, cells)
    shortcut_ok = check_storage_shortcut(c_n, x)
    h = fit_cooling(cells, c_n)
    plot(cells, sim, x, default, out_dir)

    result = {
        "initial_concentration_negative_mol_m3": c_n,
        "sei_solvent_diffusivity_m2_s": 10 ** x[0],
        "sei_activation_energy_J_mol": 1000 * x[1],
        "cooling_coefficient_W_m2K": h,
        "rmse_lli_train_pct": rmse(x, sim, [c for c in cells if c["chamber"] != 10]),
        "rmse_lli_test_10C_pct": rmse(x, sim, [c for c in cells if c["chamber"] == 10]),
        "storage_shortcut_valid": bool(shortcut_ok),
    }
    json.dump(result, open(Path(out_dir) / "calibration.json", "w"), indent=2)
    print(json.dumps(result, indent=2))
    return result
