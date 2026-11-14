"""Does a knee appear at the dashboard's default NMC duty? O'Kane et al.'s coupled model.

The empirical NMC model (ageing.NmcRefit) adds a calendar and a cycling loss and has no
knee. O'Kane et al. (2022, PCCP 24, 7909, CC BY) couple SEI growth, SEI on cracks, lithium
plating and loss of active material from particle cracking in PyBaMM for the same LG M50
cell (parameter set OKane2022); their model reproduces a knee without fitting one. Here it
runs the dashboard's default battery test (1C discharge to 2.5 V, 0.3C CC-CV to 4.2 V,
20 °C, one cycle a day: the rest of the day at full charge, as ageing.add_rest), and its
capacity is compared with NmcRefit's curve for the same cycle. Isothermal: at these rates
the cell warms by about 1 K.

A knee shows as fade that speeds up: the loss rate over the last tenth of the run divided
by the mean rate over the run (straight line = 1; NmcRefit's power law < 1).

Run:  python scripts/check_okane_knee.py [cycles]   (default 600 cycles; hours;
      writes results/okane_knee.csv)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pybamm

from battery_twin.ageing import add_rest, predict_capacity
from battery_twin.chemistry import standard_profile

TEMP_C = 20.0
C_CHARGE, C_DISCHARGE = 0.3, 1.0
REST_H = 24 - 1 / C_DISCHARGE - 1 / C_CHARGE - 0.5        # fills the day (CV tail ~0.5 h)
OPTIONS = {"SEI": "solvent-diffusion limited", "SEI porosity change": "true",
           "lithium plating": "partially reversible",
           "lithium plating porosity change": "true",
           "particle mechanics": ("swelling and cracking", "swelling only"),
           "SEI on cracks": "true", "loss of active material": "stress-driven"}
OUT = Path("results") / "okane_knee.csv"
BLOCK = 20


def run(n_cycles):
    pv = pybamm.ParameterValues("OKane2022")
    temp_k = TEMP_C + 273.15
    pv.update({"Ambient temperature [K]": temp_k, "Initial temperature [K]": temp_k})
    cycle = (f"Discharge at {C_DISCHARGE:g}C until 2.5 V", "Rest for 5 minutes",
             f"Charge at {C_CHARGE:g}C until 4.2 V", "Hold at 4.2 V until C/20",
             f"Rest for {REST_H:.2f} hours")
    model, parts = pybamm.lithium_ion.DFN(OPTIONS), []
    # blocks of BLOCK cycles, each started from the last state: a single 1,000-cycle solution
    # does not fit in memory
    while sum(len(p) for p in parts) < n_cycles:
        sim = pybamm.Simulation(model, parameter_values=pv,
                                experiment=pybamm.Experiment([cycle] * BLOCK))
        sol = sim.solve(save_at_cycles=BLOCK)
        done = [k for k, c in enumerate(sol.cycles) if c is None or len(c.steps) == len(cycle)]
        s = sol.summary_variables
        parts.append(pd.DataFrame({"cap": np.asarray(s["Capacity [A.h]"], dtype=float)[:len(done)]}))
        if len(done) < BLOCK or parts[-1].cap.iloc[-1] < 0.8 * parts[0].cap.iloc[0]:
            break                                   # solver stopped, or 80 % reached
        model = model.set_initial_conditions_from(sol, inplace=False)
    d = pd.concat(parts, ignore_index=True).iloc[:n_cycles]
    d.insert(0, "Cycle", np.arange(1, len(d) + 1))
    cap = d.pop("cap")
    d["SOH [%]"] = 100 * cap / cap.iloc[0]
    return d


def empirical(n_cycles):
    """NmcRefit for the same cycle and pace (relative capacity after each cycle)."""
    t, soc = standard_profile(C_CHARGE, C_DISCHARGE)
    t, soc, temp, _ = add_rest(t, soc, np.full(len(t), TEMP_C), 365, TEMP_C)
    return 100 * predict_capacity("NMC", t, soc, temp, n_cycles)


def acceleration(soh):
    """Loss rate over the last tenth of the run / mean loss rate over the run."""
    loss = 100 - np.asarray(soh, dtype=float)
    n = len(loss)
    tail = max(2, n // 10)
    return ((loss[-1] - loss[-tail]) / (tail - 1)) / (loss[-1] / (n - 1))


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    d = run(n)
    d["NmcRefit SOH [%]"] = empirical(len(d))
    OUT.parent.mkdir(exist_ok=True)
    d.to_csv(OUT, index=False)
    print(d.iloc[np.unique(np.linspace(0, len(d) - 1, 13).astype(int))].round(2)
          .to_string(index=False))
    print(f"\ncycles simulated: {len(d)} (stops at 80 % or {n})")
    print(f"fade acceleration (last tenth / mean): O'Kane {acceleration(d['SOH [%]']):.2f}, "
          f"NmcRefit {acceleration(d['NmcRefit SOH [%]']):.2f}  (>1 = knee forming)")
