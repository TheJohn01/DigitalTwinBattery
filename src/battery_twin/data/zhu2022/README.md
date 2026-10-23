# NCA and NCM 18650 cycling at 25, 35 and 45 °C (Zhu et al. 2022)

- **Data:** J. Zhu et al. *Data-driven capacity estimation of commercial lithium-ion batteries
  from voltage relaxation.* Nature Communications 13, 2261 (2022), doi 10.1038/s41467-022-29837-w.
  Zenodo 6405084, CC BY 4.0.
- **Part used:** Dataset 1 (NCA, 3.5 Ah) and Dataset 2 (NCM, 3.5 Ah), commercial 18650 cells,
  full cycles 2.65-4.2 V, CC-CV charge, 1C discharge, about 4 h per cycle.

| Chemistry | Chamber | Charge | Cells | Median cycles to 80 % |
|---|---|---|---|---|
| NCA | 25 °C | 0.25C | 7 | 307 |
| NCA | 25 °C | 0.5C | 19 | 168 |
| NCA | 25 °C | 1C | 9 | not reached (about 30 cycles recorded) |
| NCA | 35 °C | 0.5C | 3 | 509 |
| NCA | 45 °C | 0.5C | 28 | 495 |
| NMC | 25 °C | 0.5C | 23 | mostly not reached (about 90 % after 190 cycles) |
| NMC | 35 °C | 0.5C | 4 | 1,037 |
| NMC | 45 °C | 0.5C | 28 | 634 |

| File | Content |
|---|---|
| `cycles.csv` | One row per cycle (121 cells): chemistry, chamber temperature, charge and discharge rate, cell, cycle number, discharge capacity [mAh], time at the end of the cycle [h]. Written by `scripts/extract_zhu2022.py <folder>`. |

Used by `scripts/fit_ageing.py` (NMC step): the NCM life ratio 45 °C / 35 °C (0.61) sets
`K_HOT`, the NMC model's extra wear in the heat. Only the ratio is used: these cells fade at
their own level, and the 35 °C group has only four cells. The NCA cells are not used (they
fade faster than the Samsung 50E the NCA model is set to, and their 25 °C cells age faster
than the warmer ones, unlike the 50E).
