"""The SOC filter and the rest-to-rest capacity (battery_twin.estimator) on a real home storage
system: Figgener et al. (2024), system 10, the whole of 2022 (data/figgener2024/README.md).

The system is one of the paper's 'MediumNMC' products (8.8 kWh, 46.8 V nominal, 3 kW): a
pack voltage of 44-52 V on a sloping curve, so 13 NMC cells in series (mean cell voltage =
pack voltage / 13). It charges from PV by day, discharges at night and rests empty until the
sun comes up, so it has the full and empty states and the rests the method needs.

Reference SOC, from the data alone: a day runs from an empty rest (at least 30 min under
0.5 A, pack under 46.5 V) to the next one. The charge counted from the empty rest to the first
full point (pack at least 51.6 V, current under 5 A) is that day's usable capacity; the SOC is
the charge counted from the empty rest over that capacity (0 when empty, 1 when full).

As a battery management system would: the open-circuit voltage curve (2 % SOC bins), the
resistance R0 and one RC element are fitted on January-March (least squares; tau from a
grid); the capacity is the median of those months' days. The filter then runs on each day of
April-December from a wrong 50 %; it sees only the current and the cell voltage. Separately,
the rest-to-rest capacity method runs over April-December as one record.

Run:  python scripts/validate_estimator_storage.py          (uses data/figgener2024)
      python scripts/validate_estimator_storage.py "<folder with the monthly System_ID_10 CSVs>"
      (the second form first rebuilds data/figgener2024/system10_2022_1min.csv.gz)
"""
import glob
import sys

import numpy as np
import pandas as pd

from battery_twin.constants import DATA_DIR
from battery_twin.estimator import ekf, rc_current, rest_capacities

FILE = DATA_DIR / "figgener2024" / "system10_2022_1min.csv.gz"
CELLS_IN_SERIES = 13
TRAIN_MONTHS = (1, 2, 3)


def extract(raw_dir):
    """One-minute means of the 1 s monthly files (current: + = charging, as in the data)."""
    out = []
    for f in sorted(glob.glob(f"{raw_dir}/*_System_ID_10.csv")):
        d = pd.read_csv(f, usecols=["Time", "V_in_V", "I_in_A", "T_Bat_in_C"])
        d["Time"] = pd.to_datetime(d.Time, format="%d-%b-%Y %H:%M:%S")
        g = d.set_index("Time").resample("1min")
        out.append(pd.DataFrame({"current_a": g.I_in_A.mean(), "pack_voltage_v": g.V_in_V.mean(),
                                 "housing_temp_c": g.T_Bat_in_C.mean()}))
    m = pd.concat(out)
    m.index = m.index.strftime("%Y-%m-%d %H:%M")
    m.round({"current_a": 2, "pack_voltage_v": 3, "housing_temp_c": 1}).to_csv(
        FILE, index_label="time")


def load():
    m = pd.read_csv(FILE, parse_dates=["time"]).set_index("time").interpolate(limit=30)
    i = -m.current_a.fillna(0.0).to_numpy()                 # + = discharge, as in the filter
    v = m.pack_voltage_v.ffill().to_numpy() / CELLS_IN_SERIES
    return m.index, 60.0 * np.arange(len(m)), i, v


def days(t, i, v):
    """[(empty rest end, first full point, next empty rest end)] as sample indices."""
    rest = np.abs(i) < 0.5
    edges = np.flatnonzero(np.diff(rest.astype(int))) + 1
    starts, ends = np.r_[0, edges], np.r_[edges, len(i)]
    empties = [b - 1 for a, b in zip(starts, ends)
               if rest[a] and b - a >= 30 and v[b - 1] < 46.5 / CELLS_IN_SERIES]
    full = np.flatnonzero((v >= 51.6 / CELLS_IN_SERIES) & (np.abs(i) < 5))
    out = []
    for a, b in zip(empties[:-1], empties[1:]):
        f = full[(full > a) & (full < b)]
        if len(f):
            out.append((a, f[0], b))
    return out


def fit_cell(t, i, v, ah_out, train):
    """OCV curve, R0, R1 and tau from the empty-to-full charges of the training days."""
    bins = np.linspace(0, 1, 51)
    best = None
    for tau in (60, 300, 900, 1800):
        rows, ys = [], []
        for a, f, _ in train:
            k = np.arange(a, f + 1)
            soc = (ah_out[a] - ah_out[k]) / (ah_out[a] - ah_out[f])
            onehot = np.zeros((len(k), 50))
            onehot[np.arange(len(k)), np.clip(np.digitize(soc, bins) - 1, 0, 49)] = 1
            rows.append(np.column_stack([onehot, -i[k], -rc_current(t[k] - t[a], i[k], tau)]))
            ys.append(v[k])
        A, y = np.vstack(rows), np.concatenate(ys)
        x, *_ = np.linalg.lstsq(A, y, rcond=None)
        res = float(np.sum((A @ x - y) ** 2))
        if best is None or res < best[0]:
            best = (res, x, tau)
    _, x, tau = best
    return 0.5 * (bins[1:] + bins[:-1]), np.maximum.accumulate(x[:50]), x[50], x[51], tau


def evaluate():
    index, t, i, v = load()
    ah_out = np.cumsum(i) / 60.0
    month = index.month.to_numpy()
    all_days = days(t, i, v)
    train = [d for d in all_days if month[d[0]] in TRAIN_MONTHS]
    test = [d for d in all_days if month[d[0]] not in TRAIN_MONTHS]
    ocv_soc, ocv_v, r0, r1, tau = fit_cell(t, i, v, ah_out, train)
    q0 = float(np.median([ah_out[a] - ah_out[f] for a, f, _ in train]))
    rms, worst, at_empty = [], [], []
    for a, f, b in test:
        k = np.arange(a, b + 1)
        truth = np.clip((ah_out[a] - ah_out[k]) / (ah_out[a] - ah_out[f]), 0, 1)
        soc, _, _ = ekf(t[k] - t[a], i[k], v[k], ocv_soc, ocv_v, q0, r0, r1, tau, soc0=0.5)
        err = 100 * (soc - truth)[k >= f]           # after the filter has seen a full charge
        rms.append(np.sqrt(np.mean(err ** 2)))
        worst.append(np.abs(err).max())
        at_empty.append(abs(err[-1]))
    k = np.flatnonzero(~np.isin(month, TRAIN_MONTHS))
    found = rest_capacities(t[k] - t[k[0]], i[k], v[k], ocv_soc, ocv_v, q0)
    rest_q = pd.Series([q for _, q in found], index=index[k][[j for j, _ in found]])
    counted = pd.Series([ah_out[a] - ah_out[f] for a, f, _ in test], index=index[[a for a, _, _ in test]])
    monthly = pd.DataFrame({"rest-to-rest [Ah]": rest_q.resample("MS").median(),
                            "counted empty to full [Ah]": counted.resample("MS").median()})
    return {
        "training capacity [Ah]": q0,
        "R0 per cell [mOhm]": 1000 * r0,
        "test days": len(test),
        "SOC error after the first full charge, RMS, median of days [%-points]": float(np.median(rms)),
        "SOC error RMS, 95th percentile of days [%-points]": float(np.percentile(rms, 95)),
        "largest SOC error in a day, median of days [%-points]": float(np.median(worst)),
        "SOC error at the next empty rest, median [%-points]": float(np.median(at_empty)),
        "rest-to-rest capacity pairs": len(found),
        "rest-to-rest capacity, median [Ah]": float(rest_q.median()),
        "counted capacity, median of test days [Ah]": float(counted.median()),
    }, monthly


if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract(sys.argv[1])
    summary, monthly = evaluate()
    for k, val in summary.items():
        print(f"{k}: {val:.1f}" if isinstance(val, float) else f"{k}: {val}")
    print(monthly.round(1).to_string())
