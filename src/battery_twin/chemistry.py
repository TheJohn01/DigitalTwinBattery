"""Battery chemistries and the electrochemical (physics) simulation.

Every other module reads chemistry data from the CHEMISTRIES table below.
The physics model (PyBaMM) simulates a few cycles in full: voltage, current, heat and
state of charge. Long-term capacity fade is then predicted by the empirical models in
ageing.py, driven by the operating conditions of those simulated cycles.
"""
import json

import numpy as np
import pandas as pd
import pybamm

from .ageing import (MIN_SOH, SodiumIon, add_rest, cut_at_data_end, cycles_to,
                     depth_and_discharge_rate, predict_capacity, validity_warnings)
from .constants import DATA_DIR
from .lfp_blade_params import MODEL_OPTIONS as LFP_BLADE_OPTIONS
from .lfp_blade_params import ageing_resistance as lfp_blade_ageing_resistance
from .lfp_blade_params import get_parameter_values as lfp_blade_parameter_values
from .nca_params import get_parameter_values as nca_parameter_values
from .sodium_ion_params import get_parameter_values as sodium_ion_parameter_values

# ---------------------------------------------------------------------------
# 0. NMC calibration result
# ---------------------------------------------------------------------------
# calibration.py fits the NMC model to measured LG M50T data (Kirkaldy et al., J. Power
# Sources 603 (2024) 234185) and writes calibration.json. The values are read from that
# file, so re-running the calibration only needs the new file copied into data/.
CALIBRATION_FILE = DATA_DIR / "calibration.json"
with open(CALIBRATION_FILE) as _f:
    CALIBRATION = json.load(_f)

# ---------------------------------------------------------------------------
# 1. Chemistry table
# ---------------------------------------------------------------------------
# eol_credit_kg_per_kg is an INDICATIVE ASSUMPTION, not measured data. Production GWP, water
# and ecotoxicity come from Degen et al. 2024 (environment.py); costs from NREL and
# BloombergNEF (economics.py).
# Capacity fade comes from empirical models fitted to measured data (ageing.py);
# "ageing_source" names the data behind each one.
# Uncalibrated Li-ion chemistries use the SEI activation energy from OKane 2022 (38 kJ/mol);
# their parameter sets use 0 J/mol, which would make SEI growth independent of temperature.
CHEMISTRIES = {
    "NMC": {
        "label": "NMC / Graphite (Chen 2020, LG M50 21700)",
        "family": "lithium_ion",
        "parameter_set": "Chen2020",
        "v_min": 2.5, "v_max": 4.2,
        # Calibrated values, read from data/calibration.json (see section 0)
        "updates": {
            "Initial concentration in negative electrode [mol.m-3]":
                CALIBRATION["initial_concentration_negative_mol_m3"],   # C/10 capacity 4.857 Ah
            "SEI solvent diffusivity [m2.s-1]":
                CALIBRATION["sei_solvent_diffusivity_m2_s"],            # default was 2.5e-22
            "SEI growth activation energy [J.mol-1]":
                CALIBRATION["sei_activation_energy_J_mol"],
        },
        "calibration": "Capacity, SEI growth and cooling calibrated to Kirkaldy et al. (2024), LG M50T",
        "ageing_source": "Calendar ageing from NREL BLAST-Lite (LG M50, Truong Bui et al. 2021); "
                         "cycling incl. fast-charge and cold-charge losses fitted to LG HG2 data "
                         "(Luh & Blank 2024; Preger et al. 2020; Wittman et al. 2023) and "
                         "Ohneseit et al. 2025",
        "eol_credit_kg_per_kg": 4.2,   # recycling credit (kg CO2eq avoided per kg)
        "wh_per_kg": 260.0,            # cell-level specific energy
    },
    "LFP": {
        "label": "LFP / Graphite (BYD Blade 135 Ah, Gorsch 2025)",
        "family": "lithium_ion",
        "parameter_set": "BYD-Blade",          # lfp_blade_params.py, commercial BEV cell
        "v_min": 2.6, "v_max": 3.65,
        # missing thermal/SEI values are borrowed from Chen2020, see build_model
        "updates": {"SEI growth activation energy [J.mol-1]": 38000.0},  # OKane 2022
        "model_options": LFP_BLADE_OPTIONS,    # LFP charge/discharge hysteresis
        "calibration": "Commercial BYD Blade BEV cell: geometry and capacity from the teardown "
                       "of Gorsch et al. (2025), LFP / graphite electrochemistry from Prada "
                       "2013, fitted to the Blade's measured pulse resistance. Checked against "
                       "BYD's 4680 LFP cell (Liu et al. 2025) and a 280 Ah LFP cell (Gray & "
                       "Vagg 2026)",
        "ageing_source": "Empirical model (NREL BLAST-Lite) fitted to Sony-Murata 3 Ah LFP data, "
                         "Naumann et al. 2018/2020; Gasper et al., J. Electrochem. Soc. 2022; "
                         "cycling term rescaled to Ohneseit et al. 2025 (21700 LFP), fast-charge "
                         "factor from Severson et al. 2019 (A123 LFP)",
        "eol_credit_kg_per_kg": 1.5,
        "wh_per_kg": 160.0,            # BYD Blade, 432 Wh / 2.7 kg (Gorsch et al. 2025)
    },
    "NCA": {
        "label": "NCA / Graphite-SiOx (Schmitt 2023, Samsung INR21700-50E)",
        "family": "lithium_ion",
        "parameter_set": "Schmitt2023",        # nca_params.py, commercial 4.9 Ah 21700
        "v_min": 2.5, "v_max": 4.2,
        "updates": {"SEI growth activation energy [J.mol-1]": 38000.0},  # OKane 2022
        "calibration": "Commercial Samsung INR21700-50E cell, parameterised by Schmitt et al. "
                       "(2023); checked here against their measured discharges at 0.04C, 0.5C "
                       "and 1C (capacity within 1 %, 16-24 mV RMSE)",
        "ageing_source": "Empirical model of the Panasonic NCR18650B: calendar ageing from NREL "
                         "BLAST-Lite (Keil et al. 2016), cycling refitted to Preger et al. 2020",
        "eol_credit_kg_per_kg": 4.2,
        "wh_per_kg": 255.7,            # Samsung INR21700-50E datasheet (Schmitt et al. 2023)
    },
    "Na-ion": {
        "label": "Sodium-ion: Hard carbon / layered oxide NFM (Schneider 2025, Mushang NA18650-1250)",
        "family": "sodium_ion",
        "parameter_set": "Schneider2025",      # sodium_ion_params.py, commercial 1.25 Ah 18650
        "v_min": 1.5, "v_max": 3.8,
        "updates": {},
        "calibration": "Commercial Mushang NA18650-1250 cell, parameterised and validated by "
                       "Schneider et al. (2025); checked here against their measured discharges "
                       "at C/100-5C (18-49 mV RMSE) and Rehm et al. (2025) efficiencies. Its "
                       "temperature dependence was measured at 10-40 °C; below 10 °C it is "
                       "extrapolated",
        "ageing_source": "Linear fade per cycle measured on commercial layered-oxide / hard-carbon "
                         "18650 cells: 0.05 %/cycle default from Liu et al., Applied Energy 2026 "
                         "(full cycles); 0.01 % for the best cells (Liu 2026; Carter et al., "
                         "Energies 2025)",
        "eol_credit_kg_per_kg": 1.0,
        "wh_per_kg": 105.0,            # 1.25 Ah x 3.0 V / 35.86 g (Schneider et al. 2025)
    },
}

# Cooling coefficient that reproduces the measured self-heating in Kirkaldy et al. (2024),
# rounded to a whole number for the dashboard slider.
CALIBRATED_H_COOLING = float(round(CALIBRATION["cooling_coefficient_W_m2K"]))

# Battery cooling options for the dashboard. h is an EFFECTIVE heat transfer coefficient
# over the whole cell surface (the lumped thermal model has one surface), so it is lower
# than the coolant-side values in textbooks: free convection of air 2-25, forced air 25-250,
# forced liquids 100-20,000 W/m2K (Incropera et al., Fundamentals of Heat and Mass Transfer,
# Table 1.1). The averages below are modelling assumptions within those ranges, not
# measurements of a specific pack.
# Pre-conditioning (liquid options): the thermal system holds the cells at
# PRECONDITION_C while they charge and discharge, warming them in cold weather and cooling
# them in hot weather. Between cycles the battery rests at the ambient temperature.
PRECONDITION_C = 25.0
COOLING_OPTIONS = {
    "Forced air / passive": {
        "h": 25.0, "preconditioned": False,
        "warning": "Average of passive (about 5-15 W/m²K) and forced-air (about 25-50 W/m²K) "
                   "cooling; the real value depends strongly on air speed and cell spacing. "
                   "No pre-conditioning: the cells charge at the ambient temperature, so cold "
                   "weather and fast charging age NMC much faster (lithium plating).",
    },
    "Liquid cold plate": {
        "h": 100.0, "preconditioned": True,
        "warning": "Effective value for the whole cell surface (about 50-200 W/m²K). Only part "
                   "of each cell touches the plate, through a thermal interface material, so "
                   "the value depends heavily on the pack design. Pre-conditioning assumed: "
                   f"cells are held at {PRECONDITION_C:.0f} °C while cycling and rest at the "
                   "ambient temperature between cycles.",
    },
    "Immersion cooling": {
        "h": 300.0, "preconditioned": True,
        "warning": "Effective value (about 100-1,000 W/m²K, depending on the fluid and how fast "
                   "it flows); few measurements on complete packs are published. Pre-conditioning "
                   f"assumed: cells are held at {PRECONDITION_C:.0f} °C while cycling and rest "
                   "at the ambient temperature between cycles.",
    },
}


def cooling_conditions(cooling, ambient_c):
    """(h in W/m2K, temperature around the cells while cycling) for a cooling option."""
    option = COOLING_OPTIONS[cooling]
    cycling_c = PRECONDITION_C if option["preconditioned"] else float(ambient_c)
    return option["h"], cycling_c


def is_sodium(chemistry):
    return CHEMISTRIES[chemistry]["family"] == "sodium_ion"


DFN_ABOVE_C_CHARGE = 2.0     # charging faster than this always uses the detailed model


def choose_model(chemistry, c_charge, detailed=False):
    """"DFN" (detailed) or "SPMe". Sodium-ion only has a DFN model in PyBaMM."""
    if detailed or c_charge > DFN_ABOVE_C_CHARGE or is_sodium(chemistry):
        return "DFN"
    return "SPMe"


MAX_POINTS_PER_CYCLE = 200   # downsampling of the time series for plots/export
MAX_SAVED_CYCLES = 50        # full data kept for at most ~50 cycles


def trapezoid(y, x):
    return float(np.trapezoid(y, x))


# ---------------------------------------------------------------------------
# 2. Model building
# ---------------------------------------------------------------------------
def build_model(chemistry, model_type="SPMe", ambient_c=25.0, h_cooling=CALIBRATED_H_COOLING,
                area_scale=1.0):
    """Return (model, parameter_values, has_sei). Every model has a lumped thermal model.

    area_scale < 1 makes an aged cell (see run_aged_window): the electrode area shrinks,
    so the capacity falls by that factor and, at the same current, the resistance rises."""
    c = CHEMISTRIES[chemistry]
    sodium = is_sodium(chemistry)
    if sodium:
        # Commercial sodium-ion cell (Schneider et al. 2025), a complete parameter set
        pv = pybamm.ParameterValues(sodium_ion_parameter_values())
    else:
        if c["parameter_set"] == "Schmitt2023":      # commercial NCA cell (nca_params.py)
            pv = pybamm.ParameterValues(nca_parameter_values())
        elif c["parameter_set"] == "BYD-Blade":      # commercial LFP cell (lfp_blade_params.py)
            pv = pybamm.ParameterValues(lfp_blade_parameter_values())
        else:
            pv = pybamm.ParameterValues(c["parameter_set"])
        # Fill ONLY missing parameters (e.g. thermal/SEI values) from Chen2020.
        # Existing values of the chosen parameter set are never overwritten.
        donor = pybamm.ParameterValues("Chen2020")
        existing = set(pv.keys())
        pv.update({k: donor[k] for k in donor.keys() if k not in existing},
                  check_already_exists=False)
    pv.update({"Total heat transfer coefficient [W.m-2.K-1]": float(h_cooling)},
              check_already_exists=False)

    temp_k = float(ambient_c) + 273.15
    pv.update({"Ambient temperature [K]": temp_k, "Initial temperature [K]": temp_k},
              check_already_exists=False)
    pv.update(c["updates"], check_already_exists=False)
    pv.update({"Electrode width [m]": pv["Electrode width [m]"] * area_scale})
    if c["parameter_set"] == "BYD-Blade" and area_scale < 1:     # measured ohmic growth
        pv.update({"Contact resistance [Ohm]": pv["Contact resistance [Ohm]"]
                   + lfp_blade_ageing_resistance(area_scale)})
    # "Reference temperature [K]" is deliberately NOT changed.

    if sodium:
        # PyBaMM's lithium-ion DFN equations hold for sodium ions too (Schneider et al. used
        # them in PyBaMM). No SEI model: sodium-ion ageing comes from the empirical model.
        return pybamm.lithium_ion.DFN({"thermal": "lumped"}), pv, False

    options = {"thermal": "lumped", "SEI": "solvent-diffusion limited"}
    options.update(c.get("model_options", {}))
    if pv["Contact resistance [Ohm]"] > 0:           # measured ohmic resistance (NCA)
        options["contact resistance"] = "true"
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
                   n_cycles=10, ambient_c=25.0, h_cooling=CALIBRATED_H_COOLING, area_scale=1.0):
    """Run the simulation and return plain DataFrames (easy to cache/export).

    Raises an exception if the solver fails. There is no synthetic fallback.
    """
    model, pv, has_sei = build_model(chemistry, model_type, ambient_c, h_cooling, area_scale)
    experiment = build_experiment(chemistry, c_charge, c_discharge, n_cycles)
    save_every = max(1, int(n_cycles) // MAX_SAVED_CYCLES)
    n_steps = len(experiment.cycles[0])

    # Sodium-ion: if the solver stops early (charging in the cold, see mesh_settings), try the
    # next particle mesh. Lithium chemistries are solved once, with PyBaMM's default mesh.
    stretches = SODIUM_MESH_STRETCHES if is_sodium(chemistry) else [None]
    for stretch in stretches:
        sim = pybamm.Simulation(model, parameter_values=pv, experiment=experiment,
                                **mesh_settings(model, stretch))
        if save_every > 1:
            solution = sim.solve(save_at_cycles=save_every)
        else:
            solution = sim.solve()
        complete = (len(solution.cycles) == int(n_cycles) + 1
                    and len(solution.cycles[-1].steps) == n_steps)
        if complete:
            break
    # PyBaMM returns what it solved when the solver fails (or runs out of memory) mid-run
    if not complete and is_sodium(chemistry):
        raise RuntimeError(
            "The sodium-ion simulation stopped before the last cycle: the hard-carbon anode "
            "surface fills up during charging, which happens when charging fast in the cold "
            "(where real cells risk sodium plating). Try a lower charge rate, a warmer "
            "temperature or pre-conditioned cooling.")
    if not complete:
        raise RuntimeError(
            f"The simulation stopped after {len(solution.cycles) - 1} of {int(n_cycles)} cycles "
            "(the solver failed or ran out of memory). Try a lower charge or discharge rate, a "
            "warmer temperature or pre-conditioned cooling.")

    return summarise(solution, has_sei, ambient_c, chemistry, model_type)


# Particle meshes tried in turn for sodium-ion: exponential spacing with these stretch
# factors (None = PyBaMM's uniform default). Each one alone fails in a few cold-charging
# cases (0-10 °C); in a test of 40 cases from -10 to 45 °C and 0.3C to 3C, every case was
# solved by one of them.
SODIUM_MESH_STRETCHES = [2.0, None, 2.5, 1.5]


def mesh_settings(model, stretch):
    """Particle mesh. The sodium-ion diffusivities change by up to three decades with the
    state of charge, which gives steep gradients at the particle surface, so (as in
    Schneider et al. 2025) the radial mesh is refined towards the surface: exponential
    spacing with the given stretch factor. stretch=None keeps PyBaMM's default."""
    if stretch is None:
        return {}
    submesh = dict(model.default_submesh_types)
    for domain in ("negative particle", "positive particle"):
        submesh[domain] = pybamm.MeshGenerator(pybamm.Exponential1DSubMesh,
                                               submesh_params={"side": "right", "stretch": stretch})
    return {"submesh_types": submesh}


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


def _cycle_temperature(cycle):
    return cycle["X-averaged cell temperature [C]"].entries


def cycle_profile(cycle):
    """Time, state of charge and cell temperature of one cycle: the operating
    conditions handed to the empirical ageing model."""
    t = cycle["Time [s]"].entries
    i = cycle["Current [A]"].entries                      # + = discharge
    temp = _cycle_temperature(cycle)
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


def summarise(solution, has_sei, ambient_c, chemistry, model_type):
    n_total = len(solution.cycles)          # includes conditioning cycle 0
    if n_total < 2:
        raise RuntimeError("The solver stopped during the first cycle. "
                           "Try lower C-rates or the DFN model.")
    retained = range(1, n_total)

    # --- capacity per cycle -------------------------------------------------
    if has_sei:
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
        temp = _cycle_temperature(cycle)
        max_temp[k - 1] = float(np.max(temp))
        mean_temp[k - 1] = trapezoid(temp, t) / (t[-1] - t[0])
        duration_h[k - 1] = (t[-1] - t[0]) / 3600.0
        efficiency.append(_efficiency_row(k, t, v, i))

        if t0 is None:
            t0 = t[0]
        # evenly spaced in time (solver points are sparse in constant-current steps)
        tu = np.linspace(t[0], t[-1], MAX_POINTS_PER_CYCLE)
        vu, iu = np.interp(tu, t, v), np.interp(tu, t, i)
        series.append(pd.DataFrame({
            "Cycle": k,
            "Time [min]": (tu - t0) / 60.0,
            "Voltage [V]": vu,
            "Current [A]": iu,
            "Power [W]": vu * iu,
            "Temperature [°C]": np.interp(tu, t, temp),
            # the open-circuit voltage a battery management system would know (for the estimator)
            "Open-circuit voltage [V]": np.interp(
                tu, t, cycle["Battery open-circuit voltage [V]"].entries),
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
    })
    meta = {
        "chemistry": chemistry,
        "model": model_type if has_sei else f"{model_type} (no SEI physics)",
        "has_ageing_physics": has_sei,
        "cycles_completed": len(cycles_df),
        "cell_capacity_ah": _discharge_capacity(first_saved),
        "cell_energy_wh": _discharge_energy_wh(first_saved),
    }
    return {
        "profile": cycle_profile(last_saved),
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
RANGE_TEMP_C = 5.0          # range band for lithium chemistries: cell temperature ± this
# Default battery test (also the dashboard's defaults): inside the measured ageing data
# for NMC, LFP and NCA.
DEFAULT_C_CHARGE, DEFAULT_C_DISCHARGE, DEFAULT_AMBIENT_C = 0.3, 1.0, 20.0


def run_battery_test(chemistry, model_type="SPMe", c_charge=DEFAULT_C_CHARGE,
                     c_discharge=DEFAULT_C_DISCHARGE, n_cycles=1000,
                     ambient_c=DEFAULT_AMBIENT_C, h_cooling=CALIBRATED_H_COOLING,
                     na_fade_per_efc=SodiumIon.FADE_PER_EFC, cycles_per_year=365,
                     cycling_c=None, aged_windows=False):
    """Simulate DETAILED_CYCLES cycles with PyBaMM, then predict capacity fade with the
    empirical model of the chemistry, using the simulated state of charge and cell
    temperature of the last full cycle. na_fade_per_efc is only used for sodium-ion.

    cycles_per_year sets how much real time each cycle takes: the simulated cycle is
    followed by a rest (see ageing.add_rest), so calendar ageing is counted correctly.

    result["cycles"] stops at n_cycles; result["projection"] goes to PROJECTION_CYCLES.

    cycling_c is the temperature around the cells while they cycle (the coolant
    temperature with pre-conditioning); None means the ambient temperature. The rest
    between cycles is always at ambient_c.

    aged_windows=True also simulates the middle and last DETAILED_CYCLES cycles of the
    n_cycles chosen (see run_aged_window); the result is in result["windows"].
    """
    if cycling_c is None:
        cycling_c = ambient_c
    result = run_simulation(chemistry, model_type, c_charge, c_discharge,
                            DETAILED_CYCLES, cycling_c, h_cooling)
    profile = result["profile"]
    t, soc, temp, cycles_per_year_used = add_rest(
        profile["Time [s]"], profile["SOC"], profile["Temperature [°C]"],
        cycles_per_year, ambient_c)
    q = predict_capacity(chemistry, t, soc, temp, PROJECTION_CYCLES, na_fade_per_efc)

    # Range band: the same prediction for a cooler and a hotter cell (lithium), or for the
    # best and worst measured commercial cells (sodium-ion). It shows how much the result
    # depends on an uncertain input; it is not a statistical confidence interval.
    sodium = is_sodium(chemistry)
    if sodium:
        na_rates = (min(na_fade_per_efc, SodiumIon.FADE_PER_EFC_BEST),
                    max(na_fade_per_efc, SodiumIon.FADE_PER_EFC))
        variants = [predict_capacity(chemistry, t, soc, temp, PROJECTION_CYCLES, rate)
                    for rate in na_rates]
        range_basis = (f"sodium-ion loss of {100 * na_rates[0]:.2f}–{100 * na_rates[1]:.2f} "
                       "% per cycle")
    else:
        variants = [predict_capacity(chemistry, t, soc, temp + dt, PROJECTION_CYCLES)
                    for dt in (-RANGE_TEMP_C, RANGE_TEMP_C)]
        range_basis = f"cell temperature ±{RANGE_TEMP_C:.0f} °C"
    q_low = np.minimum.reduce([q] + variants)
    q_high = np.maximum.reduce([q] + variants)

    q, q_low, q_high = cut_at_data_end(q), cut_at_data_end(q_low), cut_at_data_end(q_high)
    cycles = np.arange(1, PROJECTION_CYCLES + 1)
    capacity = result["meta"]["cell_capacity_ah"] * q
    physics = result["cycles"].set_index("Cycle")
    projection = pd.DataFrame({
        "Cycle": cycles,
        "SOH [%]": 100.0 * q,
        "SOH low [%]": 100.0 * q_low,
        "SOH high [%]": 100.0 * q_high,
        "Capacity [Ah]": capacity,
        "Max temperature [°C]": physics["Max temperature [°C]"].reindex(cycles).to_numpy(),
    })
    dod, _ = depth_and_discharge_rate(profile["Time [s]"], profile["SOC"])
    # mean cell temperature of the last simulated cycle (full resolution, from summarise)
    mean_temp = float(physics["Mean temperature [°C]"].dropna().iloc[-1])

    result["projection"] = projection
    result["ageing_cycle"] = (t, soc, temp)      # the repeating cycle, for the second life
    if aged_windows:
        result["windows"] = cycle_windows(result, q, int(n_cycles), chemistry, model_type,
                                          c_charge, c_discharge, cycling_c, h_cooling)
    result["cycles"] = projection[projection["Cycle"] <= int(n_cycles)].reset_index(drop=True)
    result["meta"].update({
        "cycles_completed": int(n_cycles),
        "cycles_to_80pct": cycles_to(q, 0.8),
        "cycles_to_80pct_range": (cycles_to(q_low, 0.8), cycles_to(q_high, 0.8)),
        "range_basis": range_basis,
        # first cycle below MIN_SOH, where the ageing data end (q is NaN from there)
        "cycles_to_data_end": cycles_to(q, MIN_SOH / 100),
        "h_cooling": float(h_cooling),
        "cycling_c": float(cycling_c),
        "mean_cell_temperature_c": mean_temp,
        "depth_of_discharge": dod,
        "cycle_duration_h": float(profile["Time [s]"].iloc[-1]) / 3600,
        "cycles_per_year": cycles_per_year_used,     # lower than asked if cycles are too long
        "ageing_warnings": validity_warnings(chemistry, mean_temp, c_charge, c_discharge, dod,
                                              int(n_cycles)),
    })
    return result


def run_aged_window(chemistry, model_type, c_charge, c_discharge, cycling_c, h_cooling, soh):
    """Simulate DETAILED_CYCLES cycles of a cell that has aged to capacity fraction soh.

    Simple approximation: the aged cell is the new cell with its electrode area scaled by
    soh (loss of active material). Its capacity falls to soh and, because the current for
    a given C-rate stays that of the new cell, the current per electrode area and so the
    resistance rise by 1/soh (e.g. +25 % at 80 % capacity; Ohneseit et al. 2025 measured
    roughly +10 to +50 % ohmic resistance growth to 80 %). Real ageing also changes the
    electrode balance and the SEI, which this does not capture."""
    return run_simulation(chemistry, model_type, c_charge, c_discharge, DETAILED_CYCLES,
                          cycling_c, h_cooling, area_scale=float(soh))


def cycle_windows(result, q, n_cycles, chemistry, model_type, c_charge, c_discharge,
                  cycling_c, h_cooling):
    """Voltage and temperature of the first, middle and last DETAILED_CYCLES cycles.

    The first window is the normal simulation. The middle and last windows are simulated
    with run_aged_window at the capacity the ageing model predicts at their first cycle.
    A window is left out if it overlaps an earlier one or if the capacity there is below
    MIN_SOH (no data)."""
    n = DETAILED_CYCLES
    starts = {"First": 1, "Middle": max(1, n_cycles // 2 - n // 2 + 1),
              "Last": max(1, n_cycles - n + 1)}
    frames, rows, used = [], [], []
    for name, start in starts.items():
        if any(abs(start - u) < n for u in used):
            continue                                 # overlaps an earlier window
        soh = 1.0 if name == "First" else float(q[start - 1])
        if not np.isfinite(soh):                     # q is NaN below MIN_SOH
            rows.append({"Window": name, "Cycles": f"{start}–{start + n - 1}",
                         "Capacity used [%]": np.nan, "Note": "below the ageing data"})
            continue
        res = result if name == "First" else run_aged_window(
            chemistry, model_type, c_charge, c_discharge, cycling_c, h_cooling, soh)
        series = res["series"].copy()
        series["Time [h]"] = (series["Time [min]"] - series["Time [min]"].iloc[0]) / 60
        series["Cycle"] = series["Cycle"] + start - 1
        label = f"{name}: cycles {start}–{start + n - 1}"
        series["Window"] = label
        frames.append(series)
        temp = series["Temperature [°C]"]
        eff = res["efficiency"]
        rows.append({"Window": name, "Cycles": f"{start}–{start + n - 1}",
                     "Capacity used [%]": 100 * soh,
                     "Discharge capacity [Ah]": float(eff["Discharge [Ah]"].mean()),
                     "Energy efficiency [%]": float(eff["Energy efficiency [%]"].mean()),
                     "Max temperature [°C]": float(temp.max()),
                     "Mean temperature [°C]": float(temp.mean()),
                     "Note": "simulated" if name == "First" else "aged cell, simulated"})
        used.append(start)
    return {"series": pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(),
            "summary": pd.DataFrame(rows)}


def standard_profile(c_charge, c_discharge, rest_min=30):
    """A simple full cycle (CC discharge, CC charge, rests), used to compare
    chemistries under identical conditions without running the physics model."""
    t_dis, t_cha, rest = 3600 / c_discharge, 3600 / c_charge, rest_min * 60
    t = np.concatenate([np.linspace(0, t_dis, 30), t_dis + rest + np.linspace(0, t_cha, 30),
                        [t_dis + 2 * rest + t_cha]])
    soc = np.concatenate([np.linspace(1, 0, 30), np.linspace(0, 1, 30), [1.0]])
    return t, soc
