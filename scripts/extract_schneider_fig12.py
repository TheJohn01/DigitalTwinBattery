"""Needs PyMuPDF (pip install pymupdf). Usage: python extract_schneider_fig12.py <paper.pdf> <output folder>
Extract the model curves of Schneider et al. 2025 (JES 172 090525), Fig. 12, from the PDF vector paths."""
import sys, numpy as np, pymupdf as fitz
pdf, out = sys.argv[1], sys.argv[2]
pg = fitz.open(pdf)[16]
def pts_of(d):
    p = []
    for it in d["items"]:
        if it[0] == "l": seq = [it[1], it[2]]
        elif it[0] == "c": seq = [it[1], it[4]]
        else: continue
        for q in seq:
            if not p or (abs(p[-1][0]-q.x) > 1e-6 or abs(p[-1][1]-q.y) > 1e-6): p.append((q.x, q.y))
    return np.array(p)
# panel calibrations: x0,x1 (sto 0..1), y mapping
panels = {
 "a": dict(x=(87.0, 285.7), y=lambda y: 10 ** (-17 + (198.0 - y) / 32.0), box=(86.8, 198.6)),
 "b": dict(x=(342.2, 540.9), y=lambda y: 10 ** (-14 + (198.6 - y) / ((198.6 - 86.8) / 4)), box=(86.8, 198.6)),
 "c": dict(x=(79.0, 277.7), y=lambda y: (348.1 - y) / ((348.1 - 243.2) / 4), box=(241.2, 353.0)),
 "d": dict(x=(339.9, 538.6), y=lambda y: (353.0 - y) * 200 / (353.0 - 241.2), box=(241.2, 353.0)),
}
want = {  # (panel, colour, dashed) -> file
 ("a", (1.0, 0.0, 0.0), True): "anode_diffusivity_m2_s.csv",
 ("a", (0.0, 0.0, 1.0), True): "cathode_diffusivity_m2_s.csv",
 ("b", (0.75, 0.0, 0.75), True): "anode_kinetic_rate.csv",
 ("b", (0.0, 0.75, 0.75), True): "cathode_kinetic_rate.csv",
 ("c", (1.0, 0.0, 0.0), False): "anode_ocp_V.csv",
 ("c", (0.0, 0.0, 1.0), False): "cathode_ocp_V.csv",
 ("d", (0.0, 0.0, 1.0), False): "anode_diffusivity_Ea_kJ_mol.csv",
 ("d", (0.0, 0.75, 0.75), False): "anode_kinetic_rate_Ea_kJ_mol.csv",
 ("d", (1.0, 0.0, 0.0), False): "cathode_diffusivity_Ea_kJ_mol.csv",
 ("d", (0.75, 0.0, 0.75), False): "cathode_kinetic_rate_Ea_kJ_mol.csv",
}
found = {}
for d in pg.get_drawings():
    if not d["color"] or round(d.get("width") or 0, 2) != 1.35: continue
    col = tuple(round(c, 2) for c in d["color"]); dashed = d["dashes"] not in (None, "[] 0")
    r = d["rect"]
    if r.width < 150: continue                      # skip legend samples
    for name, p in panels.items():
        if abs(r.x0 - p["x"][0]) < 1 and p["box"][0] - 1 <= r.y0 and r.y1 <= p["box"][1] + 1:
            key = (name, col, dashed)
            if key in want:
                xy = pts_of(d)
                sto = (xy[:, 0] - p["x"][0]) / (p["x"][1] - p["x"][0])
                val = p["y"](xy[:, 1])
                order = np.argsort(sto, kind="stable"); sto, val = sto[order], val[order]
                keep = np.concatenate([[True], np.diff(sto) > 1e-9])
                found[key] = (np.clip(sto[keep], 0, 1), val[keep])
missing = [want[k] for k in want if k not in found]
assert not missing, missing
header = {"c": "stoichiometry,ocp_V", "d": "stoichiometry,activation_energy_kJ_mol",
          "a": "stoichiometry,diffusivity_m2_s", "b": "stoichiometry,kinetic_rate_m2.5_mol-0.5_s-1"}
for key, fname in want.items():
    s, v = found[key]
    np.savetxt(f"{out}/{fname}", np.column_stack([s, v]), delimiter=",", header=header[key[0]], comments="", fmt="%.6g")
    print(f"{fname:40s} n={len(s):3d} sto {s.min():.3f}-{s.max():.3f}  val {v.min():.4g}..{v.max():.4g}  at0 {v[0]:.4g} at1 {v[-1]:.4g}")
