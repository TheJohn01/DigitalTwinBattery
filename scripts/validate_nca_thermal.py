"""NCA physics model (Samsung INR21700-50E, Schmitt 2023) against measured self-heating and
capacity of the same cell: two 50E cells of batch 17 of the University of Wuppertal tests
(data/popp2024/README.md).

Each cell was charged CC-CV at 0.5C (2.45 A), discharged at C/5 (0.98 A) to 2.5 V, charged
again and put through an HPPC test (1C pulses, 0.5C discharges in 10 % steps), then charged at
0.75C (3.67 A), in a 25 °C chamber; the thermocouple sits on the middle of the can. The cells'
holder sets the cooling, so h is fitted once, to the mean rise over the first 0.5C charge, and
the other steps are predictions of the model's heat. The model's can temperature is compared
(core and can, chemistry.R_CORE_21700); rise = end of the step minus its start.

Run:  python scripts/validate_nca_thermal.py          (about 1 minute; uses data/popp2024)
      python scripts/validate_nca_thermal.py "<folder with the Report_*_MCU*.csv files>"
      (the second form first rebuilds data/popp2024/samsung50e_steps.csv from the 1 kHz files)
"""
import glob
import sys

import numpy as np
import pandas as pd
import pybamm

from battery_twin.chemistry import build_model
from battery_twin.constants import DATA_DIR

STEPS = DATA_DIR / "popp2024" / "samsung50e_steps.csv"
# the steps compared: (name, current in A (+ = charge), SOC at the start)
CASES = [("0.5C charge from empty", 2.45, 0.0),
         ("C/5 discharge from full", -0.98, 1.0),
         ("0.75C charge from empty", 3.67, 0.0)]


def one_second(path):
    """One-second means of time, current, voltage and can temperature from a 1 kHz report."""
    parts = []
    # header names contain commas, so columns are taken by position: 0 time, 4 I, 10 T, 11 U
    for c in pd.read_csv(path, header=None, skiprows=1, usecols=[0, 4, 10, 11],
                         names=["time", "i", "temp", "u"], chunksize=2_000_000, dtype={0: str}):
        c = c.dropna(subset=["u"])
        parts.append(c.groupby(c.time.str[:19], sort=False)[["i", "temp", "u"]].mean())
    d = pd.concat(parts)
    return d.groupby(level=0, sort=False).mean()


def extract(raw_dir):
    """Every constant-current step longer than 5 minutes, per cell."""
    rows = []
    for path in sorted(glob.glob(f"{raw_dir}/Report_*_MCU*.csv")):
        d = one_second(path)
        i = d.i.to_numpy()
        level = np.select([i > 3.3, i > 2.2, i < -4, i < -2.2, i < -0.5],
                          [3.67, 2.45, -4.9, -2.45, -0.98], 0.0)
        step = np.cumsum(np.r_[True, level[1:] != level[:-1]])
        for _, k in pd.Series(range(len(i))).groupby(step):
            k = k.to_numpy()
            if len(k) > 300 and level[k[0]] != 0:
                rows.append({"cell": path.split("_MCU")[1][0], "start": d.index[k[0]],
                             "current_a": round(float(i[k].mean()), 3),
                             "ah": round(float(np.sum(i[k]) / 3600), 4),
                             "v_start": round(float(d.u.iloc[k[0]]), 4),
                             "v_end": round(float(d.u.iloc[k[-1]]), 4),
                             "t_start_c": d.temp.iloc[k[0]], "t_end_c": d.temp.iloc[k[-1]]})
    STEPS.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(STEPS, index=False)


def measured():
    """Rise [K] and charge moved [Ah] of the compared steps, one row per cell and step."""
    s = pd.read_csv(STEPS)
    s["rise"] = s.t_end_c - s.t_start_c
    rows = []
    for name, current, soc0 in CASES:
        start_v = (s.v_start < 3.1) if soc0 == 0 else (s.v_start > 4.1)
        full = (s.v_end > 4.19) if current > 0 else (s.v_end < 2.52)
        m = s[((s.current_a - current).abs() < 0.05 * abs(current)) & start_v & full]
        first = m.groupby("cell").head(1)                  # the first such step of each cell
        rows += [{"case": name, "cell": r.cell, "rise": r.rise, "ah": abs(r.ah)}
                 for r in first.itertuples()]
    return pd.DataFrame(rows)


def simulate(current, soc0, h):
    """(can temperature rise [K], charge moved [Ah]) of one step from 25 °C."""
    model, pv, _ = build_model("NCA", "SPMe", 25.0, h)
    limit = "until 4.2 V" if current > 0 else "until 2.5 V"
    word = "Charge" if current > 0 else "Discharge"
    sol = pybamm.Simulation(model, parameter_values=pv, experiment=pybamm.Experiment(
        [f"{word} at {abs(current)} A {limit}"])).solve(initial_soc=soc0)
    can = sol["Surface temperature [K]"].entries
    q = sol["Discharge capacity [A.h]"].entries
    return float(can[-1] - can[0]), float(abs(q[-1] - q[0]))


def fit_h(target, low=2.0, high=60.0):
    for _ in range(10):
        h = 0.5 * (low + high)
        if simulate(2.45, 0.0, h)[0] > target:
            low = h
        else:
            high = h
    return 0.5 * (low + high)


def main():
    m = measured()
    mean = m.groupby("case", sort=False)[["rise", "ah"]].mean()
    h = fit_h(mean.loc[CASES[0][0], "rise"])
    rows = []
    for name, current, soc0 in CASES:
        rise, ah = simulate(current, soc0, h)
        cells = m[m.case == name]
        rows.append({"Step": name, "Rise, cells [K]": " / ".join(f"{r:.1f}" for r in cells.rise),
                     "Rise, model [K]": rise, "Charge, cells [Ah]": " / ".join(f"{a:.2f}" for a in cells.ah),
                     "Charge, model [Ah]": ah, "Fitted here": name == CASES[0][0]})
    out = pd.DataFrame(rows)
    print(f"h fitted to the 0.5C charge: {h:.1f} W/m2K")
    pd.set_option("display.width", 160)
    print(out.round(2).to_string(index=False))
    return h, m, out


if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract(sys.argv[1])
    main()
