"""The SOC filter (battery_twin.estimator) on a real car: the TUM Tesla Model 3 (LFP), fully
charged at 2.8 A in 2021 (1,000 km) and in 2025 (80,100 km); Bilfinger et al. 2025, see
data/bilfinger2025/README.md.

As a battery management system would: the open-circuit voltage curve and the capacity come
from the 2021 charge (the car nearly new). On the 2025 charge the filter starts from a wrong
50 % and still assumes the 2021 capacity; it only sees the current and the mean cell voltage.
Truth: the charge counted back from full at the end, over that charge's own capacity (charged
Ah / BMS SOC window). The charges are slow (0.017C), so the voltage is close to the
open-circuit voltage, and both are charges, so hysteresis does not enter.

Run:  python scripts/validate_estimator_tesla.py                 (uses data/bilfinger2025)
      python scripts/validate_estimator_tesla.py "<folder with the two .feather files>"
      (the second form first rebuilds data/bilfinger2025/charge_<year>.csv, one row a minute)
"""
import sys

import numpy as np
import pandas as pd

from battery_twin.constants import DATA_DIR
from battery_twin.estimator import ekf

DATA = DATA_DIR / "bilfinger2025"
YEARS = (2021, 2025)


def extract(raw_dir):
    """charge_<year>.csv from the TUM .feather files: one row a minute."""
    for year in YEARS:
        d = pd.read_feather(f"{raw_dir}/Tesla_Model_3_JB_6A_CEE7_FTM_{year}.feather")
        out = pd.DataFrame({
            "time_s": d.time_s - d.time_s.iloc[0],
            "current_a": d.I,                                # + = charging
            "cell_voltage_v": d[[f"cell_voltage_{k}" for k in range(106)]].mean(axis=1),
            "soc_bms_pct": d.SOC,
            "ah_charged": d.Q})
        out = out.groupby(out.time_s // 60).last()           # the last sample of each minute
        out.round(5).to_csv(DATA / f"charge_{year}.csv", index=False)


def load(year):
    d = pd.read_csv(DATA / f"charge_{year}.csv")
    q = d.ah_charged.to_numpy()
    capacity = q[-1] / (1 - d.soc_bms_pct.iloc[0] / 100)     # Ah over the BMS window
    truth = 1 - (q[-1] - q) / capacity                         # full at the end
    return d, capacity, truth


def evaluate():
    new, q_new, soc_new = load(2021)
    bins = np.linspace(0, 1, 51)                     # OCV curve of the new pack, 2 % bins
    curve = pd.DataFrame({"soc": soc_new, "v": new.cell_voltage_v}).groupby(
        np.digitize(soc_new, bins)).mean()
    ocv_soc, ocv_v = curve.soc.to_numpy(), np.maximum.accumulate(curve.v.to_numpy())
    rows = {}
    for year in YEARS:
        d, capacity, truth = load(year)
        t, i = d.time_s.to_numpy(), d.current_a.to_numpy()
        soc, _, _ = ekf(t, -i, d.cell_voltage_v.to_numpy(), ocv_soc, ocv_v, q_new,
                        r0=1e-3, soc0=0.5)
        err = 100 * (soc - truth)
        counted = truth[0] + np.concatenate(
            [[0.0], np.cumsum(0.5 * (i[1:] + i[:-1]) * np.diff(t))]) / 3600 / q_new
        # capacity from the voltage at the start (SOC read off the 2021 curve) to full
        start = np.interp(d.cell_voltage_v.iloc[0], ocv_v, ocv_soc)
        rows[year] = {
            "capacity [Ah]": capacity,
            "SOC error RMS [%-points]": float(np.sqrt(np.mean(err ** 2))),
            "SOC error max after 10 h [%-points]": float(np.abs(err[t > 36000]).max()),
            "SOC error at full [%-points]": float(err[-1]),
            "counting with the 2021 capacity, error at full [%-points]":
                float(100 * (counted[-1] - truth[-1])),
            "BMS SOC error RMS [%-points]":
                float(np.sqrt(np.mean((d.soc_bms_pct.to_numpy() - 100 * truth) ** 2))),
            "capacity from voltage to full [Ah]": float(d.ah_charged.iloc[-1] / (1 - start)),
        }
    return pd.DataFrame(rows)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract(sys.argv[1])
    pd.set_option("display.width", 120)
    print(evaluate().round(2).to_string())
