"""Capacity fade versus ambient temperature, for every chemistry."""
import matplotlib.pyplot as plt

from battery_twin.chemistry import CHEMISTRIES, run_battery_test

fig, axes = plt.subplots(1, len(CHEMISTRIES), figsize=(14, 4), sharey=True)
for ax, chemistry in zip(axes, CHEMISTRIES):
    for ambient in [15, 25, 35, 45]:
        r = run_battery_test(chemistry, "SPMe", c_charge=0.5, c_discharge=1.0,
                             n_cycles=2000, ambient_c=ambient)
        ax.plot(r["cycles"]["Cycle"], r["cycles"]["SOH [%]"], label=f"{ambient} °C")
    ax.set(title=chemistry, xlabel="Cycle")
    ax.grid(True)
axes[0].set_ylabel("Capacity [%]")
axes[0].legend()
plt.tight_layout()
plt.show()
