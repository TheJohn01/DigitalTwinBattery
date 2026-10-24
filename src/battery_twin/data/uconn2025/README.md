# UConn-MathWorks LFP second-life cells (Li et al. 2025)

- **Data:** T. Li, A. Lawlor, A. Narasimhamurthy, X. Peng, C. Hu (University of Connecticut and
  The MathWorks), *UConn-MathWorks LFP/Gr Second-Life Battery Aging Dataset* (2025), REIL
  Datasets 3, https://digitalcommons.lib.uconn.edu/reil_datasets/3, CC BY 4.0.
- **Cells:** LithiumWerks 18650 LFP / graphite, 1.2 Ah (the A123 APR18650 line). Two of the
  108 cells kept: G5C1 (4.8C charge, derated near the end, 3C discharge) and G13C2 (1C charge,
  4C discharge), cycled to 70-76 % in about 2-3 months, then at 0.5C both ways over 2.0-3.6 V
  to 47 %. Chamber temperature not stated ("controlled"). G6C3 was sent without its reference
  tests and is not kept.

| File | Content |
|---|---|
| `second_life.csv` | One row per cell and reference test (56): cell, test number, date, life of the cycling block before it (first / second), cycles since the start, C/3 reference discharge capacity [Ah] (`ref_dchg`). Written by `scripts/extract_uconn2025.py G5C1.rar G13C2.rar`. |

Second life: G5C1 70.4 -> 47.0 % in 746 cycles, G13C2 76.2 -> 46.7 % in 573 cycles; both had
already bent (a knee) in their first life.

Used by `scripts/validate_lfp_second_life.py`.
