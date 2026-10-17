"""Run a battery test and save the results as CSV files in ./results."""
from pathlib import Path

from battery_twin.chemistry import run_battery_test

out = Path("results")
out.mkdir(exist_ok=True)
result = run_battery_test("NMC")      # the default test, as in run_single.py
result["cycles"].to_csv(out / "capacity_per_cycle.csv", index=False)
result["series"].to_csv(out / "voltage_temperature_series.csv", index=False)
result["efficiency"].to_csv(out / "efficiency.csv", index=False)
print(f"Saved 3 CSV files in {out.resolve()}")
