"""How much the assumed values of the LFP (BYD Blade) parameter set move the dashboard's
physics results: each assumption changed on its own, the fitted values kept.

Output per case, for the dashboard's default cycle (0.3C charge, 1C discharge, 20 °C,
forced air h = 25 W/m2K, SPMe): 1C discharge capacity, cell energy efficiency, peak cell
temperature. Writes results/blade_sensitivity.csv.
Run: python scripts/sensitivity_blade.py   (about a minute)
"""
from pathlib import Path

import pandas as pd

from battery_twin import lfp_blade_params as blade
from battery_twin.chemistry import CHEMISTRIES, run_simulation

blade_cell = blade.CELLS["Blade"]
base = {"additives": blade.CATHODE_ADDITIVES, "cathode_kg": blade_cell["cathode_kg"],
        "graphite_kg": blade_cell["graphite_kg"], "decay": blade.HYSTERESIS_DECAY}
mass_ratio = 0.3 / 2.7                        # cell mass 2.7 +/- 0.3 kg (Gorsch Table 1)

cases = [
    ("Default", {}, {}),
    ("Cathode binder + carbon 2 % (porosity 0.21)", {"additives": 0.02}, {}),
    ("Cathode binder + carbon 10 % (porosity 0.13)", {"additives": 0.10}, {}),
    ("Cell mass 2.4 kg (electrode masses -11 %)",
     {"cathode_kg": base["cathode_kg"] * (1 - mass_ratio),
      "graphite_kg": base["graphite_kg"] * (1 - mass_ratio)}, {}),
    ("Cell mass 3.0 kg (electrode masses +11 %)",
     {"cathode_kg": base["cathode_kg"] * (1 + mass_ratio),
      "graphite_kg": base["graphite_kg"] * (1 + mass_ratio)}, {}),
    ("Separator porosity 0.35", {}, {"Separator porosity": 0.35}),
    ("Separator porosity 0.55", {}, {"Separator porosity": 0.55}),
    ("Hysteresis switch over ~15 % of capacity (decay 30)", {"decay": 30.0}, {}),
    ("Hysteresis switch over ~1.5 % of capacity (decay 300)", {"decay": 300.0}, {}),
]


def apply(change):
    values = dict(base, **change)
    blade.CATHODE_ADDITIVES = values["additives"]
    blade.HYSTERESIS_DECAY = values["decay"]
    blade_cell["cathode_kg"], blade_cell["graphite_kg"] = values["cathode_kg"], values["graphite_kg"]
    blade.clear_cache()


rows = []
updates = CHEMISTRIES["LFP"]["updates"]
for name, change, pv_change in cases:
    apply(change)
    CHEMISTRIES["LFP"]["updates"] = dict(updates, **pv_change)
    r = run_simulation("LFP", "SPMe", 0.3, 1.0, n_cycles=2, ambient_c=20.0, h_cooling=25.0)
    rows.append({"Case": name, "1C capacity [Ah]": r["meta"]["cell_capacity_ah"],
                 "Energy efficiency [%]": r["efficiency"]["Energy efficiency [%]"].iloc[-1],
                 "Peak temperature [°C]": r["cycles"]["Max temperature [°C]"].max()})
apply({})
CHEMISTRIES["LFP"]["updates"] = updates

df = pd.DataFrame(rows)
print(df.round(2).to_string(index=False))
Path("results").mkdir(exist_ok=True)
df.to_csv("results/blade_sensitivity.csv", index=False)
