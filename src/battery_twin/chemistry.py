"""Battery chemistries and the electrochemical (physics) simulation.

Every other module reads chemistry data from the CHEMISTRIES table below.
The physics model (PyBaMM) simulates a few cycles in full: voltage, current, heat and
state of charge. Long-term capacity fade is then predicted by the empirical models in
ageing.py, driven by the operating conditions of those simulated cycles.
"""
import numpy as np
import pandas as pd
import pybamm

from .ageing import predict_capacity, validity_warnings

# ---------------------------------------------------------------------------
# 1. Chemistry table
# ---------------------------------------------------------------------------
# capex_eur_kwh, co2_kg_per_kwh, eol_credit_kg_per_kg, water_l_per_kwh and
# ecotox_per_kg are INDICATIVE ASSUMPTIONS for comparison, not measured data.
# Capacity fade comes from empirical models fitted to measured data (ageing.py);
# "ageing_source" names the data behind each one.
CHEMISTRIES = {
    "NMC": {
        "label": "NMC / Graphite (Chen 2020, LG M50 21700)",
        "family": "lithium_ion",
        "parameter_set": "Chen2020",
        "v_min": 2.5, "v_max": 4.2,
        # Calibrated by calibrate.py against measured LG M50T ageing data
        # (Kirkaldy et al., J. Power Sources 603 (2024) 234185):
        "updates": {
            "Initial concentration in negative electrode [mol.m-3]": 28342.0,  # C/10 capacity 4.857 Ah
            "SEI solvent diffusivity [m2.s-1]": 2.195e-20,                     # default was 2.5e-22
            "SEI growth activation energy [J.mol-1]": 25400.0,
        },
        "calibration": "Capacity, SEI growth and cooling calibrated to Kirkaldy et al. (2024), LG M50T",
        "ageing_source": "Empirical model (NREL BLAST-Lite) fitted to LG M50 21700 cycling data, "
                         "Truong Bui et al., IEEE 2021",
        "capex_eur_kwh": 125.0,
        "co2_kg_per_kwh": 85.0,        # cradle-to-gate, includes raw materials
        "eol_credit_kg_per_kg": 4.2,   # recycling credit (kg CO2eq avoided per kg)
        "wh_per_kg": 260.0,            # cell-level specific energy
        "water_l_per_kwh": 55.0,
        "ecotox_per_kg": 1.00,
    },
    "LFP": {
        "label": "LFP / Graphite (Prada 2013, A123 26650)",
        "family": "lithium_ion",
        "parameter_set": "Prada2013",
        "v_min": 2.0, "v_max": 3.6,
        # Prada2013 has no thermal geometry: use 26650 can dimensions
        # (other missing thermal/SEI values are borrowed from Chen2020, see build_model)
        "updates": {"Cell volume [m3]": 3.45e-5, "Cell cooling surface area [m2]": 0.00637,
                    "SEI growth activation energy [J.mol-1]": 38000.0},  # OKane 2022
        "calibration": None,
        "ageing_source": "Empirical model (NREL BLAST-Lite) fitted to Sony-Murata 3 Ah LFP data, "
                         "Naumann et al. 2018/2020; Gasper et al., J. Electrochem. Soc. 2022",
        "capex_eur_kwh": 95.0,
        "co2_kg_per_kwh": 55.0,
        "eol_credit_kg_per_kg": 1.5,
        "wh_per_kg": 110.0,
        "water_l_per_kwh": 38.0,
        "ecotox_per_kg": 0.65,
    },
    "NCA": {
        "label": "NCA / Graphite (Kim 2011, pouch)",
        "family": "lithium_ion",
        "parameter_set": "NCA_Kim2011",
        "v_min": 2.7, "v_max": 4.2,
        "updates": {"SEI growth activation energy [J.mol-1]": 38000.0},  # OKane 2022
        "calibration": None,
        "ageing_source": "Empirical model (NREL BLAST-Lite) fitted to Panasonic NCR18650B data, "
                         "Keil et al. 2016 (calendar) and Preger et al. 2020 (cycling)",
        "capex_eur_kwh": 130.0,
        "co2_kg_per_kwh": 90.0,
        "eol_credit_kg_per_kg": 4.2,
        "wh_per_kg": 240.0,
        "water_l_per_kwh": 58.0,
        "ecotox_per_kg": 1.05,
    },
    "Na-ion": {
        "label": "Sodium-ion: Hard carbon / NVPF (Chayambuka 2022)",
        "family": "sodium_ion",
        "parameter_set": "Chayambuka2022",
        "v_min": 2.0, "v_max": 4.2,
        # The published cell is a 3 mAh lab cell. Scaling the electrode width
        # x1000 gives a 3 Ah cell with identical electrochemistry.
        "updates": {"Electrode width [m]": 1000.0,
                    "Nominal cell capacity [A.h]": 3.0,
                    "Current function [A]": 3.0},
        "calibration": None,
        "ageing_source": "Linear fade of 0.1 %/cycle measured on a commercial hard carbon / NVPF "
                         "cell, Carter et al., Energies 2025",
        "capex_eur_kwh": 90.0,
        "co2_kg_per_kwh": 60.0,
        "eol_credit_kg_per_kg": 1.0,
        "wh_per_kg": 140.0,
        "water_l_per_kwh": 30.0,
        "ecotox_per_kg": 0.50,
    },
}

# Uncalibrated Li-ion chemistries use the SEI activation energy from OKane 2022 (38 kJ/mol);
# their parameter sets use 0 J/mol, which would make SEI growth independent of temperature.
# Cooling coefficient that reproduces the measured self-heating in Kirkaldy et al. (2024).
CALIBRATED_H_COOLING = 13.0
MAX_POINTS_PER_CYCLE = 200   # downsampling of the time series for plots/export
MAX_SAVED_CYCLES = 50        # full data kept for at most ~50 cycles


def trapezoid(y, x):
    return float(np.trapezoid(y, x))


# ---------------------------------------------------------------------------
# 2. Model building
# ---------------------------------------------------------------------------
def build_model(chemistry, model_type="SPMe", ambient_c=25.0, h_cooling=CALIBRATED_H_COOLING):
    """Return (model, parameter_values, has_thermal_and_sei)."""
    c = CHEMISTRIES[chemistry]
    pv = pybamm.ParameterValues(c["parameter_set"])
    temp_k = float(ambient_c) + 273.15

    if c["family"] == "sodium_ion":
        # PyBaMM only offers an isothermal sodium-ion DFN without ageing.
        pv.update(c["updates"])
        pv.update({"Ambient temperature [K]": temp_k,
                   "Initial temperature [K]": temp_k}, check_already_exists=False)
        return pybamm.sodium_ion.BasicDFN(), pv, False

    # Fill ONLY missing parameters (e.g. thermal/SEI for Prada2013) from Chen2020.
    # Existing values of the chosen parameter set are never overwritten.
    donor = pybamm.ParameterValues("Chen2020")
    existing = set(pv.keys())
    missing = {k: donor[k] for k in donor.keys() if k not in existing}
    pv.update(missing, check_already_exists=False)

    pv.update({
        "Ambient temperature [K]": temp_k,
        "Initial temperature [K]": temp_k,
        "Total heat transfer coefficient [W.m-2.K-1]": float(h_cooling),
    }, check_already_exists=False)
    pv.update(c["updates"], check_already_exists=False)
    # "Reference temperature [K]" is deliberately NOT changed.

    options = {"thermal": "lumped", "SEI": "solvent-diffusion limited"}
    if model_type == "DFN":
        model = pybamm.lithium_ion.DFN(options)
    else:
        model = pybamm.lithium_ion.SPMe(options)
    return model, pv, True


def build_experiment(chemistry, c_charge, c_discharge, n_cycles):
    c = CHEMISTRIES[chemistry]
    step = (
        f"Discharge at {c_discharge:g}C until {c['v_min']} V",
        "Rest for 5 minutes",
        f"Charge at {c_charge:g}C until {c['v_max']} V",
        f"Hold at {c['v_max']} V until C/20",
        "Rest for 5 minutes",
    )
    # Cycle 0 is a conditioning cycle: the parameter set's initial state does
    # not match the CC-CV charged state, so it is excluded from the results.
    return pybamm.Experiment([step] * (int(n_cycles) + 1))


# ---------------------------------------------------------------------------
# 3. Simulation
# ---------------------------------------------------------------------------
def run_simulation(chemistry, model_type="SPMe", c_charge=1.0, c_discharge=1.0,
                   n_cycles=10, ambient_c=25.0, h_cooling=CALIBRATED_H_COOLING):
    """Run the simulation and return plain DataFrames (easy to cache/export).

    Raises an exception if the solver fails. There is no synthetic fallback.
    """
    model, pv, has_ageing = build_model(chemistry, model_type, ambient_c, h_cooling)
    experiment = build_experiment(chemistry, c_charge, c_discharge, n_cycles)
    save_every = max(1, int(n_cycles) // MAX_SAVED_CYCLES)

    sim = pybamm.Simulation(model, parameter_values=pv, experiment=experiment)
    if save_every > 1:
        solution = sim.solve(save_at_cycles=save_every)
    else:
        solution = sim.solve()

    return summarise(solution, has_ageing, ambient_c, chemistry, model_type)


def _discharge_capacity(cycle):
    """Measured discharge capacity of one cycle. The PyBaMM variable is
    cumulative, so the difference between end and start of the step is used."""
    q = cycle.steps[0]["Discharge capacity [A.h]"].entries
    return float(q[-1] - q[0])


def _discharge_energy_wh(cycle):
    step = cycle.steps[0]
    t = step["Time [s]"].entries
    v = step["Voltage [V]"].entries
    i = step["Current [A]"].entries
    return trapezoid(v * i, t) / 3600.0


def _cycle_temperature(cycle, has_thermal, ambient_c):
    if has_thermal:
        return cycle["X-averaged cell temperature [C]"].entries
    return np.full(len(cycle["Time [s]"].entries), float(ambient_c))


def cycle_profile(cycle, has_thermal, ambient_c):
    """Time, state of charge and cell temperature of one cycle: the operating
    conditions handed to the empirical ageing model."""
    t = cycle["Time [s]"].entries
    i = cycle["Current [A]"].entries                      # + = discharge
    temp = _cycle_temperature(cycle, has_thermal, ambient_c)
    charge_out = np.concatenate([[0.0], np.cumsum(0.5 * (i[1:] + i[:-1]) * np.diff(t))]) / 3600
    soc = np.clip(1.0 - charge_out / np.max(charge_out), 0.0, 1.0)   # full at the start
    idx = np.linspace(0, len(t) - 1, min(len(t), 400)).astype(int)
    return pd.DataFrame({"Time [s]": t[idx] - t[0], "SOC": soc[idx], "Temperature [°C]": temp[idx]})


def _efficiency_row(cycle_number, t, v, i):
    q_dis = trapezoid(np.clip(i, 0, None), t) / 3600.0      # PyBaMM: + = discharge
    q_cha = trapezoid(np.clip(-i, 0, None), t) / 3600.0
    e_dis = trapezoid(np.clip(v * i, 0, None), t) / 3600.0
    e_cha = trapezoid(np.clip(-v * i, 0, None), t) / 3600.0
    return {
        "Cycle": cycle_number,
        "Charge [Ah]": q_cha, "Discharge [Ah]": q_dis,
        "Coulombic efficiency [%]": 100 * q_dis / q_cha if q_cha > 0 else np.nan,
        "Charge energy [Wh]": e_cha, "Discharge energy [Wh]": e_dis,
        "Energy efficiency [%]": 100 * e_dis / e_cha if e_cha > 0 else np.nan,
    }


def summarise(solution, has_ageing, ambient_c, chemistry, model_type):
    n_total = len(solution.cycles)          # includes conditioning cycle 0
    if n_total < 2:
        raise RuntimeError("The solver stopped during the first cycle. "
                           "Try lower C-rates or the DFN model.")
    retained = range(1, n_total)

    # --- capacity per cycle -------------------------------------------------
    if has_ageing:
        # Thermodynamic capacity (eSOH) is available for every cycle, even
        # those not saved, so the SOH trend has no gaps.
        cap_all = np.asarray(solution.summary_variables["Capacity [A.h]"], dtype=float)
        sei_all = np.asarray(
            solution.summary_variables["Loss of capacity to negative SEI [A.h]"], dtype=float)
        capacity = cap_all[1:n_total]
        sei_loss = sei_all[1:n_total]
    else:
        capacity = np.array([_discharge_capacity(solution.cycles[k]) for k in retained])
        sei_loss = np.full(len(capacity), np.nan)

    soh = 100.0 * capacity / capacity[0]   # reference = first retained cycle

    # --- saved cycles: temperatures, series, efficiency ---------------------
    max_temp = np.full(len(capacity), np.nan)
    mean_temp = np.full(len(capacity), np.nan)
    duration_h = np.full(len(capacity), np.nan)
    series, efficiency = [], []
    t0 = None
    for k in retained:
        cycle = solution.cycles[k]
        if cycle is None:                  # not saved (save_at_cycles)
            continue
        t = cycle["Time [s]"].entries
        v = cycle["Voltage [V]"].entries
        i = cycle["Current [A]"].entries
        temp = _cycle_temperature(cycle, has_ageing, ambient_c)
        max_temp[k - 1] = float(np.max(temp))
        mean_temp[k - 1] = trapezoid(temp, t) / (t[-1] - t[0])
        duration_h[k - 1] = (t[-1] - t[0]) / 3600.0
        efficiency.append(_efficiency_row(k, t, v, i))

        if t0 is None:
            t0 = t[0]
        idx = np.linspace(0, len(t) - 1, min(len(t), MAX_POINTS_PER_CYCLE)).astype(int)
        series.append(pd.DataFrame({
            "Cycle": k,
            "Time [min]": (t[idx] - t0) / 60.0,
            "Voltage [V]": v[idx],
            "Current [A]": i[idx],
            "Power [W]": v[idx] * i[idx],
            "Temperature [°C]": temp[idx],
        }))

    first_saved = next(solution.cycles[k] for k in retained if solution.cycles[k] is not None)
    last_saved = next(solution.cycles[k] for k in reversed(retained) if solution.cycles[k] is not None)

    cycles_df = pd.DataFrame({
        "Cycle": list(retained),
        "Capacity [Ah]": capacity,
        "SOH [%]": soh,
        "SEI capacity loss [Ah]": sei_loss,
        "Max temperature [°C]": max_temp,
        "Mean temperature [°C]": mean_temp,
        "Cycle duration [h]": duration_h,
        "Simulated": True,          # False for cycles added by run_long_term
    })
    meta = {
        "chemistry": chemistry,
        "model": "Sodium-ion BasicDFN (isothermal)" if not has_ageing else model_type,
        "has_ageing_physics": has_ageing,
        "cycles_completed": len(cycles_df),
        "cycles_simulated": len(cycles_df),
        "cell_capacity_ah": _discharge_capacity(first_saved),
        "cell_energy_wh": _discharge_energy_wh(first_saved),
    }
    return {
        "profile": cycle_profile(last_saved, has_ageing, ambient_c),
        "cycles": cycles_df,
        "series": pd.concat(series, ignore_index=True),
        "efficiency": pd.DataFrame(efficiency),
        "meta": meta,
    }




# ---------------------------------------------------------------------------
# 4. Battery test: physics for the first cycles, empirical ageing afterwards
# ---------------------------------------------------------------------------
DETAILED_CYCLES = 10        # cycles simulated in full with the physics model
PROJECTION_CYCLES = 20000   # horizon for "cycles until 80 %" and the economics
MIN_SOH = 50.0              # the ageing data do not go below this capacity [%]


def run_battery_test(chemistry, model_type="SPMe", c_charge=0.5, c_discharge=1.0,
                     n_cycles=1000, ambient_c=25.0, h_cooling=CALIBRATED_H_COOLING):
    """Simulate DETAILED_CYCLES cycles with PyBaMM, then predict capacity fade with the
    empirical model of the chemistry, using the simulated state of charge and cell
    temperature of the last full cycle.

    result["cycles"] stops at n_cycles; result["projection"] goes to PROJECTION_CYCLES.
    """
    result = run_simulation(chemistry, model_type, c_charge, c_discharge,
                            DETAILED_CYCLES, ambient_c, h_cooling)
    profile = result["profile"]
    q = predict_capacity(chemistry, profile["Time [s]"], profile["SOC"],
                         profile["Temperature [°C]"], PROJECTION_CYCLES)

    q = np.where(q >= MIN_SOH / 100, q, np.nan)   # no data below MIN_SOH: stop the curve
    cycles = np.arange(1, PROJECTION_CYCLES + 1)
    capacity = result["meta"]["cell_capacity_ah"] * q
    physics = result["cycles"].set_index("Cycle")
    projection = pd.DataFrame({
        "Cycle": cycles,
        "SOH [%]": 100.0 * q,
        "Capacity [Ah]": capacity,
        "Max temperature [°C]": physics["Max temperature [°C]"].reindex(cycles).to_numpy(),
    })
    below = projection.loc[projection["SOH [%]"] < 80.0, "Cycle"]
    dod = float(profile["SOC"].max() - profile["SOC"].min())
    mean_temp = trapezoid(profile["Temperature [°C]"].to_numpy(), profile["Time [s]"].to_numpy()) \
        / float(profile["Time [s]"].iloc[-1])

    result["projection"] = projection
    result["cycles"] = projection[projection["Cycle"] <= int(n_cycles)].reset_index(drop=True)
    result["physics_cycles"] = physics.reset_index()
    result["meta"].update({
        "cycles_completed": int(n_cycles),
        "cycles_to_80pct": float(below.iloc[0]) if len(below) else float("inf"),
        "mean_cell_temperature_c": mean_temp,
        "depth_of_discharge": dod,
        "cycle_duration_h": float(profile["Time [s]"].iloc[-1]) / 3600,
        "ageing_warnings": validity_warnings(chemistry, mean_temp, c_charge, c_discharge, dod,
                                              int(n_cycles)),
    })
    return result


def standard_profile(c_charge, c_discharge, rest_min=30):
    """A simple full cycle (CC discharge, CC charge, rests), used to compare
    chemistries under identical conditions without running the physics model."""
    t_dis, t_cha, rest = 3600 / c_discharge, 3600 / c_charge, rest_min * 60
    t = np.concatenate([np.linspace(0, t_dis, 30), t_dis + rest + np.linspace(0, t_cha, 30),
                        [t_dis + 2 * rest + t_cha]])
    soc = np.concatenate([np.linspace(1, 0, 30), np.linspace(0, 1, 30), [1.0]])
    return t, soc


def fit_sqrt_fade(cycles_df):
    """Fit SOH loss [%] = a * sqrt(cycle); used by the economics."""
    cycles_df = cycles_df.dropna(subset=["SOH [%]"])
    n = cycles_df["Cycle"].to_numpy(dtype=float)
    loss = 100.0 - cycles_df["SOH [%]"].to_numpy(dtype=float)
    return max(float(np.sum(loss * np.sqrt(n)) / np.sum(n)), 0.0)
