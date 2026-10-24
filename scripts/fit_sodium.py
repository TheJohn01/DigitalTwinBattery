"""Sodium-ion ageing constants (ageing.SodiumIon) from TUM's Mushang NA18650-1250 cells, the
cell of the physics model (data/bahrke2026, data/rehm2026). All tests at 25 °C unless noted.

1. Calendar: 24 cells stored at 10, 30, 50, 70 and 90 % SOC (25 °C) and 10/50/90 % (45 °C)
   for about 1.5 years. Loss = K_CAL(SOC) * sqrt(years): a square root fits the curves a
   little better than a straight line (median RMS 0.44 vs 0.54 %-points). K_CAL is the
   median of the three 25 °C cells at each SOC; the 45 °C cells aged no faster, so there is
   no temperature term.
2. Cycling at full depth: four cells cycled 0-100 % at 1C. Their loss minus the calendar
   loss of the test's time (at the window's mean K_CAL) is linear in EFC down to 80 %;
   FADE_PER_EFC is the median of the four slopes, FADE_PER_EFC_WORST the fastest.
3. Depth: the four cells cycled 20-80 % at 1C (Rehm et al. 2026). Their loss minus the
   calendar part, per EFC at the last check-up, over FADE_PER_EFC: median PARTIAL_FACTOR,
   fastest PARTIAL_FACTOR_WORST. The 20 % windows (0-20 ... 80-100 %) are a check: their
   loss is the calendar loss of their SOC, with no cycling wear left.

Run:  python scripts/fit_sodium.py
"""
import numpy as np
import pandas as pd

from battery_twin.constants import DATA_DIR

CHECKUPS = DATA_DIR / "bahrke2026" / "checkups.csv"
REHM = DATA_DIR / "rehm2026" / "sodium_20_80_1c.csv"
FULL_1C = ["001", "013", "014", "020"]
WINDOWS = {"046": (0.0, 0.2), "049": (0.2, 0.4), "055": (0.4, 0.6), "065": (0.6, 0.8),
           "076": (0.8, 1.0), "019": (0.2, 0.8)}
SOC_GRID = np.array([0.1, 0.3, 0.5, 0.7, 0.9])


def checkups():
    d = pd.read_csv(CHECKUPS, parse_dates=["start"], dtype={"cell": str})
    first = d.groupby("cell").transform("first")
    d["years"] = (d.start - first.start).dt.total_seconds() / (365 * 86400)
    d["rel"] = d.q_ah / first.q_ah
    return d


def calendar(d):
    """K_CAL at SOC_GRID: median over the 25 °C cells of loss / sqrt(years) at the end."""
    cal = d[d.plan.str.contains("per")].copy()
    cal["soc"] = cal.plan.str.extract(r"_(\d+)per", expand=False).astype(int) / 100
    t45 = cal.groupby("cell").test.transform(lambda s: s.str.contains("45Cel").any())
    last = cal[~t45].groupby("cell").last()
    last = last[last.years > 1.0]                             # cells stored the whole test
    k = ((1 - last.rel) / np.sqrt(last.years)).groupby(last.soc).median()
    return np.interp(SOC_GRID, k.index, k.values)


def window_k(k_cal, lo, hi):
    """Mean K_CAL over a constant-current window (equal time at each SOC)."""
    return float(np.mean(np.interp(np.linspace(lo, hi, 21), SOC_GRID, k_cal)))


def cycling_rates(d, k_cal):
    """Cycling loss per EFC of each full-depth 1C cell, down to 80 %."""
    rates = {}
    for cell in FULL_1C:
        g = d[(d.cell == cell) & (d.rel >= 0.8)]
        cyc = 1 - g.rel - window_k(k_cal, 0, 1) * np.sqrt(g.years)
        rates[cell] = float(np.polyfit(g.efc, cyc, 1)[0])
    return rates


def partial_rates(d, k_cal):
    """Cycling loss per EFC of the 20-80 % cells at their last check-up. Rehm's file has
    no dates: the time comes from cell 019's pace (EFC per year), which ran alongside."""
    r = pd.read_csv(REHM).groupby("cell").last()
    g019 = d[d.cell == "019"].iloc[-1]
    pace = g019.efc / g019.years
    k = window_k(k_cal, 0.2, 0.8)
    return {c[-3:]: float((1 - row.soh - k * np.sqrt(row.efc / pace)) / row.efc)
            for c, row in r.iterrows()}


def window_check(d, k_cal):
    """20 % windows and 20-80 %: measured loss next to the calendar loss of their SOC."""
    rows = []
    for cell, (lo, hi) in WINDOWS.items():
        g = d[d.cell == cell].iloc[-1]
        rows.append({"cell": cell, "window": f"{lo:.0%}-{hi:.0%}", "EFC": round(g.efc),
                     "years": round(g.years, 2), "measured loss [%]": round(100 * (1 - g.rel), 1),
                     "calendar alone [%]": round(100 * window_k(k_cal, lo, hi) * np.sqrt(g.years), 1)})
    return pd.DataFrame(rows)


def fit():
    d = checkups()
    k_cal = calendar(d)
    full = cycling_rates(d, k_cal)
    fade = float(np.median(list(full.values())))
    part = {c: max(v, 0.0) / fade for c, v in partial_rates(d, k_cal).items()}
    return {"K_CAL": k_cal, "FADE_PER_EFC": fade, "FADE_PER_EFC_WORST": max(full.values()),
            "PARTIAL_FACTOR": float(np.median(list(part.values()))),
            "PARTIAL_FACTOR_WORST": max(part.values()), "full": full, "partial": part}


if __name__ == "__main__":
    f = fit()
    print("K_CAL at SOC 10/30/50/70/90 % [% per sqrt(year)]:", np.round(100 * f["K_CAL"], 2))
    print("Full depth 1C, cycling loss per EFC [%]:",
          {c: round(100 * v, 4) for c, v in f["full"].items()})
    print(f"FADE_PER_EFC = {100 * f['FADE_PER_EFC']:.4f} %, worst {100 * f['FADE_PER_EFC_WORST']:.4f} %")
    print("20-80 % cells, cycling part / FADE_PER_EFC:", {c: round(v, 3) for c, v in f["partial"].items()})
    print(f"PARTIAL_FACTOR = {f['PARTIAL_FACTOR']:.3f}, worst {f['PARTIAL_FACTOR_WORST']:.3f}")
    print(window_check(checkups(), f["K_CAL"]).to_string(index=False))
