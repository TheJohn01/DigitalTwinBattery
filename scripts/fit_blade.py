"""Fit the three free values of the BYD LFP parameter set (lfp_blade_params.py), one per
measurement, in this order:

1. LFP_OCP_SHIFT: the cell OCV vs the pseudo-OCV of a commercial 280 Ah LFP / graphite cell
   (mean of its C/10 charge and discharge at 25 °C, 10-90 % SOC; Gray & Vagg 2026,
   data/gray2026). The Afshar LFP OCP of Prada2013 sits a few tens of mV too low.
2. GRAPHITE_J0_SCALE: the charge-transfer resistance of the BYD 4680 LFP cell, 5.9 Ohm cm2
   from impedance at 20 % SOC (Liu et al. 2025, Fig. 6a; normalised to the LFP electrode
   area). With linear kinetics R_ct = RT/F * (1/(a L j0)_graphite + 1/(a L j0)_LFP), which
   is solved for the graphite factor. With Chen 2020's graphite kinetics the model gives
   about 40 Ohm cm2, far above the 6-17 Ohm cm2 Liu et al. measured in pulses.
3. LFP_HYSTERESIS: half the gap between the C/10 charge and discharge curves of the same
   280 Ah cell (mean over 10-90 % SOC), minus the part its own measured resistance explains
   (28 A x (R0 + R1) of its HPPC fit at 25 °C, Gray & Vagg 2026).
4. GRAPHITE_DIFFUSIVITY: the rate test of the same cell, discharge capacity at 1C and 2C
   relative to C/2 (94.7 and 87.9 %; Liu et al. Fig. 7): symmetric CC-CV cycles, 2.8-3.65 V,
   CV to C/60, 25 °C, lumped thermal model with h = 10 W/m2K (cell holder in a chamber).
   With Prada2013's 3e-15 m2/s the model gives 91 and 74 %, and graphite diffusion is what
   limits it (the LFP diffusivity, porosity and conductivity hardly matter).

Run: python scripts/fit_blade.py   (a few minutes). Copy the four printed values into
lfp_blade_params.py, then run scripts/validate_blade.py.
"""
import numpy as np
import pandas as pd
import pybamm

from battery_twin import lfp_blade_params as blade
from battery_twin.constants import DATA_DIR

R_GAS, F = 8.314, 96485.33
RCT_MEASURED = 5.9e-4                       # Ohm m2 (5.9 Ohm cm2), Liu et al. 2025
RATE_MEASURED = {"1C": 0.947, "2C": 0.879}  # discharge capacity / C/2 capacity
H_HOLDER = 10.0


def parameter_values(cell, ambient_c=25.0, h=H_HOLDER):
    """Parameter values of a BYD cell, completed from Chen2020 as in chemistry.build_model."""
    pv = pybamm.ParameterValues(blade.get_parameter_values(cell))
    donor = pybamm.ParameterValues("Chen2020")
    have = set(pv.keys())
    pv.update({k: donor[k] for k in donor.keys() if k not in have}, check_already_exists=False)
    pv.update({"Total heat transfer coefficient [W.m-2.K-1]": h,
               "Ambient temperature [K]": ambient_c + 273.15,
               "Initial temperature [K]": ambient_c + 273.15})
    return pv


def model_ocv(cell, soc):
    """Cell OCV at the given SOCs, from the electrode balance and the two OCPs."""
    x_0, x_100, y_0, y_100 = blade.electrode_balance(cell)
    x = x_0 + soc * (x_100 - x_0)
    y = y_0 - soc * (y_0 - y_100)
    return blade.lfp_ocp(y) - blade.graphite_ocp_PeymanMPM(x)


def fit_ocp_shift():
    data = pd.read_csv(DATA_DIR / "gray2026" / "pseudo_ocv_25C.csv")
    data = data[(data["soc"] >= 0.1) & (data["soc"] <= 0.9)]
    for _ in range(3):              # the balance moves a little with the shift: repeat
        error = model_ocv("Blade", data["soc"].to_numpy()) - data["pseudo_ocv_V"].to_numpy()
        blade.LFP_OCP_SHIFT -= float(np.mean(error))
        blade.clear_cache()
    error = model_ocv("Blade", data["soc"].to_numpy()) - data["pseudo_ocv_V"].to_numpy()
    return blade.LFP_OCP_SHIFT, 1000 * float(np.sqrt(np.mean(error ** 2)))


def fit_j0_scale():
    """Graphite factor that gives the measured R_ct of the BYD 4680 at 20 % SOC, 25 °C."""
    pv = parameter_values("BYD4680")
    x_0, x_100, y_0, y_100 = blade.electrode_balance("BYD4680")
    x, y = x_0 + 0.2 * (x_100 - x_0), y_0 - 0.2 * (y_0 - y_100)
    c_e, temp = pv["Initial concentration in electrolyte [mol.m-3]"], 298.15

    def a_l_j0(side, sto, c_max, j0_function):
        a = 3 * pv[f"{side} electrode active material volume fraction"] / pv[f"{side} particle radius [m]"]
        j0 = pybamm.Scalar(0) + j0_function(c_e, sto * c_max, c_max, temp)
        return a * pv[f"{side} electrode thickness [m]"] * float(j0.evaluate())

    graphite = a_l_j0("Negative", x, blade.C_MAX_NEG,
                      blade.graphite_LGM50_electrolyte_exchange_current_density_Chen2020)
    lfp = a_l_j0("Positive", y, blade.C_MAX_POS, pv["Positive electrode exchange-current density [A.m-2]"])
    rt_f = R_GAS * temp / F
    scale = 1 / (graphite * (RCT_MEASURED / rt_f - 1 / lfp))
    blade.GRAPHITE_J0_SCALE = scale
    return scale, 1e4 * rt_f / graphite, 1e4 * rt_f / lfp


def fit_hysteresis():
    gap = pd.read_csv(DATA_DIR / "gray2026" / "pseudo_ocv_25C.csv")
    gap = gap[(gap["soc"] >= 0.1) & (gap["soc"] <= 0.9)]
    hppc = pd.read_csv(DATA_DIR / "gray2026" / "LIC_hppc_analysis.csv")
    hppc = hppc[hppc["Temperature_C"] == 25]
    resistance = np.interp(gap["soc"], hppc["SoC"], hppc["R0_Ohm"] + hppc["R1_Ohm"])
    blade.LFP_HYSTERESIS = float(np.mean(gap["half_gap_V"] - 28.0 * resistance))
    return blade.LFP_HYSTERESIS, 1000 * float(np.mean(gap["half_gap_V"]))


def rate_test(pv):
    """Discharge capacity [Ah] after a CC-CV charge, at C/2, 1C and 2C (Liu's protocol)."""
    model = pybamm.lithium_ion.DFN({"thermal": "lumped", **blade.MODEL_OPTIONS})
    capacity = {}
    for rate in ("C/2", "1C", "2C"):
        steps = (f"Charge at {rate} until 3.65 V", "Hold at 3.65 V until C/60",
                 "Rest for 30 minutes", f"Discharge at {rate} until 2.8 V")
        sol = pybamm.Simulation(model, parameter_values=pv,
                                experiment=pybamm.Experiment([steps])).solve(initial_soc=0.0)
        q = sol.cycles[0].steps[3]["Discharge capacity [A.h]"].entries
        capacity[rate] = float(q[-1] - q[0])
    return capacity


def rate_error(log_d):
    blade.GRAPHITE_DIFFUSIVITY = 10 ** log_d
    cap = rate_test(parameter_values("BYD4680"))
    return sum((cap[r] / cap["C/2"] - RATE_MEASURED[r]) ** 2 for r in RATE_MEASURED)


def fit_diffusivity():
    grid = np.linspace(np.log10(2e-15), np.log10(3e-14), 9)
    best = grid[int(np.argmin([rate_error(x) for x in grid]))]
    fine = np.linspace(best - 0.08, best + 0.08, 9)
    blade.GRAPHITE_DIFFUSIVITY = 10 ** fine[int(np.argmin([rate_error(x) for x in fine]))]
    cap = rate_test(parameter_values("BYD4680"))
    return blade.GRAPHITE_DIFFUSIVITY, {r: cap[r] / cap["C/2"] for r in RATE_MEASURED}


if __name__ == "__main__":
    shift, rmse = fit_ocp_shift()
    print(f"LFP_OCP_SHIFT = {shift:.4f} V   (OCV RMSE {rmse:.1f} mV at 10-90 % SOC)")
    scale, r_graphite, r_lfp = fit_j0_scale()
    print(f"GRAPHITE_J0_SCALE = {scale:.3g}   (before: graphite {r_graphite:.1f}, "
          f"LFP {r_lfp:.2f} Ohm cm2)")
    hysteresis, half_gap = fit_hysteresis()
    print(f"LFP_HYSTERESIS = {hysteresis:.4f} V   (half gap at C/10 {half_gap:.1f} mV)")
    d, ratios = fit_diffusivity()
    print(f"GRAPHITE_DIFFUSIVITY = {d:.3g}   (1C {100 * ratios['1C']:.1f} %, "
          f"2C {100 * ratios['2C']:.1f} %; measured 94.7, 87.9 %)")
