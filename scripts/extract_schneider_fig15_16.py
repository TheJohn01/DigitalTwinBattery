"""Needs PyMuPDF (pip install pymupdf). Usage: python extract_schneider_fig15_16.py <paper.pdf> <output folder>
Measured discharge voltage (Fig. 15a) and surface temperature (Fig. 16) of the commercial
NA18650-1250 cell, Schneider et al. 2025 (JES 172 090525), read from the PDF vector paths."""
import sys, numpy as np, pymupdf as fitz
pdf, out = sys.argv[1], sys.argv[2]
pg = fitz.open(pdf)[18]
RATES = {(0.0, 0.0, 1.0): 0.01, (1.0, 0.0, 0.0): 0.1, (0.0, 0.5, 0.0): 0.5,
         (0.75, 0.0, 0.75): 1.0, (0.0, 0.75, 0.75): 2.0, (0.75, 0.75, 0.0): 5.0}
def pts(d):
    p = []
    for it in d["items"]:
        seq = [it[1], it[2]] if it[0] == "l" else ([it[1], it[4]] if it[0] == "c" else [])
        for q in seq:
            if not p or abs(p[-1][0] - q.x) + abs(p[-1][1] - q.y) > 1e-6: p.append((q.x, q.y))
    return np.array(p)
volt, temp = {}, {}
for d in pg.get_drawings():
    if not d.get("color") or str(d.get("dashes")) in ("None", "[] 0"): continue
    col = tuple(round(c, 2) for c in d["color"]); r = d["rect"]
    if col not in RATES or r.width < 100: continue
    xy = pts(d)
    if r.y0 < 300:   # Fig. 15a (top left panel)
        q = (xy[:, 0] - 92.2) * 200 / (121.3 - 92.2); v = 1.5 + (231.4 - xy[:, 1]) / 64.0
        volt[RATES[col]] = (q, v)
    else:            # Fig. 16
        q = (xy[:, 0] - 83.8) * 200 / (114.6 - 83.8); t = 25 + (507.1 - xy[:, 1]) * 5 / (507.1 - 458.5)
        temp[RATES[col]] = (q, t)
for name, data, col in [("measured_discharge_voltage.csv", volt, "voltage_V"), ("measured_surface_temperature.csv", temp, "surface_temperature_C")]:
    rows = [(c, q, y) for c in sorted(data) for q, y in zip(*data[c])]
    np.savetxt(f"{out}/{name}", np.array(rows), delimiter=",", header=f"c_rate,discharge_capacity_mAh,{col}", comments="", fmt="%.5g")
    for c in sorted(data): print(name, c, "n", len(data[c][0]), "Qmax %.0f mAh" % data[c][0].max(), "first %.3f last %.3f" % (data[c][1][0], data[c][1][-1]))
