"""NMC physics model (LG M50, calibrated) against the measured self-heating and round-trip
efficiency of the same cell: Catenaro & Onori (2021), data/catenaro2021/nmc_tests.csv (see
scripts/extract_catenaro.py).

Each test is simulated as measured: from empty, CC charge at 0.3C to 4.2 V, CV hold to C/100,
1 h rest, CC discharge at 1, 2, 3 or 5C to 2.5 V, in a 5, 25 or 35 °C chamber. The model is
the one the dashboard runs for a 0.3C charge (choose_model: SPMe, DFN at 5C).

The cell sat in a cylindrical holder, which sets the cooling: the heat transfer coefficient h
is fitted once, to the 25 °C, 1C rise, and the other rates and chambers are predictions, so
they test the model's heat generation. Temperature rise = surface temperature at the end of
the measured discharge minus at its start; at 5C the tester stopped the discharge at its
temperature limit, so the model is read at the same discharged charge (Ah). The model's can
temperature is compared (core and can, see chemistry.R_CORE_21700).
Round-trip energy efficiency: discharge energy / charge energy, only for tests whose charge
started from empty.

Run:  python scripts/validate_thermal.py        (about 10 minutes; writes results/thermal_validation.csv)
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pybamm

from battery_twin.chemistry import build_model, choose_model
from battery_twin.constants import DATA_DIR

MEASURED = pd.read_csv(DATA_DIR / "catenaro2021" / "nmc_tests.csv")


def simulate(chamber_c, c_rate, h):
    """(Ah discharged, temperature rise [K]) along the discharge, and round-trip efficiency."""
    model, pv, _ = build_model("NMC", choose_model("NMC", 0.3, c_discharge=c_rate), chamber_c, h)
    steps = ("Charge at 0.3C until 4.2 V", "Hold at 4.2 V until C/100", "Rest for 1 hour",
             f"Discharge at {c_rate:g}C until 2.5 V")
    sol = pybamm.Simulation(model, parameter_values=pv,
                            experiment=pybamm.Experiment([steps])).solve(initial_soc=0)
    dis, ch = sol.cycles[0].steps[3], sol.cycles[0].steps[:2]
    energy = lambda s: np.trapezoid(np.abs(s["Voltage [V]"].entries * s["Current [A]"].entries),
                                    s["Time [s]"].entries) / 3600
    q = dis["Discharge capacity [A.h]"].entries
    temp = dis["Surface temperature [K]"].entries
    return q - q[0], temp - temp[0], energy(dis) / sum(energy(s) for s in ch)


def rise_at(sim, ah):
    q, rise, _ = sim
    return float(np.interp(ah, q, rise))


def fit_h(target, low=2.0, high=40.0):
    """Bisection on h: the 25 °C, 1C rise at the measured end of discharge."""
    ah = MEASURED.query("chamber_c == 25 and c_rate == 1").discharge_ah.mean()
    for _ in range(10):
        h = 0.5 * (low + high)
        if rise_at(simulate(25, 1.0, h), ah) > target:
            low = h                                     # too warm: more cooling
        else:
            high = h
    return 0.5 * (low + high)


def main():
    m = MEASURED.assign(rise=MEASURED.t_end_c - MEASURED.t_start_c,
                        rte=100 * MEASURED.discharge_wh / MEASURED.charge_wh,
                        complete=(MEASURED.charge_ah - MEASURED.discharge_ah).abs()
                        / MEASURED.discharge_ah < 0.02)
    groups = m.groupby(["chamber_c", "c_rate"])
    h = fit_h(groups.rise.mean()[(25, 1.0)])
    print(f"h fitted at 25 °C, 1C: {h:.1f} W/m2K")
    rows = []
    for (chamber, rate), g in groups:
        sim = simulate(chamber, rate, h)
        ah = g.discharge_ah.mean()
        full = g[g.complete]
        rows.append({"Chamber [°C]": chamber, "Discharge [C]": rate, "Cells": len(g),
                     "Discharged, measured [Ah]": ah, "Discharged, model to 2.5 V [Ah]": sim[0][-1],
                     "Rise, measured [K]": g.rise.mean(), "Rise, spread [K]": g.rise.std(),
                     "Rise, model [K]": rise_at(sim, ah),
                     "Efficiency, measured [%]": full.rte.mean() if len(full) else np.nan,
                     "Efficiency, model [%]": 100 * sim[2],
                     "Fitted here": chamber == 25 and rate == 1.0})
    out = pd.DataFrame(rows)
    Path("results").mkdir(exist_ok=True)
    out.to_csv("results/thermal_validation.csv", index=False)
    pd.set_option("display.width", 160)
    print(out.round(2).to_string(index=False))
    return out


if __name__ == "__main__":
    main()
