"""Capacity at every reference test of UConn-MathWorks LFP cells cycled to below 80 % with fast
charging, then in a second life at 0.5C over the full depth:
data/uconn2025/second_life.csv (data/uconn2025/README.md).

Data: T. Li, A. Lawlor, A. Narasimhamurthy, X. Peng, C. Hu (University of Connecticut and
The MathWorks), "UConn-MathWorks LFP/Gr Second-Life Battery Aging Dataset" (2025), REIL
Datasets 3, digitalcommons.lib.uconn.edu/reil_datasets/3, CC BY 4.0. LithiumWerks 18650
LFP / graphite, 1.2 Ah.

Capacity: the largest Capacity(Ah) of the C/3 reference discharge (Segment "ref_dchg") of
each "RPT <k>.csv". Cycles: the cycles of each "cycling <k>.csv" block; RPT k follows block k.

Run:  python scripts/extract_uconn2025.py G5C1.rar G13C2.rar
"""
import io
import re
import sys

import libarchive
import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "uconn2025" / "second_life.csv"


def read(archive):
    """(RPT rows, cycling-block rows) of one cell's archive."""
    rpts, blocks = [], []
    with libarchive.file_reader(archive) as a:
        for e in a:
            m = re.search(r"(\w+)/(RPT|cycling) (\d+)\.csv$", e.pathname)
            if not (e.size and m):
                continue
            cell, kind, k = m.group(1), m.group(2), int(m.group(3))
            d = pd.read_csv(io.BytesIO(b"".join(e.get_blocks())), low_memory=False)
            if kind == "RPT":
                ref = d[d.Segment == "ref_dchg"]
                rpts.append({"cell": cell, "rpt": k, "date": d["Date(h:min:s.ms)"].iloc[0][:10],
                             "q_ah": round(float(ref["Capacity(Ah)"].max()), 4)})
            else:
                life = str(d.Phase.dropna().iloc[0]).split()[0].lower()   # "first" / "second"
                blocks.append({"cell": cell, "rpt": k, "block_cycles": d.Cycle.nunique(),
                               "life": life})
    return pd.DataFrame(rpts), pd.DataFrame(blocks)


if __name__ == "__main__":
    out = []
    for archive in sys.argv[1:]:
        rpts, blocks = read(archive)
        d = rpts.merge(blocks, on=["cell", "rpt"], how="left").sort_values("rpt")
        d["life"] = d.life.fillna("first")                  # RPT 0: before any cycling
        d["cycles"] = d.block_cycles.fillna(0).cumsum().astype(int)
        out.append(d[["cell", "rpt", "date", "life", "cycles", "q_ah"]])
    d = pd.concat(out)
    OUT.parent.mkdir(exist_ok=True)
    d.to_csv(OUT, index=False)
    print(f"{d.cell.nunique()} cells, {len(d)} reference tests -> {OUT}")
