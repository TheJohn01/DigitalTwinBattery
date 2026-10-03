"""Capacity fade versus charge rate (NMC). Above 2C the detailed DFN model is used."""
import matplotlib.pyplot as plt

from battery_twin.chemistry import run_battery_test

plt.figure(figsize=(8, 4))
for c_rate in [0.3, 0.5, 1.0, 2.0, 3.0]:
    model = "DFN" if c_rate > 2 else "SPMe"
    r = run_battery_test("NMC", model, c_charge=c_rate, c_discharge=1.0, n_cycles=2000)
    plt.plot(r["cycles"]["Cycle"], r["cycles"]["SOH [%]"], label=f"Charge {c_rate:g}C")
    print(f"{c_rate:g}C: outside ageing data -> {r['meta']['ageing_warnings']}")
plt.xlabel("Cycle")
plt.ylabel("Capacity [%]")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()
