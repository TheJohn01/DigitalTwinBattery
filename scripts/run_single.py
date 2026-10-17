"""Run one battery test from the command line."""
from battery_twin.chemistry import run_battery_test

CHEMISTRY = "NMC"   # NMC, LFP, NCA or Na-ion

result = run_battery_test(CHEMISTRY)       # default test: 0.3C charge, 1C discharge, 20 °C
meta = result["meta"]
print(f"Capacity after {meta['cycles_completed']:,} cycles: "
      f"{result['cycles']['SOH [%]'].iloc[-1]:.1f} %")
print(f"Cycles until 80 %: {meta['cycles_to_80pct']:,.0f}")
print(f"Mean cell temperature: {meta['mean_cell_temperature_c']:.1f} °C")
for note in meta["ageing_warnings"]:
    print("Outside the ageing data:", note)
