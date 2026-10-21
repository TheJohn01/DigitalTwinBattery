"""Field calibration of the NMC car first life: Smart e.d. fleet (Rücker et al. 2024).

The NMC ageing model is fitted to laboratory cells (calendar: LG M50; cycling: LG HG2 and
others). Cars in real use age more slowly. This script scales the model's two losses,

    field loss = a * calendar loss + b * cycling loss,

to the capacity tests of six Smart e.d. cars (data/rucker2024), each modelled with
ageing.ev_daily_profile at its own km per day (odometer / days), the Smart's 17.6 kWh pack,
0.157 kWh/km, 11 kW charging (0.55C), charged to 100 %, cells at 10 °C (about Berlin's annual
mean). a and b are non-negative least squares. Then it checks cars not used in the fit.

Also checks: the (unscaled) LFP car model against the TUM Tesla Model 3 (data/bilfinger2025);
the storage model against 21 home storage systems (Figgener et al. 2024); fast charging against
the ID.3 cell's highway test (Schreiber et al. 2025).

Run: python scripts/fit_field_ageing.py   (prints a, b and the checks; a few seconds)
"""
import numpy as np
import pandas as pd
from scipy.optimize import nnls

from battery_twin.ageing import (DC_FAST_C, EV_FIELD_SCALE, ev_daily_profile, ev_first_life,
                                 predict_capacity)
from battery_twin.constants import DATA_DIR

C_INIT = 40.76                  # Ah in the voltage window (Table 6)
PACK, CONS, CHARGE_C, CELL_C, TOP = 17.6, 0.157, 0.55, 10.0, 1.0
MIN_TEST_C = 12.0               # colder tests read low (higher resistance)


def losses(days, km, pack=PACK, cons=CONS, charge_c=CHARGE_C, cell_c=CELL_C, top=TOP):
    t, soc, temp = ev_daily_profile(km / days, pack, cons, charge_c, cell_c, top)
    cal, cyc = predict_capacity("NMC", t, soc, temp, int(round(days)), parts=True)
    return cal[-1], cyc[-1]


tests = pd.read_csv(DATA_DIR / "rucker2024" / "smart_capacity_tests.csv")
used = tests[tests.test_ambient_c >= MIN_TEST_C]
measured = 1 - used.capacity_window_ah.to_numpy() / C_INIT
A = np.array([losses(r.days, r.odometer_km) for r in used.itertuples()])
(a, b), _ = nnls(A, measured)
fit = A @ [a, b]
print(f"a (calendar) = {a:.2f}, b (cycling) = {b:.2f}; {len(used)} tests; RMSE "
      f"{100 * np.sqrt(np.mean((measured - fit) ** 2)):.2f} points "
      f"(unscaled {100 * np.sqrt(np.mean((measured - A.sum(axis=1)) ** 2)):.2f})")
for r, m, f in zip(used.itertuples(), measured, fit):
    print(f"  {r.vehicle:8s} {r.test:11s} day {r.days:6.0f}: lost {100 * m:4.1f} %, fit {100 * f:4.1f} %")

print("Checks (not in the fit): capacity measured / unscaled model / fitted model [%]")
for name, days, km, meas, args in [
        # Schreiber et al. 2025: VW ID.3 test car, 60,000 km in 3.5 years (charged to 80 %)
        ("VW ID.3", 3.5 * 365, 60000, 0.980, dict(pack=58, cons=0.16, charge_c=0.18, top=0.8)),
        # Rücker et al. 2024, Table D.15: Peugeot iOn (GS Yuasa LEV50), window 36.94 Ah
        ("iOn-2", 1005.8, 26331, 32.2 / 36.94, dict(pack=16, cons=0.176, charge_c=0.15)),
        ("iOn-1", 1159.5, 20658, 34.6 / 36.94, dict(pack=16, cons=0.176, charge_c=0.15))]:
    cal, cyc = losses(days, km, **args)
    print(f"  {name:8s} {100 * meas:5.1f} / {100 * (1 - cal - cyc):5.1f} / "
          f"{100 * (1 - a * cal - b * cyc):5.1f}")

# LFP: the TUM 2020 Tesla Model 3 (Bilfinger et al. 2025, data/bilfinger2025), measured at
# 1,000 and 80,100 km, about four years apart. LFP's car loss is almost all calendar. The LFP
# model is not scaled; this only checks it.
m3 = pd.read_csv(DATA_DIR / "bilfinger2025" / "model3_lfp_capacity.csv")
km_day = (m3.odometer_km.iloc[1] - m3.odometer_km.iloc[0]) / (4 * 365)
print(f"LFP Tesla Model 3: measured {100 * m3.capacity_bms_soc_ah.iloc[1] / m3.capacity_bms_soc_ah.iloc[0]:.1f} % "
      f"(BMS window) / {100 * m3.capacity_335_360v_ah.iloc[1] / m3.capacity_335_360v_ah.iloc[0]:.1f} % "
      f"(335-360 V) after about 4 years; model ({km_day:.0f} km/day, 0.2C, charged to 100 %): "
      + ", ".join(f"{100 * ev_first_life('LFP', 4.0, km_day, 55.1, 0.15, 0.2, c)[0][-1]:.1f} % "
                  f"at {c:g} °C" for c in (10, 15, 20)))

# Storage: 21 German home storage systems over up to 8 years (Figgener et al. 2024, Nature
# Energy 9, 1438): about 200 EFC a year, mostly shallow cycles, low C-rates, indoors. Mean
# capacity loss from the operating data (capacity tests): NMC 1.9 (3.2), LFP 2.0 (2.2)
# percentage points a year, with about 2 points of spread between systems. The storage model
# is not scaled; this checks its slope between years 2 and 8 on a home storage day:
# empty overnight, PV charge at 0.25C from 10 to 65 % from 9:00, discharge at 0.1C from 19:00.
H = 3600.0
t_hss = np.array([0, 9 * H, 9 * H + 0.55 / 0.25 * H, 19 * H, 19 * H + 0.55 / 0.1 * H, 24 * H])
soc_hss = np.array([0.10, 0.10, 0.65, 0.65, 0.10, 0.10])
print("Home storage, capacity loss per year between years 2 and 8 (model at 20-25 °C / field):")
for chem, field in (("NMC", "1.9-3.2"), ("LFP", "2.0-2.2")):
    slopes = []
    for cell_c in (20.0, 25.0):
        q = predict_capacity(chem, t_hss, soc_hss, np.full(len(t_hss), cell_c), 8 * 365)
        slopes.append(100 * (q[2 * 365 - 1] - q[-1]) / 6)
    print(f"  {chem}: {slopes[0]:.1f}-{slopes[1]:.1f} / {field} pp per year")

# Fast charging: Schreiber et al. 2025, VW ID.3 cell (LG E78, NMC), highway test at 20 °C.
# Each cycle: drive 100 -> 20 % (about 0.4C), DC fast charge 20 -> 80 % (DC_FAST_C), drive
# 80 -> 20 %, AC charge at 11 kW (0.18C) to 100 %. Measured: 92.2 % after 448 cycles
# (160,000 km, about 1,100 fast charges by the knee at 1,400 EFC). Not used in the fit above.
legs = [(0.8 / 0.4, 0.2), (60 / H, 0.2), (0.6 / DC_FAST_C, 0.8), (60 / H, 0.8),
        (0.6 / 0.4, 0.2), (60 / H, 0.2), (0.8 / 0.18, 1.0), (0.5, 1.0)]
t_hw, soc_hw = np.cumsum([0.0] + [h * H for h, _ in legs]), np.array([1.0] + [s for _, s in legs])
cal, cyc = predict_capacity("NMC", t_hw, soc_hw, np.full(len(t_hw), 20.0), 448, parts=True)
fa, fb = EV_FIELD_SCALE["NMC"]
print(f"Fast charging, ID.3 highway test after 448 cycles: measured 92.2 %, laboratory model "
      f"{100 * (1 - cal[-1] - cyc[-1]):.1f} %, with the field factors "
      f"{100 * (1 - fa * cal[-1] - fb * cyc[-1]):.1f} %")
