"""Fit the NMC electrolyte diffusivity factor to measured high-rate capacities of the LG M50.

With Chen2020's electrolyte (Nyman et al. 2008, LiPF6 in EC:EMC; the M50's own electrolyte
is not published) the salt runs out near the current collector at 3C and the model stops
at about half the capacity the cell delivers. The diffusivity is multiplied by one factor,
picked on a grid to match the mean capacity at 2C and 3C in the 25 and 35 °C chambers of
Catenaro & Onori (2021), data/catenaro2021/nmc_tests.csv. The 5 °C chamber is printed as a
check only: Chen2020's transport properties have no temperature dependence, so the model
is optimistic in the cold whatever the factor.

Each test as measured: CC 0.3C to 4.2 V, CV to C/100, 1 h rest, CC discharge to 2.5 V. DFN,
h = 17 W/m2K (the holder's cooling, scripts/validate_thermal.py).

Run:  python scripts/fit_electrolyte.py     (about 15 minutes); put the printed factor in
      src/battery_twin/data/calibration.json ("electrolyte_diffusivity_factor").
"""
import numpy as np
import pandas as pd
import pybamm

from battery_twin.chemistry import CALIBRATION, build_model
from battery_twin.constants import DATA_DIR

MEASURED = pd.read_csv(DATA_DIR / "catenaro2021" / "nmc_tests.csv").groupby(
    ["chamber_c", "c_rate"]).discharge_ah.mean()
FIT_CASES = [(25, 2.0), (25, 3.0), (35, 2.0), (35, 3.0)]
CHECK_CASES = [(5, 1.0), (5, 2.0), (5, 3.0)]


def capacity(chamber_c, c_rate):
    model, pv, _ = build_model("NMC", "DFN", chamber_c, 17.0)
    steps = ("Charge at 0.3C until 4.2 V", "Hold at 4.2 V until C/100", "Rest for 1 hour",
             f"Discharge at {c_rate:g}C until 2.5 V")
    sol = pybamm.Simulation(model, parameter_values=pv,
                            experiment=pybamm.Experiment([steps])).solve(initial_soc=0)
    q = sol.cycles[0].steps[3]["Discharge capacity [A.h]"].entries
    return float(q[-1] - q[0])


def rms(cases):
    return float(np.sqrt(np.mean([(capacity(*k) - MEASURED[k]) ** 2 for k in cases])))


if __name__ == "__main__":
    errors = {}
    for factor in (1.5, 2.0, 2.5, 3.0):
        CALIBRATION["electrolyte_diffusivity_factor"] = factor     # read by the NMC model
        errors[factor] = rms(FIT_CASES)
        print(f"factor {factor:g}: RMS capacity error {errors[factor]:.3f} Ah (25 and 35 °C)")
    best = min(errors, key=errors.get)
    CALIBRATION["electrolyte_diffusivity_factor"] = best
    print(f"\nelectrolyte_diffusivity_factor = {best:g}")
    for k in CHECK_CASES:
        print(f"  check {k[0]} °C, {k[1]:g}C: model {capacity(*k):.2f} Ah, measured {MEASURED[k]:.2f} Ah")
