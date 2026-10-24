"""LFP calendar term (BLAST-Lite Sony-Murata, not refitted) against stored LFP cells, and the
LFP heat term (LfpAdjusted.K_HOT, fitted in fit_ageing.py LFP step 3) on the Offenburg cells:

1. Stanford (Lam et al. 2024, data/lam2024): K2 Energy LFP18650E and LFP18650P, five cells per
   condition, stored at 24 and 45 °C at 50 and 100 % SOC for up to 7.8 years. Median capacity
   loss of each cell type after 1, 2, 4 and 7.5 years next to the model's calendar loss.
2. Offenburg (Yagci et al. 2025, data/yagci2025): 200 Ah stationary cells stored at 35 and
   50 °C at 75 and 100 % SOC for about 2.3 years.
3. Offenburg cells cycled fully at C/4 with the cells at 36.5 and 52 °C, to 1,500 cycles: the
   model with the cell's own level (fitted on the 36.5 °C cells), with and without K_HOT.

Run:  python scripts/validate_lfp_calendar.py          (a few seconds)
"""
import numpy as np
import pandas as pd

from scipy.optimize import least_squares

from battery_twin.ageing import LfpAdjusted, add_rest, predict_capacity
from battery_twin.constants import DATA_DIR


def model_loss(temp_c, soc, days):
    """Calendar loss [%] of the LFP model stored at temp_c and soc for `days`."""
    cal, _ = predict_capacity("LFP", np.array([0.0, 86400.0]), np.full(2, soc),
                              np.full(2, float(temp_c)), max(int(days), 1), parts=True)
    return 100 * float(cal[-1])


def stanford(years=(1, 2, 4, 7.5)):
    d = pd.read_csv(DATA_DIR / "lam2024" / "lfp_calendar.csv")
    rows = []
    for (cell, ctype, temp, soc), g in d.groupby(["cell", "cell_type", "temp_c", "soc"]):
        for y in years:
            if g.days.max() >= 365 * y - 30:
                q = np.interp(365 * y, g.days, g.q_ah) / g.q_ah.iloc[0]
                rows.append({"type": ctype.split()[-1], "temp_c": temp, "soc": soc, "years": y,
                             "loss": 100 * (1 - q)})
    t = (pd.DataFrame(rows).groupby(["temp_c", "soc", "years", "type"]).loss.median()
         .unstack())
    t["model"] = [model_loss(temp, soc, 365 * y) for temp, soc, y in t.index]
    return t


def offenburg():
    d = pd.read_csv(DATA_DIR / "yagci2025" / "checkups.csv", dtype={"cell": str})
    d = d[d.condition == "calendar"]
    rows = []
    for cell, g in d.groupby("cell"):
        last = g.iloc[-1]
        rows.append({"cell": cell, "temp_c": last.chamber_c, "soc": last.storage_soc,
                     "days": last.days, "loss": 100 * (1 - last.q_ah / g.q_ah.iloc[0]),
                     "model": model_loss(last.chamber_c, last.storage_soc, last.days)})
    return pd.DataFrame(rows)


def cycled(row, level, k_hot):
    """Model capacity of an Offenburg cycled cell at one check-up (full C/4 cycles)."""
    t, soc = np.array([0.0, 4 * 3600, 4.1 * 3600, 8.1 * 3600]), np.array([1.0, 0.0, 0.0, 1.0])
    t, soc, temp, _ = add_rest(t, soc, np.full(4, row.cycling_cell_c),
                               row.checkup / row.days * 365, row.cycling_cell_c)
    scale, hot = LfpAdjusted.SCALE, LfpAdjusted.K_HOT
    try:
        LfpAdjusted.SCALE, LfpAdjusted.K_HOT = scale * level, k_hot
        return float(predict_capacity("LFP", t, soc, temp, int(row.checkup))[-1])
    finally:
        LfpAdjusted.SCALE, LfpAdjusted.K_HOT = scale, hot


def offenburg_cycling():
    """Measured and model capacity of the cycled cells, with and without the heat term."""
    d = pd.read_csv(DATA_DIR / "yagci2025" / "checkups.csv", dtype={"cell": str})
    d["rel"] = d.q_ah / d.groupby("cell").q_ah.transform("first")
    d = d[(d.condition == "cycling") & (d.checkup > 0)].copy()
    c35 = d[d.chamber_c == 35]
    level = least_squares(lambda x: [cycled(r, x[0], 0.0) - r.rel for r in c35.itertuples()],
                          [0.5], bounds=([0.01], [10])).x[0]
    d["model"] = [cycled(r, level, LfpAdjusted.K_HOT) for r in d.itertuples()]
    d["no heat term"] = [cycled(r, level, 0.0) for r in d.itertuples()]
    return d[["cell", "chamber_c", "cycling_cell_c", "checkup", "rel", "model", "no heat term"]]


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    print("Stanford K2 LFP storage, capacity loss [%] (median of five cells per type):")
    print(stanford().round(1).to_string())
    print("\nOffenburg 200 Ah LFP storage, capacity loss [%]:")
    print(offenburg().round(1).to_string(index=False))
    print(f"\nOffenburg cycled cells, relative capacity (K_HOT = {LfpAdjusted.K_HOT:g} per K "
          "above 35 °C):")
    print(offenburg_cycling().round(3).to_string(index=False))
