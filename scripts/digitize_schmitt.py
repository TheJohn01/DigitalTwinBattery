"""Needs PyMuPDF and Pillow (pip install pymupdf pillow).
Usage: python digitize_schmitt.py <Schmitt_2023 paper.pdf> <supplementary.pdf> <output folder>

Reads two figures of Schmitt et al. (2023), J. Electrochem. Soc. 170, 070509 (CC BY 4.0), for the
Samsung INR21700-50E ("HE") cell. The figures are embedded raster images (300 dpi), so the
curves are read pixel by pixel by colour, with the axes calibrated on the tick marks:

- Fig. 9a: half-cell OCPs balanced to the 21700 cell ("Calc. anode", "Calc. cathode", dashed)
  and the measured 21700 OCV, against discharge capacity in mAh/cm2. The capacity is turned
  into electrode stoichiometry with the simulation balancing of Table SIV (x = 0.999 and 0.16
  at 100 % SOC; capacity per area from c_max, active-material fraction and thickness).
- Fig. 14a: measured discharges at 0.04C, 0.5C and 1C (25 °C). Solid (measured) and dashed
  (their model) curves share a colour; they agree within 0.5 % up to 3 mAh/cm2, so the voltage
  is kept up to 3 mAh/cm2, and the end-of-discharge capacity is the rightmost pixel of each
  colour (the measured curve ends last).
- Supplementary Fig. S14a/b: measured exchange-current density at 25 °C vs full-cell SOC (the
  markers). The analytic fits of Table SIV do not reproduce these points (HE anode fit: 0.22
  instead of the measured 0.38 mA/cm2 at 50 % SOC; cathode fit negative at 0 % SOC), so the
  measurements themselves are used. SOC is turned into stoichiometry over the measured OCV
  span (Q_CELL).
"""
import sys
from io import BytesIO

import numpy as np
import pymupdf
from PIL import Image

F = 96485.33
# Simulation balancing, Table SIV (HE): capacity per electrode area [mAh/cm2]
Q_ANODE = 31695 * 0.66 * 75e-6 * F / 3600 * 0.1                             # = 4.205 mAh/cm2
Q_CATHODE = 50000 * 0.74 * 60e-6 * F / 3600 * 0.1                            # = 5.951 mAh/cm2
X_ANODE_100, X_CATHODE_100 = 0.999, 0.16
Q_CELL = 4.07                  # mAh/cm2 between 100 and 0 % SOC (measured 21700 OCV, Fig. 9a)


def figure(pdf, page_no, size):
    """The embedded image of the given pixel size on a page (1-based page number)."""
    doc = pymupdf.open(pdf)
    for xref, *_ in doc[page_no - 1].get_images():
        info = doc.extract_image(xref)
        if (info["width"], info["height"]) == size:
            return np.asarray(Image.open(BytesIO(info["image"])).convert("RGB")).astype(int)
    raise ValueError(f"no {size} image on page {page_no}")


def track(mask, x_range, start_largest=True):
    """Follow one curve from left to right: per column, the pixel group closest to the
    previous point (gaps between dashes are skipped)."""
    xs, ys = [], []
    for x in range(*x_range):
        rows = np.where(mask[:, x])[0]
        if len(rows) == 0:
            continue
        groups = np.split(rows, np.where(np.diff(rows) > 4)[0] + 1)
        if ys:
            g = min(groups, key=lambda gr: abs(np.median(gr) - ys[-1]))
            if abs(np.median(g) - ys[-1]) > 25 + 2 * (x - xs[-1]):
                continue
        else:
            g = max(groups, key=len)
        xs.append(x)
        ys.append(float(np.median(g)))
    return np.array(xs, float), np.array(ys)


def smooth_monotonic(q, v, increasing, step=0.02):
    """Median per capacity bin, then forced monotonic (an OCP has no wiggles of its own)."""
    edges = np.arange(q.min(), q.max() + step, step)
    qc, vc = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        sel = (q >= a) & (q < b)
        if sel.any():
            qc.append(q[sel].mean()); vc.append(np.median(v[sel]))
    vc = np.maximum.accumulate(vc) if increasing else np.minimum.accumulate(vc)
    return np.array(qc), np.asarray(vc)


def fig9(pdf, out, slow):
    im = figure(pdf, 13, (1820, 1016))
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    x0, px = 148.5, 152.0                          # 0 mAh/cm2 at x = 148.5, 152 px per mAh/cm2

    def volt(y):                                   # broken axis: 2.5-4.0 V above, 0-1.0 V below
        return np.where(y < 265, 4.0 - (y - 55.0) * 1.5 / 190.0, (446.0 - y) / 127.0)

    def panel(mask):
        mask = mask.copy()
        mask[:, :121] = False; mask[:, 875:] = False; mask[:7] = False; mask[444:] = False
        mask[120:398, 150:470] = False                                      # legend
        return mask
    cathode = panel((R > 200) & (G > 80) & (G < 175) & (B > 130) & (B < 210))
    anode = panel((B > 200) & (R > 60) & (R < 160) & (G > 130) & (G < 210))
    ocv = panel(R + G + B < 120); ocv[265:] = False; ocv[:, :140] = False

    xc, yc = track(cathode, (121, 875))
    xa, ya = track(anode, (121, 735))              # the last dash runs next to the solid anode:
    last_x, last_y = [], []                        # take the upper (dashed) pixel group there
    for x in range(735, 778):
        rows = np.where(anode[300:400, x])[0] + 300
        if len(rows):
            last_x.append(x); last_y.append(float(np.median(rows[rows <= rows.min() + 6])))
    xa, ya = np.concatenate([xa, last_x]), np.concatenate([ya, last_y])
    xo, yo = track(ocv, (121, 875))

    qc, vc = smooth_monotonic((xc - x0) / px, volt(yc), increasing=False)
    qa, va = smooth_monotonic((xa - x0) / px, volt(ya), increasing=True)
    qo, vo = smooth_monotonic((xo - x0) / px, volt(yo), increasing=False)
    # Beyond 3 mAh/cm2 the balanced half-cell curves of Fig. 9a give a full-cell OCV up to
    # 90 mV off the measured 21700 OCV (as the paper's own "Calc. full cell" there), and the
    # relaxed OCV stops at 2.72 V. The paper aligned its balancing to the C/25 discharge, so the
    # reference beyond 3 mAh/cm2 is the measured 0.04C discharge (Fig. 14a, to 2.5 V), offset to
    # the OCV at 3 mAh/cm2 (C/25 overpotential). The anode OCP there is cathode OCP minus that
    # reference, and the Fig. 9a anode beyond it, each shifted to join continuously.
    q_join = 3.0
    head = qa < q_join
    qs, vs = slow
    q_mid = qs[qs >= q_join]
    ref = np.interp(q_mid, qs, vs) + np.interp(q_join, qo, vo) - np.interp(q_join, qs, vs)
    v_mid = np.interp(q_mid, qc, vc) - ref
    v_mid = v_mid + np.interp(q_join, qa, va) - v_mid[0]
    tail = qa > q_mid[-1]
    v_tail = va[tail] + v_mid[-1] - np.interp(q_mid[-1], qa, va)
    qa = np.concatenate([qa[head], q_mid, qa[tail]])
    va = np.maximum.accumulate(np.concatenate([va[head], v_mid, v_tail]))

    for name, x, v in [("anode_ocp_V.csv", X_ANODE_100 - qa / Q_ANODE, va),
                       ("cathode_ocp_V.csv", X_CATHODE_100 + qc / Q_CATHODE, vc)]:
        order = np.argsort(x)
        np.savetxt(f"{out}/{name}", np.column_stack([x[order], v[order]]), delimiter=",",
                   header="stoichiometry,ocp_V", comments="", fmt="%.5f")
        print(f"{name}: stoichiometry {x.min():.3f}-{x.max():.3f}, {v.min():.3f}-{v.max():.3f} V")
    np.savetxt(f"{out}/measured_ocv_V.csv", np.column_stack([qo, vo]), delimiter=",",
               header="discharge_capacity_mAh_cm2,ocv_V", comments="", fmt="%.5f")
    print(f"measured_ocv_V.csv: 0-{qo.max():.3f} mAh/cm2")


def fig14(pdf, out):
    im = figure(pdf, 17, (1820, 1328))
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    x0, px = 142.0, (831.0 - 142.0) / 4            # 0 and 4 mAh/cm2
    y42, py = 32.5, (460.5 - 32.5) / 1.6           # 4.2 V at y = 32.5; 2.6 V at y = 460.5
    colours = {0.04: (B > 180) & (R < 150) & (G < 150),
               0.5: (G > 180) & (R < 150) & (B < 170),
               1.0: (R > 180) & (B > 150) & (G < 150)}
    rows = []
    for c_rate, mask in colours.items():
        mask = mask.copy()
        mask[:8] = False; mask[490:] = False; mask[:, :140] = False; mask[:, 880:] = False
        mask[350:490, 150:380] = False                                      # legend
        x, y = track(mask, (140, 880))
        q, v = (x - x0) / px, 4.2 - (y - y42) / py
        q_end = (np.where(mask.any(axis=0))[0].max() - x0) / px
        # solid (measured) and dashed (model) overlap: keep up to 3 mAh/cm2, except at 0.04C
        # where they agree within 0.5 % to the end (paper Fig. 14c)
        keep = q <= (q_end if c_rate == 0.04 else 3.0)
        rows += [(c_rate, qq, vv) for qq, vv in zip(q[keep], v[keep])]
        rows.append((c_rate, q_end, 2.5))
        if c_rate == 0.04:
            slow = smooth_monotonic(np.append(q[keep], q_end), np.append(v[keep], 2.5), False)
        print(f"{c_rate}C: end of discharge {q_end:.3f} mAh/cm2")
    np.savetxt(f"{out}/measured_discharge_voltage.csv", np.array(rows), delimiter=",",
               header="c_rate,discharge_capacity_mAh_cm2,voltage_V", comments="", fmt="%.5f")
    return slow


def fig_s14(si_pdf, out):
    from scipy import ndimage
    im = figure(si_pdf, 7, (1374, 999))
    R, G, B = im[..., 0], im[..., 1], im[..., 2]
    green = (G > 120) & (R < 110) & (B < 110) & (G - R > 60)            # 25 °C markers
    y0, py = 419.0, 159.0                                                # 0 mA/cm2; px per mA/cm2
    for name, (xa, xb), soc_to_x in [
            ("anode_j0_25C.csv", (118, 660), lambda soc: X_ANODE_100 - (1 - soc) * Q_CELL / Q_ANODE),
            ("cathode_j0_25C.csv", (798, 1339), lambda soc: X_CATHODE_100 + (1 - soc) * Q_CELL / Q_CATHODE)]:
        m = green.copy()
        m[:, :xa - 8] = False; m[:, xb + 8:] = False; m[425:] = False; m[:22] = False
        m[30:150, xa + 380:xb] = False                                   # legend
        core = ndimage.binary_erosion(m, structure=np.ones((7, 7)))      # markers, not lines
        lab, n = ndimage.label(core)
        pts = [((cx - xa) / (xb - xa), (y0 - cy) / py)
               for cy, cx in ndimage.center_of_mass(core, lab, range(1, n + 1))]
        for x_edge, soc in ((xa, 0.0), (xb, 1.0)):                       # markers on the axes
            ys = np.sort(np.where(green[22:425, x_edge - 12:x_edge + 13])[0])
            groups = np.split(ys, np.where(np.diff(ys) > 3)[0] + 1)
            pts.append((soc, (y0 - (np.mean(max(groups, key=len)) + 22)) / py))
        soc, j0 = np.array(sorted(pts)).T
        x = soc_to_x(np.round(soc, 2))
        order = np.argsort(x)
        np.savetxt(f"{out}/{name}", np.column_stack([x[order], 10 * j0[order]]), delimiter=",",
                   header="stoichiometry,exchange_current_density_A_m2", comments="", fmt="%.5f")
        print(f"{name}: {len(x)} points, {10 * j0.min():.2f}-{10 * j0.max():.2f} A/m2")


if __name__ == "__main__":
    slow_discharge = fig14(sys.argv[1], sys.argv[3])
    fig9(sys.argv[1], sys.argv[3], slow_discharge)
    fig_s14(sys.argv[2], sys.argv[3])
