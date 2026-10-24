"""Capacity at every diagnostic of Stanford's K2 Energy LFP cells stored at 24 and 45 °C (50 and
100 % SOC) for up to 7.8 years:
data/lam2024/lfp_calendar.csv (data/lam2024/README.md).

Data: V. Lam et al. (2024/2025), "A decade of insights: delving into calendar aging trends and
implications", Joule; data on OSF (osf.io/ju325), cell list Joule_cell_id.csv in
github.com/viveklam/Joule-Decade-Calendar-Aging. Capacity: the first C/5 discharge of each
diagnostic (RPT0.2C_0_D_capacity).

Run:  python scripts/extract_lam2024.py "<joule_declass_sum folder>" Joule_cell_id.csv
"""
import json
import sys
from pathlib import Path

import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "lam2024" / "lfp_calendar.csv"

if __name__ == "__main__":
    folder, ids = Path(sys.argv[1]), pd.read_csv(sys.argv[2])
    rows = []
    keep = (ids.Cell_chemistry == "LFP") & (ids.Temperature <= 45)   # 60/85 °C: far outside the model
    for r in ids[keep].itertuples():
        path = folder / f"{r.Cell_id}_sum.json"
        if not path.exists():                               # not every cell has a summary
            continue
        s = json.loads(json.load(open(path))["summary_data"])
        q, days = s["RPT0.2C_0_D_capacity"], s["Calendar_DateTime(days)"]
        rows += [{"cell": r.Cell_id, "cell_type": r.Cell_type, "temp_c": r.Temperature,
                  "soc": r.SOC / 100, "days": days[k], "q_ah": q[k]} for k in q]
    d = pd.DataFrame(rows).dropna()
    OUT.parent.mkdir(exist_ok=True)
    d.to_csv(OUT, index=False)
    print(f"{d.cell.nunique()} cells, {len(d)} diagnostics -> {OUT}")
