"""The SOC filter (battery_twin.estimator.ekf) on electric-car drive cycles at six temperatures:
an LG 18650HG2 cell (NMC / graphite, 3 Ah) driven with the UDDS, HWFET, LA92 and US06 power
profiles of a compact car at 40, 25, 10, 0, -10 and -20 °C (Kollmeyer 2020;
data/kollmeyer2020/README.md).

Each drive cycle starts full and runs until about 95 % of the 1C capacity is used. Reference
SOC = 1 - charge out / C/20 capacity at that temperature. As a battery management system
would, at each temperature the open-circuit voltage is the mean of the C/20 discharge and
charge curves, and R0, R1 and tau are fitted (least squares, tau from a grid) on the UDDS
cycle only. The filter then runs on the other three cycles from a wrong 50 %, seeing only the
current and the voltage. The error is taken once 10 % of the capacity is used (the filter has
had time to converge) and at the end of the cycle.

Run:  python scripts/validate_estimator_drive.py          (uses data/kollmeyer2020)
      python scripts/validate_estimator_drive.py "<unzipped Mendeley b5mj79w5w9 folder>"
      (the second form first rebuilds the data files from the cycler's CSV files)
"""
import glob
import sys

import numpy as np
import pandas as pd

from battery_twin.constants import DATA_DIR
from battery_twin.estimator import ekf, rc_current

FOLDER = DATA_DIR / "kollmeyer2020"
TEMPS = {"40degC": 40, "25degC": 25, "10degC": 10, "0degC": 0, "n10degC": -10, "n20degC": -20}
CYCLES = ("UDDS", "HWFET", "LA92", "US06")
TRAIN = "UDDS"


def read_cycler(path):
    """Seconds, current [A] (+ = charge, as logged), voltage [V], Ah and status of a CSV."""
    with open(path, errors="replace") as f:
        skip = next(n for n, line in enumerate(f) if line.startswith("Time Stamp"))
    d = pd.read_csv(path, skiprows=[*range(skip), skip + 1], usecols=[2, 3, 8, 9, 11],
                    names=["status", "prog", "v", "i", "ah"], header=0, encoding_errors="replace")
    hms = d.prog.str.split(":", expand=True).astype(float)
    d["t"] = 3600 * hms[0] + 60 * hms[1] + hms[2]
    return d


def extract(raw_dir):
    ocv, drive = [], []
    for folder, temp in TEMPS.items():
        d = read_cycler(glob.glob(f"{raw_dir}/{folder}/*_C20DisCh.csv")[0])
        dis, cha = d[d.status == "DCH"], d[d.status == "CHA"]
        q20 = -dis.ah.min()
        soc = np.linspace(0, 1, 101)
        v_dis = np.interp(soc, 1 - (-dis.ah.to_numpy() / q20)[::-1], dis.v.to_numpy()[::-1])
        q_cha = cha.ah - cha.ah.iloc[0]
        v_cha = np.interp(soc, (q_cha / q_cha.max()).to_numpy(), cha.v.to_numpy())
        ocv.append(pd.DataFrame({"temp_c": temp, "soc": soc, "v_dis": v_dis, "v_cha": v_cha,
                                 "q20_ah": q20}))
        for name in CYCLES:
            files = glob.glob(f"{raw_dir}/{folder}/*_{name}.csv")
            if not files:
                continue
            c = read_cycler(files[0])
            c = c[c.status == "TABLE"]                       # the drive cycle itself
            if len(c) < 6000:            # under 10 minutes: the 25 °C HWFET file has no cycle
                continue
            g = c.groupby((c.t - c.t.iloc[0]).floordiv(1.0))  # one-second means
            drive.append(pd.DataFrame({"temp_c": temp, "cycle": name, "t": g.t.first() - c.t.iloc[0],
                                       "i": g.i.mean(), "v": g.v.mean(), "ah": g.ah.last()}
                                      ).dropna())            # a few unreadable cycler lines
    FOLDER.mkdir(exist_ok=True)
    pd.concat(ocv).round(5).to_csv(FOLDER / "hg2_ocv.csv", index=False)
    pd.concat(drive).round({"t": 1, "i": 4, "v": 4, "ah": 5}).to_csv(
        FOLDER / "hg2_drive_1s.csv.gz", index=False)


def fit_r(t, i, v, ocv_soc, ocv_v, soc):
    """R0, R1, tau of v = OCV(soc) - R0 i - R1 i_rc (i + = discharge), least squares."""
    best = None
    for tau in (5, 10, 20, 40, 80, 160):
        A = np.column_stack([-i, -rc_current(t, i, tau)])
        y = v - np.interp(soc, ocv_soc, ocv_v)
        x, *_ = np.linalg.lstsq(A, y, rcond=None)
        res = float(np.sum((A @ x - y) ** 2))
        if best is None or res < best[0]:
            best = (res, max(x[0], 1e-4), max(x[1], 0.0), tau)
    return best[1:]


def evaluate():
    ocv = pd.read_csv(FOLDER / "hg2_ocv.csv")
    drive = pd.read_csv(FOLDER / "hg2_drive_1s.csv.gz")
    rows = []
    for temp, o in ocv.groupby("temp_c", sort=False):
        q20 = float(o.q20_ah.iloc[0])
        ocv_soc, ocv_v = o.soc.to_numpy(), 0.5 * (o.v_dis + o.v_cha).to_numpy()
        cycles = {n: g for n, g in drive[drive.temp_c == temp].groupby("cycle")}
        g = cycles[TRAIN]
        t, i, v = g.t.to_numpy(), -g.i.to_numpy(), g.v.to_numpy()
        r0, r1, tau = fit_r(t, i, v, ocv_soc, ocv_v, 1 + g.ah.to_numpy() / q20)
        for name, g in cycles.items():
            if name == TRAIN:
                continue
            t, i, v = g.t.to_numpy(), -g.i.to_numpy(), g.v.to_numpy()
            truth = 1 + g.ah.to_numpy() / q20
            soc, _, _ = ekf(t, i, v, ocv_soc, ocv_v, q20, r0, r1, tau, soc0=0.5)
            err = 100 * (soc - truth)[truth < 0.9]
            rows.append({"temp_c": temp, "cycle": name, "R0 [mOhm]": 1000 * r0,
                         "RMS error after 10 % used [%-points]": float(np.sqrt(np.mean(err ** 2))),
                         "error at the end [%-points]": float(err[-1]),
                         "SOC at the end [%]": 100 * float(truth[-1])})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract(sys.argv[1])
    out = evaluate()
    pd.set_option("display.width", 160)
    print(out.round(1).to_string(index=False))
    print(out.groupby("temp_c", sort=False)["RMS error after 10 % used [%-points]"].median()
          .round(1).to_string())
