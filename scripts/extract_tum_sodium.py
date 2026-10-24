"""Capacity at every check-up of TUM's Mushang NA18650-1250 sodium-ion cells (calendar and
cycle ageing): data/bahrke2026/checkups.csv (data/bahrke2026/README.md).

Data: J. Bahrke, M. Rehm, J. Natterer, C. Wendlandt, A. Jossen (TUM, 2026), "Aging data for
commercial sodium-ion batteries, including check-ups and degradation mode analysis",
mediaTUM, doi 10.14459/2026mp1840745 (CC BY 4.0). Each check-up is one Basytec .mat file
(read with the mat-io package): its TestInfo holds the cell, test plan, start time and the
equivalent full cycles (EFC) done before it; its TestData two C/2 (0.625 A) cycles between
1.5 and 3.8 V, then pulses, GITT and C/20 cycles. The capacity is the C/2 constant-current
discharge of the second cycle, as in the authors' reduced tables (cell 001 matches them
within 0.2 %-points down to 19 %).

Run:  python scripts/extract_tum_sodium.py NaIon_*.rar        (pip install mat-io libarchive-c)
"""
import re
import sys
import tempfile

import libarchive
import matio
import numpy as np
import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "bahrke2026" / "checkups.csv"
C2_A = 0.625                       # C/2 of the 1.25 Ah cell


def first(info, key):
    """A scalar field of the TestInfo record (NaN if absent)."""
    if key not in info.dtype.names:
        return np.nan
    x = info[key]
    while isinstance(x, np.ndarray):                # MATLAB nests scalars in arrays
        x = x.ravel()[0] if x.size else np.nan
    return x


def checkup(path, name):
    """Row of one check-up .mat file: cell, test, plan, start, EFC, C/2 capacity; or None.
    The cell comes from the file name: some calendar files carry another cell's serial."""
    m = matio.load_from_mat(path)
    info, d = m["TestInfo"], m["TestData"]
    step = (d.Line != d.Line.shift()).cumsum()
    s = d.groupby(step).agg(cmd=("Command", "first"), i=("I", "median"), ah=("Ah_Step", "last"),
                            u0=("U", "first"))
    # C/2 discharges from full (after the 3.8 V CV and a rest: aged cells relax below 3.7 V)
    full = s[(s.cmd == "Discharge") & ((s.i + C2_A).abs() < 0.01) & (s.u0 > 3.6) & (s.ah < -0.05)]
    if len(full) < 2:
        return None
    return {"cell": re.search(r"MJBRe_?(\d+)", name).group(1), "test": first(info, "Name_of_Test"),
            "plan": first(info, "Testplan"), "start": pd.Timestamp(first(info, "Start_of_Test")),
            "efc": round(float(first(info, "EFC")), 1), "q_ah": round(-float(full.ah.iloc[1]), 5)}


if __name__ == "__main__":
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for archive in sys.argv[1:]:
            with libarchive.file_reader(archive) as a:
                for e in a:
                    if e.pathname.endswith(".mat") and e.size:
                        path = f"{tmp}/checkup.mat"
                        with open(path, "wb") as f:
                            f.write(b"".join(e.get_blocks()))
                        r = checkup(path, e.pathname)
                        if r:
                            rows.append(dict(r, folder=e.pathname.split("/")[-2]))
    d = (pd.DataFrame(rows).sort_values(["cell", "start"])
         .drop_duplicates(["cell", "start"]))               # good cells sit in two archives
    OUT.parent.mkdir(exist_ok=True)
    d.to_csv(OUT, index=False)
    print(f"{d.cell.nunique()} cells, {len(d)} check-ups -> {OUT}")
