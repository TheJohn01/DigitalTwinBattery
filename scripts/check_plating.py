"""Lithium plating in the NMC physics model against Luh & Blank's cold and fast-charge tests.

The detailed NMC model (DFN) has partially reversible lithium plating with O'Kane et al.'s
(2022) parameters for the LG M50 (chemistry.PLATING_KEYS). Luh & Blank (2024) cycled LG HG2
cells at 0-40 °C with 0.33-1.67C charging (data/published_ageing.csv): cycles to 80 % fell
from about 600 at 40 °C to 41 at 0 °C and 1.67C. The cells differ (HG2 vs M50), so only the
trend is compared: each test is simulated for three cycles in its chamber, and the plating
loss that stays after a full cycle (cycle 3 minus cycle 2) is ranked against the measured
fade rate, 1 / cycles to 80 %. The size of the loss is printed next to the measured fade.

Run:  python scripts/check_plating.py     (about 2 minutes; writes results/plating_check.csv)
"""
from pathlib import Path

import pandas as pd
import pybamm
from scipy.stats import spearmanr

from battery_twin.chemistry import CALIBRATED_H_COOLING, build_model
from battery_twin.constants import DATA_DIR

TESTS = pd.read_csv(DATA_DIR / "published_ageing.csv").query("source.str.startswith('LuhBlank')",
                                                              engine="python")


def plating_per_cycle(temp_c, c_charge, c_discharge):
    """Plating capacity loss [Ah] kept after one full cycle (start of cycle 3 - cycle 2)."""
    model, pv, _ = build_model("NMC", "DFN", temp_c, CALIBRATED_H_COOLING)
    cycle = (f"Discharge at {c_discharge:g}C until 2.5 V", "Rest for 5 minutes",
             f"Charge at {c_charge:g}C until 4.2 V", "Hold at 4.2 V until C/20",
             "Rest for 5 minutes")
    sol = pybamm.Simulation(model, parameter_values=pv,
                            experiment=pybamm.Experiment([cycle] * 3)).solve(initial_soc=1)
    loss = [c["Loss of capacity to negative lithium plating [A.h]"].entries[0] for c in sol.cycles]
    return float(loss[2] - loss[1])


def main():
    rows = []
    for r in TESTS.itertuples():
        per_cycle = plating_per_cycle(r.temp_c, r.c_charge, r.c_discharge)
        rows.append({"Chamber [°C]": r.temp_c, "Charge [C]": r.c_charge,
                     "Discharge [C]": r.c_discharge, "Measured cycles to 80 %": r.efc,
                     "Measured fade [% per cycle]": 20 / r.efc,
                     "Model plating loss [% per cycle]": 100 * per_cycle / 5.0})
    out = pd.DataFrame(rows)
    rho = spearmanr(out["Model plating loss [% per cycle]"], out["Measured fade [% per cycle]"])
    Path("results").mkdir(exist_ok=True)
    out.to_csv("results/plating_check.csv", index=False)
    pd.set_option("display.width", 160)
    print(out.round(5).to_string(index=False))
    share = (out["Model plating loss [% per cycle]"] / out["Measured fade [% per cycle]"]).median()
    print(f"\nRank correlation with the measured fade: {rho.statistic:.2f} (p = {rho.pvalue:.1g})")
    print(f"Model plating loss / measured fade, median: {share:.4f}")
    return out, rho.statistic, share


if __name__ == "__main__":
    main()
