"""E-Redes 2026 BTN consumption profiles A, B and C -> data/eredes2026/btn_profiles_2026.csv.

E-Redes publishes, under ERSE Diretiva 16/2023, the profiles that settle the consumption of
low-voltage customers without interval metering, in quarter-hours of legal (local) time:
"Perfis de Consumo e Injeção 2026", https://www.e-redes.pt (Perfil_Consumo_Injeção_E-REDES_2026.xlsx).
BTN class A: contracted power above 13.8 kVA; B: up to 13.8 kVA and more than 7,140 kWh a year;
C: up to 13.8 kVA and at most 7,140 kWh a year. The quarter-hours are summed to hours of legal
time (date, hour starting 0-23; 8,760 rows) and each profile is scaled to 1 over the year, so a
profile times an annual consumption gives kWh per hour.

Run:  python scripts/import_eredes_profiles.py <Perfil_Consumo_Injeção_E-REDES_2026.xlsx>
      (read with the standard library: an .xlsx file is a zip of XML sheets)
"""
import sys
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree as ET

import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "eredes2026" / "btn_profiles_2026.csv"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
COLUMNS = {"E": "btn_a", "F": "btn_b", "G": "btn_c"}
EXCEL_EPOCH = date(1899, 12, 30)


def rows(path):
    """Data rows of the first sheet: (Excel date, 'HH:MM' end of the quarter, A, B, C). Empty
    cells are absent from the XML, so cells are found by their column letter."""
    z = zipfile.ZipFile(path)
    shared = [''.join(t.text or '' for t in si.iter(f"{{{NS['m']}}}t"))
              for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
    sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml")).find("m:sheetData", NS)
    for r in sheet:
        cell = {}
        for c in r:
            v = c.find("m:v", NS)
            if v is not None:
                cell[c.get("r").rstrip("0123456789")] = (shared[int(v.text)] if c.get("t") == "s"
                                                         else v.text)
        if cell.get("A", "").isdigit() and all(k in cell for k in COLUMNS):
            yield int(cell["A"]), cell["C"], *(float(cell[k]) for k in COLUMNS)


if __name__ == "__main__":
    d = pd.DataFrame(rows(sys.argv[1]), columns=["day", "end", *COLUMNS.values()])
    # Four consecutive quarters make one hour of legal time: the spring clock change has 23
    # hours, the autumn one 25 (its repeated hour is marked "a" in the file and kept twice).
    end = d.end.str.rstrip("a")
    start_min = end.str[:2].astype(int) * 60 + end.str[3:].astype(int) - 15
    block = d.index // 4
    assert (start_min[d.index % 4 == 0] % 60 == 0).all(), "quarters not aligned to hours"
    first = d.groupby(block).first()
    hourly = d.groupby(block)[list(COLUMNS.values())].sum()
    hourly = hourly / hourly.sum()
    hourly.insert(0, "date", [str(EXCEL_EPOCH + timedelta(days=int(x))) for x in first.day])
    hourly.insert(1, "hour", (start_min.groupby(block).first() // 60).to_numpy())
    OUT.parent.mkdir(exist_ok=True)
    hourly.to_csv(OUT, index=False, float_format="%.4e")
    print(f"{len(d)} quarter-hours -> {len(hourly)} hours; written {OUT}")
