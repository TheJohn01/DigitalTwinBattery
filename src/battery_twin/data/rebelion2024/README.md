# Samsung INR21700-50E cycle ageing with four charge/discharge strategies (REBELION, 2024)

- **Data:** A. Urquia, S. Ponce Alcantara, R. Vilanova Martínez, C. Martin Villalba, G. Sanchez
  (UNED). *Aging of Samsung INR21700-50E Li-ion cells.* e-cienciaDatos, doi 10.21950/HZ7YOP
  (superseded by 10.21950/GT4LKX, which adds more data), CC BY 4.0. Horizon Europe project
  REBELION (101104241), work package 4.
- **Part used:** the G20 group, eight new cells, two per strategy (folders `G20_<strategy>_<A|B>`),
  cycled 0-100 % between 24 May and 10 December 2024. Room temperature is not recorded.

| Strategy | Charge | Discharge | Result |
|---|---|---|---|
| CVC | CC-CV, 2.45 A (0.5C) to 4.2 V | CC, 4.9 A (1C) to 2.5 V | 4.89 → 4.28 Ah after 578 cycles (about 530 EFC) |
| CVCV | CC-CV | CC-CV to 2.5 V | 5.00 → 4.07-4.16 Ah after 483 cycles, knee from about 430 EFC |
| CC | CC to 4.2 V | CC | 4.2 Ah, collapsed to 0.3 Ah after about 390 EFC |
| CCV | CC to 4.2 V | CC-CV | 4.3 Ah, collapsed to 0.1-0.3 Ah after about 420 EFC |

| File | Content |
|---|---|
| `nca_50e_cycling.csv` | One row per discharge (4,104): strategy, cell, start time, discharge capacity, capacity of the charge before it, whether it reached 2.5 V. Written by `scripts/extract_rebelion.py <folder>`. |

Used by `scripts/fit_ageing.py` (NCA step 2): the CVC cells set the level of the NCA cycling
term (`LEVEL_50E` in `ageing_fit.json`); the CVCV cells are a check.
