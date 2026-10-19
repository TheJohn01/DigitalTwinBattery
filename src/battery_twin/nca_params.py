"""PyBaMM parameter set for a commercial NCA cell.

Cell: Samsung INR21700-50E (21700, 4.9 Ah, 2.5-4.2 V), LiNi0.87Co0.11Al0.02O2 (NCA) cathode
and graphite/SiOx anode ("HE" cell).

Source: Schmitt C., Gerle M., Kopljar D., Friedrich K. A. (2023). Full parameterization study of
a high-energy and a high-power Li-ion cell for physicochemical models. J. Electrochem. Soc. 170,
070509. https://doi.org/10.1149/1945-7111/ace1a7 (CC BY 4.0).

- Scalar values: Table SIV of the supplementary information ("used in the P2D model"), which
  includes the paper's adjusted values of Table VI (c_max, active-material fractions,
  stoichiometry at 100 % SOC, fitted diffusion coefficients).
- Bruggeman: the paper defines tortuosity tau = eps^-alpha (Table IV/SIV: alpha = 1.07 anode,
  0.5 cathode, 0.85 separator); PyBaMM's exponent b (eps_eff = eps^b) is 1 + alpha.
- Open-circuit potentials, exchange-current density and the validation curves were read from
  the paper's figures by scripts/digitize_schmitt.py into data/schmitt2023/ (see its README).
  The exchange current uses the measured points of Fig. S14 (25 °C), because the analytic fits
  in Table SIV do not reproduce them.
- Temperature: Arrhenius terms with the measured activation energies (diffusion 25.3 / 13.2,
  exchange current 50.1 / 44.1 kJ/mol for anode / cathode).
- Ohmic resistance: 1.31 mOhm m2 per electrode, from the measured 22.1 mOhm of the cell
  (paper: mostly current collectors and tabs). Used as PyBaMM's contact resistance.
- Not given in the paper and therefore taken from elsewhere:
  * electrolyte transport: Landesfeind & Gasteiger (2019), as in the paper, but for LiPF6 in
    EC:EMC 3:7 (the coefficients PyBaMM ships) instead of EC:DMC 1:1 (about 10 % lower
    conductivity at 25 °C);
  * thermal properties, current-collector and separator materials, SEI parameters: Chen 2020
    (LG M50, also a 21700 cell), filled in by chemistry.build_model.
"""
import numpy as np
import pybamm
from pybamm.input.parameters.lithium_ion.ORegan2022 import (
    electrolyte_conductivity_EC_EMC_3_7_Landesfeind2019,
    electrolyte_diffusivity_EC_EMC_3_7_Landesfeind2019, electrolyte_TDF_EC_EMC_3_7_Landesfeind2019,
    electrolyte_transference_number_EC_EMC_3_7_Landesfeind2019)

from .constants import DATA_DIR

FOLDER = DATA_DIR / "schmitt2023"
R_GAS = 8.314
T_REF = 298.15
ELECTRODE_AREA = 0.1184           # m2, coated cathode area (both sides)
ELECTRODE_HEIGHT = 0.065          # m (21700 jelly roll); width = area / height


def _curve(name):
    data = np.loadtxt(FOLDER / name, delimiter=",", skiprows=1)
    return data[:, 0], data[:, 1]


ANODE_OCP = _curve("anode_ocp_V.csv")
CATHODE_OCP = _curve("cathode_ocp_V.csv")
ANODE_J0 = _curve("anode_j0_25C.csv")
CATHODE_J0 = _curve("cathode_j0_25C.csv")


def _arrhenius(ea_j_mol, T):
    return pybamm.exp(ea_j_mol / R_GAS * (1 / T_REF - 1 / T))


def _j0_at_25c(curve, sto, name):
    """Measured exchange current at 25 °C; held constant beyond the measured range."""
    x, y = curve
    sto = pybamm.maximum(pybamm.minimum(sto, float(x.max())), float(x.min()))
    return pybamm.Interpolant(x, y, sto, name=name)


def anode_ocp(sto):
    """Digitised OCP plus a steep drop as graphite becomes full (x -> 1). The balancing puts
    the anode at x = 0.999 at 100 % SOC, and the digitised curve, flat at about 0.08 V there,
    ends at x = 1.004, so a constant-voltage hold at 4.2 V would push x past 1. The wall
    changes the OCP by under 7 mV at x = 0.999 and stops lithiation just above x = 1."""
    x, y = ANODE_OCP
    full_wall = 0.01 * pybamm.exp((sto - 1.0) / 0.002)
    return pybamm.Interpolant(x, y, sto, name="anode_ocp_Schmitt2023", extrapolate=True) - full_wall


def cathode_ocp(sto):
    x, y = CATHODE_OCP
    return pybamm.Interpolant(x, y, sto, name="cathode_ocp_Schmitt2023", extrapolate=True)


def anode_diffusivity(sto, T):
    return 1.30e-14 * _arrhenius(25300, T)


def cathode_diffusivity(sto, T):
    return 1.34e-14 * _arrhenius(13200, T)


def anode_exchange_current(c_e, c_s_surf, c_s_max, T):
    j0 = _j0_at_25c(ANODE_J0, c_s_surf / c_s_max, "anode_j0_Schmitt2023")
    return j0 * (c_e / 1000) ** 0.5 * _arrhenius(50100, T)


def cathode_exchange_current(c_e, c_s_surf, c_s_max, T):
    j0 = _j0_at_25c(CATHODE_J0, c_s_surf / c_s_max, "cathode_j0_Schmitt2023")
    return j0 * (c_e / 1000) ** 0.5 * _arrhenius(44100, T)


def get_parameter_values():
    """Electrochemical parameters of the Samsung INR21700-50E. Missing thermal and SEI values
    are filled in from Chen 2020 by chemistry.build_model."""
    return {
        "chemistry": "lithium_ion",
        "Nominal cell capacity [A.h]": 4.9,
        "Current function [A]": 4.9,
        "Lower voltage cut-off [V]": 2.5,
        "Upper voltage cut-off [V]": 4.2,
        "Open-circuit voltage at 0% SOC [V]": 2.5,
        "Open-circuit voltage at 100% SOC [V]": 4.2,
        "Number of electrodes connected in parallel to make a cell": 1.0,
        "Number of cells connected in series to make a battery": 1.0,
        "Electrode height [m]": ELECTRODE_HEIGHT,
        "Electrode width [m]": ELECTRODE_AREA / ELECTRODE_HEIGHT,
        # 1.31 mOhm m2 per electrode (two electrodes) over the electrode area
        "Contact resistance [Ohm]": 2 * 1.31e-3 / ELECTRODE_AREA,
        "Reference temperature [K]": T_REF,
        "Ambient temperature [K]": T_REF,
        "Initial temperature [K]": T_REF,
        "Negative current collector thickness [m]": 9e-6,
        "Positive current collector thickness [m]": 13e-6,
        # negative electrode: graphite / SiOx
        "Negative electrode thickness [m]": 75e-6,
        "Negative electrode porosity": 0.24,
        "Negative electrode active material volume fraction": 0.66,
        "Negative particle radius [m]": 7.3e-6,
        "Maximum concentration in negative electrode [mol.m-3]": 31695.0,
        "Initial concentration in negative electrode [mol.m-3]": 0.999 * 31695.0,
        "Negative electrode conductivity [S.m-1]": 236.0,
        "Negative electrode Bruggeman coefficient (electrolyte)": 1 + 1.07,
        "Negative electrode Bruggeman coefficient (electrode)": 0.0,
        "Negative electrode charge transfer coefficient": 0.5,
        "Negative electrode double-layer capacity [F.m-2]": 0.00082,
        "Negative electrode OCP [V]": anode_ocp,
        "Negative electrode OCP entropic change [V.K-1]": 0.0,
        "Negative particle diffusivity [m2.s-1]": anode_diffusivity,
        "Negative electrode exchange-current density [A.m-2]": anode_exchange_current,
        # separator
        "Separator thickness [m]": 18e-6,
        "Separator porosity": 0.31,
        "Separator Bruggeman coefficient (electrolyte)": 1 + 0.85,
        # positive electrode: NCA
        "Positive electrode thickness [m]": 60e-6,
        "Positive electrode porosity": 0.21,
        "Positive electrode active material volume fraction": 0.74,
        "Positive particle radius [m]": 5.1e-6,
        "Maximum concentration in positive electrode [mol.m-3]": 50000.0,
        "Initial concentration in positive electrode [mol.m-3]": 0.16 * 50000.0,
        "Positive electrode conductivity [S.m-1]": 0.92,
        "Positive electrode Bruggeman coefficient (electrolyte)": 1 + 0.5,
        "Positive electrode Bruggeman coefficient (electrode)": 0.0,
        "Positive electrode charge transfer coefficient": 0.5,
        "Positive electrode double-layer capacity [F.m-2]": 0.00497,
        "Positive electrode OCP [V]": cathode_ocp,
        "Positive electrode OCP entropic change [V.K-1]": 0.0,
        "Positive particle diffusivity [m2.s-1]": cathode_diffusivity,
        "Positive electrode exchange-current density [A.m-2]": cathode_exchange_current,
        # electrolyte: 1 M LiPF6 (Landesfeind & Gasteiger 2019, EC:EMC 3:7, see above)
        "Initial concentration in electrolyte [mol.m-3]": 1000.0,
        "Electrolyte conductivity [S.m-1]": electrolyte_conductivity_EC_EMC_3_7_Landesfeind2019,
        "Electrolyte diffusivity [m2.s-1]": electrolyte_diffusivity_EC_EMC_3_7_Landesfeind2019,
        "Cation transference number": electrolyte_transference_number_EC_EMC_3_7_Landesfeind2019,
        "Thermodynamic factor": electrolyte_TDF_EC_EMC_3_7_Landesfeind2019,
    }
