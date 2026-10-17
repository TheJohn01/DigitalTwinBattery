"""Build data/severson2019_capacity.csv: the measured discharge capacity of the Severson
LFP cells, cycle by cycle (every STEP-th cycle, plus the last one, to keep the file small).

Source of the files: the "124 LFP Capacity Data" folder of
https://github.com/acthelen/battery_digital_twin (MIT licence, (c) 2022 Adam Thelen), which
accompanies Thelen et al., "A comprehensive review of digital twin - part 2", Structural
and Multidisciplinary Optimization 66, 1 (2023). The measurements themselves are from
Severson et al., Nature Energy 4, 383 (2019); credit for the data belongs to the authors.

Mapping, as in that repository's create_capacity_dataset_from_raw_files.py:
  train/cellK.csv -> K-th "Train" cell of data/severson2019_cycle_life.csv
  test1/cellK.csv -> K-th "Prim. Test" cell, without EL150800460605 (died after 148 cycles)
  test2/cellK.csv -> K-th "Sec. test" cell
The folder "test3" is not used: it has no cell list, and its curves go far below the 80 %
where Severson's tests stopped (they appear to be extrapolated).

Run:  python scripts/import_severson_curves.py "<path to>/124 LFP Capacity Data"
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DATA = Path(__file__).parents[1] / "src" / "battery_twin" / "data"
STEP = 10
LEFT_OUT = "EL150800460605"
FOLDERS = {"train": "Train", "test1": "Prim. Test", "test2": "Sec. test"}

folder = Path(sys.argv[1])
cells = pd.read_csv(DATA / "severson2019_cycle_life.csv")
cells = cells[cells.barcode != LEFT_OUT]

rows = []
for name, dataset in FOLDERS.items():
    group = cells[cells.dataset == dataset].reset_index(drop=True)
    for k, cell in group.iterrows():
        data = np.loadtxt(folder / name / f"cell{k + 1}.csv", delimiter=",")
        cycle, capacity = data[:, 0].astype(int), data[:, 1]
        # Check the mapping: the curve must first reach 80 % of the nominal 1.1 Ah at the
        # published cycle life, or end there (some cells were cycled beyond it)
        below = np.where(capacity <= 0.88)[0]
        life = cycle[below[0]] if len(below) else cycle[-1] + 1
        if abs(life - cell.cycle_life) > 2:
            raise ValueError(f"{name}/cell{k + 1}.csv does not match {cell.barcode}")
        keep = (cycle % STEP == 0) | (cycle == cycle[0]) | (cycle == cycle[-1])
        for c, q in zip(cycle[keep], capacity[keep]):
            rows.append({"barcode": cell.barcode, "cycle": c, "capacity_ah": round(float(q), 5)})

out = pd.DataFrame(rows)
out.to_csv(DATA / "severson2019_capacity.csv", index=False)
print(f"{out.barcode.nunique()} cells, {len(out)} rows -> {DATA / 'severson2019_capacity.csv'}")
