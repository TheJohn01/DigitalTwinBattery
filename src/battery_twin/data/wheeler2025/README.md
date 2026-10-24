# Twenty A123 LFP cells aged at 50 °C into second-life capacities (Wheeler et al. 2025)

- **Data:** W. Wheeler, P. Venet, Y. Bultel, A. Sari. *Aging study on twenty A123 18650
  Graphite/LFP 1.1 Ah cells.* Recherche Data Gouv (2025), doi 10.57745/OLBXKT, version 2.0.
  Paper: *An ageing study of twenty 18650 lithium-ion Graphite/LFP cells in first and second
  life use*, Scientific Data 12, 392 (2025), doi 10.1038/s41597-025-04712-7.
- **Cells:** A123 APR18650M1A (LFP / graphite, 1.1 Ah), the cell of Severson et al. (2019) and
  of Preger et al.'s (2020) A123 rows. 2.5-3.65 V (3.55 V in groups 2 and 5).
- **Test:** ageing at 50 °C in blocks of 100 cycles, each followed by a check-up at 50 °C (C/3
  and C/25 cycles; capacity = C/3 charge capacity). Discharge: the WLTP car profile (1,800 s,
  mean C/3, peaks 2.7C discharge and 1.1C regeneration) repeated to 70 % depth, or 2C constant
  current (group 6); 100 % depth to 2.5 V in group 7. The depth is taken from the last
  check-up's capacity, so the charge per cycle shrinks as the cell fades.

| Group | Cells | Charge | Discharge | Depth | Median cycles to 80 % | Capacity at the end |
|---|---|---|---|---|---|---|
| 1 | 1a, 1b, 1c | CC-CV C/3 to 3.65 V | WLTP | 70 % | 1,321 | 56-64 % after 3,200-3,300 cycles |
| 2 | 2a, 2b, 2c | CC-CV C/3 to 3.55 V | WLTP | 70 % | 1,162 | 55-57 % after 3,300 |
| 3 | 3a, 3b | CC C/3 to 3.65 V | WLTP | 70 % | 1,241 | 53-56 % after 3,900 |
| 4 | 4a, 4b, 4c | CC-CV 2C to 3.65 V | WLTP | 70 % | 1,476 | 45-54 % after 4,300-4,500 |
| 5 | 5a, 5b, 5c | CC-CV 2C to 3.55 V | WLTP | 70 % | 1,343 | 49-55 % after 4,100-4,200 |
| 6 | 6a, 6b, 6c | CC-CV 2C to 3.65 V | CC 2C | 70 % | 1,951 | 36-48 % after 6,300-6,800 |
| 7 | 7a, 7b, 7c | CC C/3 to 3.65 V | WLTP | 100 % | 1,025 | 32-42 % after 3,100-3,300 |

| File | Content |
|---|---|
| `capacity.csv` | One row per check-up (843): cell, group, ageing cycles done, full equivalent cycles (FEC, from the authors' ageing blocks), C/3 charge capacity [Ah]. Written by `scripts/extract_wheeler2025.py <extractedData.mat>`. Check-ups without a capacity in the authors' file (cells 1a, 2a, 2c, 3a, one each) are left out. |

Checks on the raw files of group 6 (the cycler's CSV files, about 20 GB; not kept): the charge
per ageing block equals the authors' file; the cells cycled 3,589-3,633 times a year, with a
median of 3.1 days between ageing blocks (October 2020 to September 2022).

Used by `scripts/validate_lfp_wheeler.py` (a check, nothing is fitted): the shape of the fade
below 80 % (the second life) and the level at 50 °C, above the LFP model's 20-40 °C data.
