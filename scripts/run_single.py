"""Run one battery test from the command line."""
from battery_twin.chemistry import run_battery_test

CHEMISTRY = "NMC"   # NMC, LFP, NCA or Na-ion

result = run_battery_test(CHEMISTRY, "SPMe", c_charge=0.3, c_discharge=1.0,
                          n_cycles=1000, ambient_c=20.0)
meta = result["meta"]
print(f"Capacity after 1,000 cycles: {result['cycles']['SOH [%]'].iloc[-1]:.1f} %")
print(f"Cycles until 80 %: {meta['cycles_to_80pct']:,.0f}")
print(f"Mean cell temperature: {meta['mean_cell_temperature_c']:.1f} °C")
for note in meta["ageing_warnings"]:
    print("Outside the ageing data:", note)
