# Commercial 280 Ah LFP cell: characterisation and ageing data (Gray & Vagg, 2026)

Cell: 280 Ah prismatic LFP / graphite storage cell, the "LIC" cell of the EU project TEMPEST
(maker not named; about 300 Ah measured at C/10).

- **Dataset:** R. Gray, C. Vagg (University of Bath). *280 Ah prismatic LFP cell:
  characterisation and aging data.* Zenodo (2026), v2. https://doi.org/10.5281/zenodo.20813753.
  Licence CC BY 4.0.
- **How the files were made:** `scripts/extract_gray2026.py capacity_hppc_entropy.zip aging.zip <folder>`.
  The `LIC_*.csv` files are the dataset's own analyses, unchanged; the others are computed
  from its raw data.
- **Temperature sensor:** cell surface, middle of the largest face.

## Files
| File | Content |
|---|---|
| `LIC_capacity_analysis.csv` | C/10 capacity at 15, 20, 25, 30, 35 °C |
| `LIC_hppc_analysis.csv` | ohmic resistance R0 and RC pair (R1, C1) at 10 SOCs and 15-35 °C |
| `LIC_entropy_analysis.csv` | full-cell entropy coefficient at 10-90 % SOC (OCV at 5-45 °C) |
| `LIC_aging_analysed.csv` | capacity (0.1C), ohmic resistance and SOH every 50 cycles: 700 cycles at 1C, CV to 0.05C, a day of rest after every 50 |
| `capacity_test_25C.csv` | charge and discharge capacity and energy of the 25 °C capacity test (28 A, 2.5-3.65 V) |
| `discharge_C10_25C.csv` | that discharge, one row a minute |
| `pseudo_ocv_25C.csv` | mean of the charge and discharge voltage at the same SOC (5-95 %) and half their difference |
| `ageing_conditions.csv` | mean cell temperature during the 1C cycles (39.6 °C) and at rest (32.5 °C), test length (114 days) |

## Use in the program
- `lfp_blade_params.py`: entropy coefficient (entropic heat), and through `scripts/fit_blade.py`
  the LFP OCP level (pseudo-OCV) and the hysteresis (half gap minus 28 A x (R0 + R1)).
- `scripts/validate_blade.py`: C/10 discharge curve, capacity and resistance vs temperature,
  C/10 energy efficiency, and the 700 cycles as a check of the LFP ageing model.
