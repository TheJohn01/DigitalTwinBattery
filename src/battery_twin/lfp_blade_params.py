"""PyBaMM parameter set for a commercial BEV LFP cell: the BYD Blade (prismatic, 135 Ah).

The cell geometry comes from a teardown of the cell. No paper measures the electrode
properties of the Blade, so the electrochemistry starts from PyBaMM's Prada2013 LFP /
graphite set and three values are fitted to measurements of LFP / graphite cells (below).

Geometry: Gorsch J. et al. (2025). Contrasting a BYD Blade prismatic cell and Tesla 4680
cylindrical cell with a teardown analysis of design and performance. Cell Rep. Phys. Sci. 6,
102453. https://doi.org/10.1016/j.xcrp.2025.102453 (CC BY 4.0), Table 1 and text:
- 135 Ah, 432 Wh, 2.6-3.65 V (C/10 CC-CV), 2.7 kg, 1,216 mL, 965 x 90 x 14 mm.
- 38 double-coated cathode sheets, 39 double-coated anode sheets, Z-folded separator.
- Coatings 70 um (cathode) and 65 um (anode) per side; foils Al 20 um, Cu 10 um;
  separator 12 um; cathode areal capacity 2.393 mAh/cm2 (capacity / coated cathode area).
- Anode active material 1.35 kg per kWh, i.e. 0.583 kg of graphite.

Derived here (see the functions below):
- Electrode area = 135 Ah / 2.393 mAh/cm2 = 5.64 m2 (all cathode sides).
- Cathode active fraction from the capacity, assuming the LFP delivers 91 % of its
  theoretical capacity (528 Wh/kg at about 3.4 V, the value Gorsch et al. quote for LFP,
  is 155 of 170 mAh/g).
- Anode active fraction from the graphite mass (graphite density 2,260 kg/m3) over the
  anode coating (78 sides, 1 mm overhang on each edge).
- The lithium inventory and the stoichiometry at 100 % SOC: PyBaMM's electrode-balance
  solver, set so that the capacity between the voltage limits is the measured one.

Electrochemistry:
- LFP: Prada2013 (Afshar 2017 OCP, Kashkooli 2017 kinetics, 50 nm particles; the BYD LFP
  particles are 100-300 nm across, Liu et al. 2025).
- Graphite: OCP of Mohtat et al. (2020, J. Electrochem. Soc. 167, 110561), a pure graphite
  whose steps match a measured LFP / graphite OCV best of the graphite OCPs PyBaMM ships;
  kinetics of Chen et al. (2020), as in Prada2013; 5 um particle radius (flakes up to 10 um
  across, Liu et al. 2025).
- Fitted by scripts/fit_blade.py, one value per measurement:
  1. LFP_OCP_SHIFT: the Afshar LFP OCP sits too low; shifted so the cell OCV matches the
     measured pseudo-OCV of a commercial 280 Ah LFP / graphite cell (Gray & Vagg 2026).
  2. GRAPHITE_J0_SCALE: the charge-transfer resistance of the BYD 4680 LFP cell, 5.9 Ohm cm2
     from impedance at 20 % SOC (Liu et al. 2025).
  3. LFP_HYSTERESIS: LFP / graphite cells charge at a higher voltage than they discharge,
     even slowly (Gray & Vagg's cell: charge and discharge curves 94 mV apart at C/10, of
     which their measured resistance explains about 31 mV). PyBaMM's "one-state
     hysteresis" option (Börjesson Axén et al. 2022, J. Energy Storage 48, 103985) moves the LFP OCP between lfp_ocp +
     LFP_HYSTERESIS (charging) and lfp_ocp - LFP_HYSTERESIS (discharging) as charge passes,
     so a short pulse barely changes it; HYSTERESIS_DECAY (assumed) makes the switch take
     about 5 % of the capacity. MODEL_OPTIONS must be used with this parameter set.
  4. GRAPHITE_DIFFUSIVITY: the rate test of the same cell (1C and 2C capacity relative to C/2).

Assumptions (not measured for this cell):
- Cathode porosity 0.30 (binder, carbon and carbon coating then fill 8.5 % of the volume);
  anode binder fraction 0.06 as in Prada2013; separator porosity 0.45 as in Prada2013.
- Electrolyte: 1.2 M LiPF6 in EC:EMC 3:7 (the electrolyte Prada2013 names), with the
  temperature-dependent fits of Landesfeind & Gasteiger (2019) that PyBaMM ships, because
  the Prada2013 conductivity has no temperature dependence.
- Entropic heat: the full-cell entropy coefficient measured on a 280 Ah LFP storage cell
  (Gray & Vagg 2026, Zenodo doi:10.5281/zenodo.20813753, CC BY 4.0) at 10-90 % SOC; LFP /
  graphite cells share it because it comes mainly from the graphite. Prada2013 has none.
- Thermal properties of the layers come from Chen2020 (filled in by chemistry.build_model).

A second geometry, the BYD 4680 LFP cell (15 Ah) of Liu et al. (2025, J. Electrochem. Soc.
172, 110536), uses the same recipe. It is only used by scripts/fit_blade.py and scripts/validate_blade.py,
to fit and check the model against that paper's rate tests and pulse resistances (none are
published for the Blade).
"""
import warnings
from functools import lru_cache

import numpy as np
import pybamm
from pybamm.input.parameters.lithium_ion.Mohtat2020 import graphite_ocp_PeymanMPM
from pybamm.input.parameters.lithium_ion.ORegan2022 import (
    electrolyte_conductivity_EC_EMC_3_7_Landesfeind2019,
    electrolyte_diffusivity_EC_EMC_3_7_Landesfeind2019, electrolyte_TDF_EC_EMC_3_7_Landesfeind2019,
    electrolyte_transference_number_EC_EMC_3_7_Landesfeind2019)
from pybamm.input.parameters.lithium_ion.Prada2013 import (
    LFP_ocp_Afshar2017, graphite_LGM50_electrolyte_exchange_current_density_Chen2020)

# PyBaMM warns at every build of a hysteresis model that the decay-rate definition changed in
# v25.10; HYSTERESIS_DECAY below is set for the new definition.
warnings.filterwarnings("ignore", message="The definition of the hysteresis decay rate")

F_CONST = 96485.33
T_REF = 298.15
C_MAX_POS = 22806.0          # mol/m3, Prada2013 (LFP)
C_MAX_NEG = 30555.0          # mol/m3, Prada2013 (graphite)
LFP_UTILISATION = 155 / 170  # usable / theoretical LFP capacity (see module docstring)
GRAPHITE_UTILISATION = 0.95  # usable / theoretical graphite capacity (assumed, about 355 of 372 mAh/g)
GRAPHITE_DENSITY = 2260.0    # kg/m3
CATHODE_POROSITY = 0.30      # assumption
# fitted by scripts/fit_blade.py (see module docstring)
LFP_OCP_SHIFT = 0.0283           # V, added to the Afshar LFP OCP
GRAPHITE_J0_SCALE = 10.1         # x Chen 2020 graphite exchange current (includes surface area)
LFP_HYSTERESIS = 0.0314          # V, half the gap between charge and discharge OCP
GRAPHITE_DIFFUSIVITY = 5.78e-15  # m2/s (Prada2013: 3e-15)
HYSTERESIS_DECAY = 100.0         # assumed: 90 % of the switch within about 5 % of the LFP capacity
MODEL_OPTIONS = {"open-circuit potential": ("single", "one-state hysteresis")}   # LFP only
ANODE_INACTIVE = 0.06        # binder volume fraction of the anode, Prada2013 (1 - 0.58 - 0.36)

# Full-cell entropy coefficient dU/dT [V/K] vs SOC, Gray & Vagg 2026 (LIC_entropy_analysis.csv)
ENTROPY_SOC = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
ENTROPY_V_K = np.array([-9.79e-5, -2.73e-5, 1.54e-4, 9.75e-7, 2.01e-5])

CELLS = {
    # Gorsch et al. 2025 (see module docstring)
    "Blade": {
        "capacity_ah": 135.0, "v_min": 2.6, "v_max": 3.65,
        "cathode_ah_per_m2": 23.93,              # 2.393 mAh/cm2
        "electrode_height_m": 0.086,             # assumed (cell 90 mm); only the area matters
        "cathode_um": 70.0, "anode_um": 65.0, "separator_um": 12.0,
        "al_um": 20.0, "cu_um": 10.0,
        "graphite_kg": 1.35 * 0.432,             # 1.35 kg/kWh x 432 Wh
        "anode_sides": 78, "cathode_sides": 76, "overhang_m": 0.001,
        "cell_volume_m3": 1.216e-3,
        "cooling_area_m2": 2 * (0.965 * 0.090 + 0.965 * 0.014 + 0.090 * 0.014),
    },
    # Liu et al. 2025, BYD 4680 LFP: C/5 capacity 15.41 Ah (2.8-3.65 V), cathode roll
    # 69 x 5,370 mm, coatings 70 um ((150 - 10) / 2) and 54.5 um per side, foils 10 um,
    # areal capacities 2.09 (LFP) and 2.34 (graphite) mAh/cm2 per side in half cells.
    "BYD4680": {
        "capacity_ah": 15.41, "v_min": 2.8, "v_max": 3.65,
        "cathode_ah_per_m2": 15.41 / (2 * 0.069 * 5.370),
        "electrode_height_m": 0.069,
        "cathode_um": 70.0, "anode_um": 54.5, "separator_um": 12.0,   # separator as Blade
        "al_um": 10.0, "cu_um": 10.0,
        "anode_ah_per_m2": 23.4,                 # 2.34 mAh/cm2, graphite half cell
        "cell_volume_m3": np.pi * 0.023 ** 2 * 0.080,
        "cooling_area_m2": np.pi * 0.046 * 0.080 + 2 * np.pi * 0.023 ** 2,
    },
}


def lfp_ocp(sto):
    """Mean of the charge and discharge OCP."""
    return LFP_ocp_Afshar2017(sto) + LFP_OCP_SHIFT


def lfp_ocp_charge(sto):          # LFP delithiation (cell charging)
    return lfp_ocp(sto) + LFP_HYSTERESIS


def lfp_ocp_discharge(sto):       # LFP lithiation (cell discharging)
    return lfp_ocp(sto) - LFP_HYSTERESIS


def graphite_exchange_current(c_e, c_s_surf, c_s_max, T):
    return GRAPHITE_J0_SCALE * graphite_LGM50_electrolyte_exchange_current_density_Chen2020(
        c_e, c_s_surf, c_s_max, T)


def electrode_fractions(cell):
    """(electrode area [m2], cathode and anode active-material volume fractions)."""
    g = CELLS[cell]
    area = g["capacity_ah"] / g["cathode_ah_per_m2"]
    lp, ln = g["cathode_um"] * 1e-6, g["anode_um"] * 1e-6
    lfp_ah_per_m3 = C_MAX_POS * F_CONST / 3600            # theoretical, full electrode volume
    eps_p = g["cathode_ah_per_m2"] / (LFP_UTILISATION * lfp_ah_per_m3 * lp)
    if "graphite_kg" in g:
        # graphite mass over the anode coating: every side is a little larger (overhang)
        side = area / g["cathode_sides"]
        h = g["electrode_height_m"]
        w = side / h
        anode_area = g["anode_sides"] * (h + 2 * g["overhang_m"]) * (w + 2 * g["overhang_m"])
        eps_n = g["graphite_kg"] / anode_area / (GRAPHITE_DENSITY * ln)
    else:
        # measured graphite half-cell capacity
        graphite_ah_per_m3 = C_MAX_NEG * F_CONST / 3600
        eps_n = g["anode_ah_per_m2"] / (GRAPHITE_UTILISATION * graphite_ah_per_m3 * ln)
    return area, eps_p, eps_n


def _entropic_change(y_full, y_empty):
    """Full-cell dU/dT of Gray & Vagg as a function of the LFP stoichiometry. SOC runs
    linearly from 1 at y_full to 0 at y_empty; outside 10-90 % SOC it is held constant."""
    sto_points = y_empty - ENTROPY_SOC * (y_empty - y_full)     # descending
    x, y = sto_points[::-1], ENTROPY_V_K[::-1]

    def entropic_change(sto, *args):     # PyBaMM passes sto (and c_s_max in some versions)
        sto = pybamm.maximum(pybamm.minimum(sto, float(x.max())), float(x.min()))
        return pybamm.Interpolant(x, y, sto, name="LFP_entropy_GrayVagg2026")
    return entropic_change


def get_parameter_values(cell="Blade"):
    """Parameter values of the BYD Blade (default) or the BYD 4680. Missing thermal and SEI
    values are filled in from Chen2020 by chemistry.build_model."""
    values = _base_values(cell)
    x_0, x_100, y_0, y_100 = electrode_balance(cell)
    values.update({
        "Initial concentration in negative electrode [mol.m-3]": x_100 * C_MAX_NEG,
        "Initial concentration in positive electrode [mol.m-3]": y_100 * C_MAX_POS,
        "Positive electrode OCP entropic change [V.K-1]": _entropic_change(y_100, y_0),
        "Positive electrode lithiation OCP [V]": lfp_ocp_discharge,
        "Positive electrode delithiation OCP [V]": lfp_ocp_charge,
        "Positive particle lithiation hysteresis decay rate": HYSTERESIS_DECAY,
        "Positive particle delithiation hysteresis decay rate": HYSTERESIS_DECAY,
        "Initial hysteresis state in positive electrode": 1.0,   # full cell: charge branch
        "Negative electrode OCP entropic change [V.K-1]": 0.0,
    })
    return values


def clear_cache():
    """Call after changing a module constant (scripts/fit_blade.py does)."""
    electrode_balance.cache_clear()


def _base_values(cell):
    """Everything except the state of charge (initial concentrations)."""
    g = CELLS[cell]
    area, eps_p, eps_n = electrode_fractions(cell)
    prada = pybamm.ParameterValues("Prada2013")
    h = g["electrode_height_m"]
    values = {
        "chemistry": "lithium_ion",
        "Nominal cell capacity [A.h]": g["capacity_ah"],
        "Current function [A]": g["capacity_ah"],
        "Lower voltage cut-off [V]": g["v_min"],
        "Upper voltage cut-off [V]": g["v_max"],
        "Open-circuit voltage at 0% SOC [V]": g["v_min"],
        "Open-circuit voltage at 100% SOC [V]": g["v_max"],
        "Number of electrodes connected in parallel to make a cell": 1.0,
        "Number of cells connected in series to make a battery": 1.0,
        "Electrode height [m]": h,
        "Electrode width [m]": area / h,
        "Cell volume [m3]": g["cell_volume_m3"],
        "Cell cooling surface area [m2]": g["cooling_area_m2"],
        "Contact resistance [Ohm]": 0.0,
        "Reference temperature [K]": T_REF,
        "Ambient temperature [K]": T_REF,
        "Initial temperature [K]": T_REF,
        "Negative current collector thickness [m]": g["cu_um"] * 1e-6,
        "Positive current collector thickness [m]": g["al_um"] * 1e-6,
        # geometry and loading (Gorsch / Liu)
        "Negative electrode thickness [m]": g["anode_um"] * 1e-6,
        "Positive electrode thickness [m]": g["cathode_um"] * 1e-6,
        "Separator thickness [m]": g["separator_um"] * 1e-6,
        "Negative electrode active material volume fraction": eps_n,
        "Positive electrode active material volume fraction": eps_p,
        "Negative electrode porosity": 1 - eps_n - ANODE_INACTIVE,
        "Positive electrode porosity": CATHODE_POROSITY,
        "Maximum concentration in negative electrode [mol.m-3]": C_MAX_NEG,
        "Maximum concentration in positive electrode [mol.m-3]": C_MAX_POS,
        "Negative particle diffusivity [m2.s-1]": GRAPHITE_DIFFUSIVITY,
        "Negative electrode OCP [V]": graphite_ocp_PeymanMPM,
        "Negative electrode exchange-current density [A.m-2]": graphite_exchange_current,
        "Positive electrode OCP [V]": lfp_ocp,
        # electrolyte: Landesfeind & Gasteiger 2019, EC:EMC 3:7, 1.2 M as in Prada2013
        "Initial concentration in electrolyte [mol.m-3]": 1200.0,
        "Electrolyte conductivity [S.m-1]": electrolyte_conductivity_EC_EMC_3_7_Landesfeind2019,
        "Electrolyte diffusivity [m2.s-1]": electrolyte_diffusivity_EC_EMC_3_7_Landesfeind2019,
        "Cation transference number": electrolyte_transference_number_EC_EMC_3_7_Landesfeind2019,
        "Thermodynamic factor": electrolyte_TDF_EC_EMC_3_7_Landesfeind2019,
    }
    # the rest from Prada2013 (LFP diffusion and kinetics, conductivities, particle radii,
    # Bruggeman, separator porosity, double layer)
    for key in prada.keys():
        if key not in values and key != "citations":
            values[key] = prada[key]

    return values


@lru_cache(maxsize=None)
def electrode_balance(cell):
    """Stoichiometries (x_0, x_100, y_0, y_100) of graphite (x) and LFP (y) at 0 and 100 %
    SOC. The lithium inventory (cyclable lithium, Ah) is set so that the capacity between
    the voltage limits is the measured one: found by bisection, since the capacity grows
    with the inventory. (PyBaMM's "cell capacity" mode can return an unphysical second
    solution with more lithium than the cathode can hold.) Cached: it takes about a second."""
    g = CELLS[cell]
    area, eps_p, eps_n = electrode_fractions(cell)
    esoh = pybamm.lithium_ion.ElectrodeSOHSolver(pybamm.ParameterValues(_base_values(cell)))
    q_n = C_MAX_NEG * eps_n * g["anode_um"] * 1e-6 * area * F_CONST / 3600
    q_p = C_MAX_POS * eps_p * g["cathode_um"] * 1e-6 * area * F_CONST / 3600
    low, high = g["capacity_ah"], q_p
    for _ in range(30):
        q_li = 0.5 * (low + high)
        sol = esoh.solve({"Q_n": q_n, "Q_p": q_p, "Q_Li": q_li})
        if float(sol["Q"]) < g["capacity_ah"]:
            low = q_li
        else:
            high = q_li
    return tuple(float(sol[k]) for k in ("x_0", "x_100", "y_0", "y_100"))
