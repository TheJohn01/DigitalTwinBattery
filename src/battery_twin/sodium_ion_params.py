"""PyBaMM parameter set for a commercial sodium-ion cell.

Cell: Shenzhen Mushang NA18650-1250 (18650, 1.25 Ah, 1.5-3.8 V), layered-oxide cathode
Na0.96Ca0.02Ni1/3Fe1/3Mn1/3O2 (NFM) and hard-carbon anode.

Source: Schneider N., Stapf N., Mehlich C., Biswas A., Birke K. P., Fill A. (2025).
Towards accurate sodium-ion cell modelling: parametrization and validation of a commercial
sodium-ion cell incorporating temperature-dependent kinetics. J. Electrochem. Soc. 172,
090525. https://doi.org/10.1149/1945-7111/adfd16 (CC BY 4.0).

- Scalar values: the paper's Table III (commercial cell).
- Curves over stoichiometry (OCP, solid diffusivity, kinetic rate and their activation
  energies): the model curves of Fig. 12, read from the PDF's vector graphics by
  scripts/extract_schneider_fig12.py into data/schneider2025/. Diffusivity and kinetic rate
  are the "fit" curves, which include the paper's scaling factors (anode 1.3, cathode 5).
- Temperature: Arrhenius terms for diffusivity and kinetic rate (stoichiometry-dependent
  activation energy, paper Eq. 22 and 24) and VTF terms for the electrolyte (Eq. 3 and 5).
  The entropic heat is neglected, as in the paper.

Readings of Table III that needed a choice (see data/schneider2025/README.md):
- Thicknesses 55.55 / 15.5 / 77.5 um (positive / separator / negative); the table prints
  "55.55, 155, 775", and Table II and Laufen et al. 2024 give 55.5 / 15 / 77 um.
- Positive electrode density 4534.5 kg/m3 (printed "45345"); electrolyte 1420.16 mol/m3
  (printed "142016"; 1.42 mol/L measured by Laufen et al.).
- Current collectors: copper (6 um) on the anode and aluminium (17 um) on the cathode.
  Table III lists the copper values in the positive column, but the anode of this cell
  uses copper foil (Rehm et al. 2025, Table 2) and its 6 um foil is the anode foil in
  Table II.
- The active-material fractions include the paper's electrode design factors
  (cathode 0.2784 x 0.9702, anode 0.6827 x 1.142), as in its Eq. 15.
- Electrolyte diffusivity from the Einstein relation (paper Eq. 6) with the measured
  conductivity, as the text describes for the commercial cell.
"""
import numpy as np
import pybamm

from .constants import DATA_DIR

FOLDER = DATA_DIR / "schneider2025"
R_GAS = 8.314
F_CONST = 96485.33
T_REF = 298.15


def _curve(name):
    data = np.loadtxt(FOLDER / name, delimiter=",", skiprows=1)
    return data[:, 0], data[:, 1]


ANODE_OCP = _curve("anode_ocp_V.csv")
CATHODE_OCP = _curve("cathode_ocp_V.csv")
ANODE_D = _curve("anode_diffusivity_m2_s.csv")
CATHODE_D = _curve("cathode_diffusivity_m2_s.csv")
ANODE_K = _curve("anode_kinetic_rate.csv")
CATHODE_K = _curve("cathode_kinetic_rate.csv")
ANODE_D_EA = _curve("anode_diffusivity_Ea_kJ_mol.csv")
CATHODE_D_EA = _curve("cathode_diffusivity_Ea_kJ_mol.csv")
ANODE_K_EA = _curve("anode_kinetic_rate_Ea_kJ_mol.csv")
CATHODE_K_EA = _curve("cathode_kinetic_rate_Ea_kJ_mol.csv")

INTERPOLATOR = "linear"
ELECTROLYTE_CONDUCTIVITY_25C = 0.9816   # S/m, Table III (Laufen et al. measured 0.98)
ELECTROLYTE_CONCENTRATION = 1420.16     # mol/m3


def _interp(curve, sto, name):
    x, y = curve
    return pybamm.Interpolant(x, y, sto, name=name, interpolator=INTERPOLATOR, extrapolate=True)


def _arrhenius(ea_curve, sto, T, name):
    """exp(Ea/R (1/T_ref - 1/T)) with a stoichiometry-dependent activation energy."""
    ea = 1000 * _interp(ea_curve, sto, name)
    return pybamm.exp(ea / R_GAS * (1 / T_REF - 1 / T))


def _log_interp(curve, sto, name):
    """Interpolate a quantity that spans decades in log space."""
    x, y = curve
    return 10 ** pybamm.Interpolant(x, np.log10(y), sto, name=name, interpolator=INTERPOLATOR,
                                    extrapolate=True)


# --- open-circuit potentials ----------------------------------------------------------
def anode_ocp(sto):
    return _interp(ANODE_OCP, sto, "anode_ocp_Schneider2025")


def cathode_ocp(sto):
    return _interp(CATHODE_OCP, sto, "cathode_ocp_Schneider2025")


# --- solid diffusivity -----------------------------------------------------------------
def anode_diffusivity(sto, T):
    return (_log_interp(ANODE_D, sto, "anode_D_Schneider2025")
            * _arrhenius(ANODE_D_EA, sto, T, "anode_D_Ea_Schneider2025"))


def cathode_diffusivity(sto, T):
    return (_log_interp(CATHODE_D, sto, "cathode_D_Schneider2025")
            * _arrhenius(CATHODE_D_EA, sto, T, "cathode_D_Ea_Schneider2025"))


# --- exchange-current density: i0 = F k (c_max - c_s)^0.5 c_s^0.5 c_e^0.5 (Eq. 23) -----
SITE_FLOOR = 1e-4   # fraction of c_max kept free / filled, so i0 never reaches exactly 0


def _site_term(c_s_surf, c_s_max):
    """c_s^0.5 (c_max - c_s)^0.5, with both factors kept above SITE_FLOOR * c_max.
    When charging in the cold the anode surface saturates (stoichiometry ~0.9998); the
    exact expression then makes i0 -> 0 and the solver fails in the constant-voltage step.
    The floor changes i0 only within 0.01 % of a full or empty particle surface."""
    floor = SITE_FLOOR * c_s_max
    return (pybamm.maximum(c_s_surf, floor) ** 0.5
            * pybamm.maximum(c_s_max - c_s_surf, floor) ** 0.5)


def anode_exchange_current(c_e, c_s_surf, c_s_max, T):
    sto = c_s_surf / c_s_max
    k = (_log_interp(ANODE_K, sto, "anode_k_Schneider2025")
         * _arrhenius(ANODE_K_EA, sto, T, "anode_k_Ea_Schneider2025"))
    return F_CONST * k * c_e ** 0.5 * _site_term(c_s_surf, c_s_max)


def cathode_exchange_current(c_e, c_s_surf, c_s_max, T):
    sto = c_s_surf / c_s_max
    k = (_log_interp(CATHODE_K, sto, "cathode_k_Schneider2025")
         * _arrhenius(CATHODE_K_EA, sto, T, "cathode_k_Ea_Schneider2025"))
    return F_CONST * k * c_e ** 0.5 * _site_term(c_s_surf, c_s_max)


# --- electrolyte -----------------------------------------------------------------------
def electrolyte_conductivity(c_e, T):
    """Measured value at 25 °C with the VTF temperature dependence of Eq. 3
    (B = 353 K, T0 = 176 K). No concentration dependence is given."""
    return ELECTROLYTE_CONDUCTIVITY_25C * pybamm.exp(-353 / (T - 176) + 353 / (T_REF - 176))


def electrolyte_diffusivity(c_e, T):
    """Einstein relation D = sigma R T / (F^2 c_e) (Eq. 6), evaluated at the initial
    salt concentration, so it follows the conductivity's temperature dependence."""
    return electrolyte_conductivity(c_e, T) * R_GAS * T / (F_CONST ** 2 * ELECTROLYTE_CONCENTRATION)


def get_parameter_values():
    """Parameter dictionary for pybamm.ParameterValues (lithium-ion DFN equations, which
    are the same equations for sodium ions)."""
    return {
        "chemistry": "lithium_ion",
        # cell
        "Nominal cell capacity [A.h]": 1.25,
        "Current function [A]": 1.25,
        "Lower voltage cut-off [V]": 1.5,
        "Upper voltage cut-off [V]": 3.8,
        "Open-circuit voltage at 0% SOC [V]": 1.5,
        "Open-circuit voltage at 100% SOC [V]": 3.8,
        "Number of electrodes connected in parallel to make a cell": 2.0,
        "Number of cells connected in series to make a battery": 1.0,
        "Electrode height [m]": 0.0575,
        "Electrode width [m]": 0.704,
        "Contact resistance [Ohm]": 0.0,
        "Cell volume [m3]": 1.665e-5,
        "Cell cooling surface area [m2]": 3.67566e-3,
        "Reference temperature [K]": T_REF,
        "Ambient temperature [K]": T_REF,
        "Initial temperature [K]": T_REF,
        "Total heat transfer coefficient [W.m-2.K-1]": 10.0,
        # current collectors (anode: copper, cathode: aluminium)
        "Negative current collector thickness [m]": 6e-6,
        "Negative current collector conductivity [S.m-1]": 58.4e6,
        "Negative current collector density [kg.m-3]": 8960.0,
        "Negative current collector specific heat capacity [J.kg-1.K-1]": 385.0,
        "Negative current collector thermal conductivity [W.m-1.K-1]": 401.0,
        "Positive current collector thickness [m]": 17e-6,
        "Positive current collector conductivity [S.m-1]": 35.5e6,
        "Positive current collector density [kg.m-3]": 2700.0,
        "Positive current collector specific heat capacity [J.kg-1.K-1]": 897.0,
        "Positive current collector thermal conductivity [W.m-1.K-1]": 287.0,
        # negative electrode: hard carbon
        "Negative electrode thickness [m]": 77.5e-6,
        "Negative electrode porosity": 0.308,
        "Negative electrode active material volume fraction": 0.6827 * 1.142,
        "Negative particle radius [m]": 2.195e-6,
        "Maximum concentration in negative electrode [mol.m-3]": 13229.6,
        "Initial concentration in negative electrode [mol.m-3]": 9642.0,
        "Negative electrode conductivity [S.m-1]": 45.3,
        "Negative electrode Bruggeman coefficient (electrolyte)": 1.5,
        "Negative electrode Bruggeman coefficient (electrode)": 0.0,
        "Negative electrode charge transfer coefficient": 0.5,
        "Negative electrode double-layer capacity [F.m-2]": 0.2,
        "Negative electrode OCP [V]": anode_ocp,
        "Negative electrode OCP entropic change [V.K-1]": 0.0,
        "Negative particle diffusivity [m2.s-1]": anode_diffusivity,
        "Negative electrode exchange-current density [A.m-2]": anode_exchange_current,
        "Negative electrode density [kg.m-3]": 1350.0,
        "Negative electrode specific heat capacity [J.kg-1.K-1]": 533.0,
        "Negative electrode thermal conductivity [W.m-1.K-1]": 1.2,
        # separator
        "Separator thickness [m]": 15.5e-6,
        "Separator porosity": 0.4065,
        "Separator Bruggeman coefficient (electrolyte)": 1.5,
        "Separator density [kg.m-3]": 1400.0,
        "Separator specific heat capacity [J.kg-1.K-1]": 993.0,
        "Separator thermal conductivity [W.m-1.K-1]": 0.31,
        # positive electrode: layered oxide NFM
        "Positive electrode thickness [m]": 55.55e-6,
        "Positive electrode porosity": 0.2972,
        "Positive electrode active material volume fraction": 0.2784 * 0.9702,
        "Positive particle radius [m]": 1.484e-6,
        "Maximum concentration in positive electrode [mol.m-3]": 40846.85,
        "Initial concentration in positive electrode [mol.m-3]": 10.0,
        "Positive electrode conductivity [S.m-1]": 5.0,
        "Positive electrode Bruggeman coefficient (electrolyte)": 1.5,
        "Positive electrode Bruggeman coefficient (electrode)": 0.0,
        "Positive electrode charge transfer coefficient": 0.5,
        "Positive electrode double-layer capacity [F.m-2]": 0.2,
        "Positive electrode OCP [V]": cathode_ocp,
        "Positive electrode OCP entropic change [V.K-1]": 0.0,
        "Positive particle diffusivity [m2.s-1]": cathode_diffusivity,
        "Positive electrode exchange-current density [A.m-2]": cathode_exchange_current,
        "Positive electrode density [kg.m-3]": 4534.5,
        "Positive electrode specific heat capacity [J.kg-1.K-1]": 662.0,
        "Positive electrode thermal conductivity [W.m-1.K-1]": 0.66,
        # electrolyte: NaPF6 1.42 mol/L in carbonates
        "Initial concentration in electrolyte [mol.m-3]": ELECTROLYTE_CONCENTRATION,
        "Cation transference number": 0.3816,
        "Thermodynamic factor": 1.0,
        "Electrolyte conductivity [S.m-1]": electrolyte_conductivity,
        "Electrolyte diffusivity [m2.s-1]": electrolyte_diffusivity,
    }
