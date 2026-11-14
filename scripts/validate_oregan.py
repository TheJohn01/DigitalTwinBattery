"""NMC physics with O'Regan et al.'s (2022) LG M50 electrode functions against Catenaro &
Onori's (2021) discharges at 5, 25 and 35 °C (data/catenaro2021/nmc_tests.csv).

Chen2020, the NMC parameter set, has electrode transport and kinetics without temperature
dependence, so the model is optimistic in the cold (README 4.3). O'Regan et al., Electrochim.
Acta 425, 140700 (2022, open access; PyBaMM set ORegan2022) measured temperature-dependent
diffusivities, exchange currents and entropic coefficients on the same cell. Two variants
replace Chen2020's functions in the calibrated NMC model (chemistry.CHEMISTRIES["NMC"]):
- "kinetics": particle diffusivities and exchange-current densities;
- "kinetics + OCP": also the OCPs and their entropic coefficients.
Everything else (calibrated capacity, SEI, electrolyte factor, cooling) stays. Each test as
measured (scripts/fit_electrolyte.py): CC 0.3C to 4.2 V, CV to C/100, 1 h rest, CC discharge
to 2.5 V; DFN, h = 17 W/m2K.

Switch rule: the NMC model takes a variant only if it lowers the 5 °C error and keeps the
25 and 35 °C cases (fitted with Chen2020) within 0.07 Ah RMS.

Run:  python scripts/validate_oregan.py     (about 30 minutes)
"""
import numpy as np
import pandas as pd
import pybamm

from battery_twin.chemistry import CHEMISTRIES, build_model
from battery_twin.constants import DATA_DIR

MEASURED = pd.read_csv(DATA_DIR / "catenaro2021" / "nmc_tests.csv").groupby(
    ["chamber_c", "c_rate"]).discharge_ah.mean()
CASES = [(t, c) for t in (5, 25, 35) for c in (1.0, 2.0, 3.0) if (t, c) in MEASURED.index]
KINETICS = [f"{e} {k}" for e in ("Negative", "Positive")
            for k in ("particle diffusivity [m2.s-1]", "electrode exchange-current density [A.m-2]")]
OCP = [f"{e} electrode {k}" for e in ("Negative", "Positive")
       for k in ("OCP [V]", "OCP entropic change [V.K-1]")]
VARIANTS = {"Chen2020 (now)": [], "kinetics": KINETICS, "kinetics + OCP": KINETICS + OCP}


def capacity(chamber_c, c_rate):
    model, pv, _ = build_model("NMC", "DFN", chamber_c, 17.0)
    steps = ("Charge at 0.3C until 4.2 V", "Hold at 4.2 V until C/100", "Rest for 1 hour",
             f"Discharge at {c_rate:g}C until 2.5 V")
    try:
        sol = pybamm.Simulation(model, parameter_values=pv,
                                experiment=pybamm.Experiment([steps])).solve(initial_soc=0)
        q = sol.cycles[0].steps[3]["Discharge capacity [A.h]"].entries
        return float(q[-1] - q[0])
    except Exception:          # the variant does not solve: no value
        return np.nan


if __name__ == "__main__":
    oregan = pybamm.ParameterValues("ORegan2022")
    base = dict(CHEMISTRIES["NMC"]["updates"])
    rows = []
    for name, keys in VARIANTS.items():
        CHEMISTRIES["NMC"]["updates"] = {**base, **{k: oregan[k] for k in keys}}
        for case in CASES:
            rows.append({"variant": name, "chamber [°C]": case[0], "C-rate": case[1],
                         "model [Ah]": capacity(*case), "measured [Ah]": MEASURED[case]})
            print(rows[-1])
    CHEMISTRIES["NMC"]["updates"] = base
    d = pd.DataFrame(rows)
    d["error [Ah]"] = d["model [Ah]"] - d["measured [Ah]"]
    pd.set_option("display.width", 160)
    print(d.round(3).to_string(index=False))
    cold = d["chamber [°C]"] == 5
    print("\nRMS error [Ah]:")
    print(pd.DataFrame({"5 °C": d[cold].groupby("variant")["error [Ah]"].apply(
                            lambda e: np.sqrt(np.mean(e ** 2))),
                        "25 and 35 °C": d[~cold].groupby("variant")["error [Ah]"].apply(
                            lambda e: np.sqrt(np.mean(e ** 2)))}).round(3).to_string())
