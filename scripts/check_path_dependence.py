"""How much does it matter that the projection repeats the new cell's cycle? (path dependence)

The dashboard drives the empirical ageing model with the last simulated cycle of the NEW cell
for the whole life (README 10.2, "Representative cycle"). As the cell ages its resistance
rises, so it warms more and reaches its voltage limits earlier, which changes the stress
factors. Karger et al. (2022, J. Energy Storage 52, 104718) update the stress factors along
the path in the same class of semi-empirical model; Röder & Ramasubramanian (2022, Energy
Technol.) review when the order of loads matters.

Here, for each chemistry at the dashboard's default test (0.3C charge, 1C discharge, 20 °C,
forced air, one cycle a day): every STEP of capacity lost, the cycle is simulated again with
the aged cell (chemistry.run_aged_window: smaller electrodes, so higher resistance), and the
empirical model goes on with that cycle from the calendar and cycling losses reached (each
matched on the new cycle's own loss curve; ageing.predict_path, also the dashboard's
Advanced option). Cycles to 80 % are compared with the single-cycle projection.

Run:  python scripts/check_path_dependence.py     (about 10 minutes)
"""
import numpy as np
import pandas as pd

from battery_twin.ageing import add_rest, cycles_to, predict_capacity, predict_path
from battery_twin.chemistry import (COOLING_OPTIONS, DEFAULT_AMBIENT_C, DEFAULT_C_CHARGE,
                                    DEFAULT_C_DISCHARGE, choose_model, run_aged_window)

STEP = 0.05                  # re-simulate every 5 points of capacity lost
END = 0.80
HORIZON = 20000
H = COOLING_OPTIONS["Forced air / passive"]["h"]


def ageing_cycle(chem, soh):
    """The repeating cycle (with the day's rest) of a cell at capacity fraction soh."""
    model = choose_model(chem, DEFAULT_C_CHARGE)
    p = run_aged_window(chem, model, DEFAULT_C_CHARGE, DEFAULT_C_DISCHARGE, DEFAULT_AMBIENT_C,
                        H, soh)["profile"]
    t, soc, temp, _ = add_rest(p["Time [s]"], p["SOC"], p["Temperature [°C]"], 365,
                               DEFAULT_AMBIENT_C)
    return t, soc, temp


def piecewise(chem):
    """Cycles to END with the cycle re-simulated every STEP of capacity lost
    (ageing.predict_path), and with the new cell's cycle alone (the dashboard's default)."""
    single = cycles_to(predict_capacity(chem, *ageing_cycle(chem, 1.0), HORIZON), END)
    return cycles_to(predict_path(chem, lambda soh: ageing_cycle(chem, soh), HORIZON, STEP),
                     END), single


if __name__ == "__main__":
    rows = []
    for chem in ("NMC", "LFP", "NCA", "Na-ion"):
        path, single = piecewise(chem)
        rows.append({"chemistry": chem, "single cycle (dashboard)": single,
                     f"re-simulated every {100 * STEP:.0f} points": path,
                     "ratio": path / single})
        print(rows[-1])
    print(pd.DataFrame(rows).round(3).to_string(index=False))
