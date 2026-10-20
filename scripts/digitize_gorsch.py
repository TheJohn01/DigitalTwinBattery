"""Read Fig. 8C of Gorsch et al. (2025, Cell Rep. Phys. Sci. 6, 102453, CC BY 4.0) into
data/gorsch2025/blade_dcr_20C.csv: the BYD Blade's volume-specific heating at 1C vs SOC.

The paper computes it as I_1C^2 * R / V_cell, with R the mean of the 18 s charge and
discharge pulse resistances at 1C and 20 °C, V_cell = 1.216 dm3 and I_1C = 135 A, so the
resistance follows back from the heating.

Run: python scripts/digitize_gorsch.py <paper.pdf> <folder>
The figure is a raster image: the dark-blue (BYD) markers are found by colour, the axes
are calibrated on the grey grid lines (y: 10-30 W/dm3; x: 10-90 % SOC).
"""
import sys
from pathlib import Path

import fitz
import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage

pdf, out = sys.argv[1], Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
page = fitz.open(pdf)[10]                      # page 10 of the article (Figure 8)
r = page.rect
clip = fitz.Rect(r.x0 + 0.05 * r.width, r.y0 + 0.50 * r.height,
                 r.x0 + 0.62 * r.width, r.y0 + 0.65 * r.height)
pix = page.get_pixmap(matrix=fitz.Matrix(5, 5), clip=clip)
a = np.asarray(Image.frombytes("RGB", (pix.width, pix.height), pix.samples)).astype(int)
red, green, blue = a[..., 0], a[..., 1], a[..., 2]

grey = (abs(red - green) < 8) & (abs(green - blue) < 8) & (red > 190) & (red < 225)
rows = np.where(grey[:, 1000:1200].sum(1) > 150)[0]          # horizontal grid lines
cols = np.where(grey[100:440, :].sum(0) > 250)[0]            # vertical grid lines
y10, y30 = rows.max(), rows.min()                            # 10 and 30 W/dm3
x10, x90 = cols.min(), cols.max()                            # 10 % and 90 % SOC

dark = (blue > 100) & (red < 40) & (green < 90)
labels, n = ndimage.label(ndimage.binary_opening(dark, iterations=6))
points = []
for i in range(1, n + 1):
    ys, xs = np.where(labels == i)
    if len(ys) > 200:                                        # markers, not the line
        soc = 10 + (xs.mean() - x10) / (x90 - x10) * 80
        heat = 10 + (y10 - ys.mean()) / (y10 - y30) * 20
        points.append((round(soc), heat))
assert len(points) == 5, points                              # 20, 35, 50, 70, 90 %
df = pd.DataFrame(points, columns=["soc_pct", "heating_W_dm3"]).sort_values("soc_pct")
df["resistance_mOhm"] = 1000 * df["heating_W_dm3"] * 1.216 / 135.0 ** 2
df.round(4).to_csv(out / "blade_dcr_20C.csv", index=False)
print(df.round(3).to_string(index=False))
