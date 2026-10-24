# Offenburg 200 Ah stationary LFP cells: calendar and cycle ageing at 35 and 50 °C

- **Data:** M. C. Yagci, O. Richter, R. Behmann, W. G. Bessler (Offenburg University of Applied
  Sciences). Research data for *Degradation modes of large-format stationary-storage
  LFP-based lithium-ion cells during calendaric and cyclic aging*, J. Energy Storage 124,
  116774 (2025), doi 10.1016/j.est.2025.116774. Zenodo 22939281, CC BY 4.0.
- **Cells:** commercial large-format LFP / graphite stationary-storage cells, 180 Ah rated,
  about 200 Ah measured. Twelve cells, two per condition.

| Condition | Cells (lab no.) | Capacity left at the last check-up |
|---|---|---|
| Cycled 0-100 % at C/4 (50 A), 35 °C chamber (cell 36.5 °C) | 19, 42 | 89.4, 88.6 % after 1,500 cycles (about 790 days) |
| Cycled 0-100 % at C/4, 50 °C chamber (cell 52 °C) | 22, 28 | 77.8, 77.6 % after 1,500 cycles (about 850 days) |
| Stored at 35 °C, 100 / 75 % SOC | 26, 30 / 20, 38 | 91.6, 93.8 / 92.3, 92.7 % after about 800 days |
| Stored at 50 °C, 100 / 75 % SOC | 31, 35 / 24, 34 | 85.9, 88.2 / 87.2, 85.4 % after about 860 days |

| File | Content |
|---|---|
| `checkups.csv` | One row per cell and check-up (0, 100, 500, 1000, 1500): condition, chamber temperature, storage SOC, mean cell temperature while cycling, days since formation, discharge capacity [Ah]. Written by `scripts/extract_yagci2025.py` from the authors' `Data` folder and the raw `Checkup_0/1000/1500` archives. |

Notes: the authors' spreadsheet repeats check-up 1000 under "Checkup_#1500", so check-up 1500
is computed from the raw files (the same method reproduces check-up 1000 within 0.03 Ah).
The 100 and 500 check-ups are placed at 10 and 50 % of the time to check-up 1000.

Used by `scripts/fit_ageing.py` (LFP step 3: the cycled cells set `K_HOT`, the LFP model's
extra cycling wear in the heat) and `scripts/validate_lfp_calendar.py` (the stored cells
check the calendar term).
