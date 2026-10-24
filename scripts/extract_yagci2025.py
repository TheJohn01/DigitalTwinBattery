"""Capacity at every check-up of Offenburg's 180/200 Ah stationary LFP cells (calendar and
cycle ageing at 35 and 50 °C): data/yagci2025/checkups.csv (data/yagci2025/README.md).

Data: M. C. Yagci, O. Richter, R. Behmann, W. G. Bessler (Offenburg University of Applied
Sciences), research data for "Degradation modes of large-format stationary-storage LFP-based
lithium-ion cells during calendaric and cyclic aging", J. Energy Storage 124, 116774 (2025);
Zenodo 22939281, CC BY 4.0.

Capacities of check-ups 0, 100, 500 and 1000: "Capacities in checkups - all cells.xlsx"
(max_CCCV_DIS). Its "Checkup_#1500" sheet repeats check-up 1000, so check-up 1500 is the
largest continuous discharge of the raw Checkup_1500 capacity files (the same method gives the
spreadsheet's check-up 1000 within 0.03 Ah). Dates: the start of formation (Checkup_0 file
names) and the start of the 1000 and 1500 check-ups (file headers); the 100 and 500 check-ups
are placed at 10 and 50 % of the time to check-up 1000 (shortcut: steady pace assumed; their raw
files were not sent).

Run:  python scripts/extract_yagci2025.py "<Data folder>" Checkup_0.rar Checkup_1000.rar Checkup_1500.rar
"""
import io
import re
import sys

import libarchive
import numpy as np
import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "yagci2025" / "checkups.csv"
# lab cell: (condition, chamber °C, storage SOC or None, mean cell temperature while cycling)
CELLS = {"19": ("cycling", 35, None, 36.5), "42": ("cycling", 35, None, 36.5),
         "26": ("calendar", 35, 1.0, None), "30": ("calendar", 35, 1.0, None),
         "20": ("calendar", 35, 0.75, None), "38": ("calendar", 35, 0.75, None),
         "22": ("cycling", 50, None, 52.0), "28": ("cycling", 50, None, 52.0),
         "31": ("calendar", 50, 1.0, None), "35": ("calendar", 50, 1.0, None),
         "24": ("calendar", 50, 0.75, None), "34": ("calendar", 50, 0.75, None)}


def sheet_capacity(xlsx, n):
    d = pd.read_excel(xlsx, sheet_name=f"Checkup_#{n}", header=None)
    head = d.apply(lambda r: r.astype(str).eq("Cell").any(), axis=1).idxmax()
    d = d.iloc[head:].dropna(axis=1, how="all")
    d.columns = d.iloc[0]
    d = d.iloc[1:]
    return pd.Series(d.max_CCCV_DIS.astype(float).values, index=d.Cell.str[-2:].values)


def raw_files(archive):
    """(cell, start of test, largest continuous discharge [Ah]) of each capacity file."""
    with libarchive.file_reader(archive) as a:
        for e in a:
            name = e.pathname.split("/")[-1]
            if not (e.size and "/Capacity/" in e.pathname) or "18A" in name:
                continue
            cell = re.search(r"CA-181103-(\d+)", name).group(1)
            date = re.search(r"_(20\d{6})_", name)
            text = b"".join(e.get_blocks()).decode("latin-1")
            if date:                                         # formation: date in the name
                yield cell, pd.Timestamp(date.group(1)), np.nan
                continue
            start = pd.Timestamp(pd.to_datetime(re.search(r"~Start of Test: (.*)", text).group(1),
                                                dayfirst=True))
            d = pd.read_csv(io.StringIO(text[text.index("~Time[h]") + 1:]), sep="\t",
                            usecols=["Time[h]", "I[A]"])
            t, i = 3600 * d["Time[h]"].to_numpy(float), d["I[A]"].to_numpy(float)
            dis = i < -1.0
            seg = np.cumsum(np.diff(np.r_[0, dis.astype(int)]) == 1) * dis
            ah = [np.trapezoid(-i[seg == k], t[seg == k]) / 3600 for k in range(1, seg.max() + 1)]
            yield cell, start, max(ah)


if __name__ == "__main__":
    folder, c0, c1000, c1500 = sys.argv[1:5]
    xlsx = f"{folder}/Capacities in checkups - all cells.xlsx"
    q = {n: sheet_capacity(xlsx, n) for n in (0, 100, 500, 1000)}
    start = {c: t for c, t, _ in raw_files(c0)}
    d1000 = {c: t for c, t, _ in raw_files(c1000)}
    r1500 = {c: (t, ah) for c, t, ah in raw_files(c1500)}
    rows = []
    for cell, (cond, chamber, soc, t_cell) in CELLS.items():
        days = {0: 0.0, 1000: (d1000[cell] - start[cell]).days,
                1500: (r1500[cell][0] - start[cell]).days}
        days[100], days[500] = 0.1 * days[1000], 0.5 * days[1000]
        for n in (0, 100, 500, 1000, 1500):
            rows.append({"cell": cell, "condition": cond, "chamber_c": chamber,
                         "storage_soc": soc, "cycling_cell_c": t_cell, "checkup": n,
                         "days": round(days[n], 1),
                         "q_ah": round(r1500[cell][1] if n == 1500 else q[n][cell], 3)})
    OUT.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"{len(CELLS)} cells -> {OUT}")
