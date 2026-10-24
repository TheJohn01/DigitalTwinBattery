# Mushang sodium-ion cells: calendar and cycle ageing (TUM, Bahrke et al. 2026)

- **Data:** J. Bahrke, M. Rehm, J. Natterer, C. Wendlandt, A. Jossen. *Aging data for
  commercial sodium-ion batteries, including check-ups and degradation mode analysis.*
  mediaTUM (2026), doi 10.14459/2026mp1840745, CC BY 4.0. Paper: *Calendar and cycle ageing
  of commercial sodium-ion cells with layered oxide cathodes: how does operation influence
  degradation modes?* (EES Batteries).
- **Cell:** Mushang NA18650-1250 (CY_18650-12P-Na; layered oxide / hard carbon, 1.25 Ah),
  the cell of the sodium-ion physics model (Schneider et al. 2025). 1.5-3.8 V.
- **Check-ups:** two C/2 cycles (capacity: the second C/2 discharge from full), pulses, GITT
  and C/20 cycles, at 25 °C.

| Test | Cells | Conditions | Result |
|---|---|---|---|
| Calendar, 25 °C | 003, 005, 006 / 009, 011, 015 / 027, 028, 032 / 038, 039, 041 / 044, 045, 047 | stored at 10 / 30 / 50 / 70 / 90 % SOC, about 1.5 years | lost 0-2.8 / 0.9-4.4 / 5.2-6.5 / 5.9-12.6 / 2.3-9.4 % |
| Calendar, 45 °C | 059, 066, 067 / 073, 075, 078 / 083, 084, 086 | 10 / 50 / 90 % SOC, about 1.45 years | lost 0.1-2.8 / 3.6 % (078: 16 % in 0.75 years, then stopped) / 4.8-5.7 % (084: 9 % in 0.75 years) |
| Cycling, full depth 1C | 001, 013, 014, 020 | 0-100 %, 25 °C | 80 % after 1,325 / 1,361 / 543 / 532 EFC |
| Cycling, full depth 0.5C / 2C | 092 / 029, 081, 087, 089 | 0-100 % | 80 % after 1,113 EFC / 029 lost 15 % in the first 85 EFC |
| Cycling, 20 % windows 1C | 046, 049, 055, 065, 076 | 0-20, 20-40, 40-60, 60-80, 80-100 % | after about 4,200 EFC: +0.5, -0.7, -2.2, -6.2, -8.0 % |
| Cycling, 20-80 % 1C | 019 (021, 022, 053 in data/rehm2026) | 60 % depth | -3.1 % after 5,137 EFC |

| File | Content |
|---|---|
| `checkups.csv` | One row per check-up (461, 52 cells): cell, test name, test plan (its `_<n>per` names a calendar cell's storage SOC), start time, EFC before it (cycling cells), C/2 capacity [Ah], archive folder. Written by `scripts/extract_tum_sodium.py NaIon_*.rar` from the check-up .mat files; the cell comes from the file name (some calendar files carry another cell's serial). Cell 001 matches the authors' reduced table within 0.2 %-points down to 19 %. |

Used by `scripts/fit_sodium.py` for `ageing.SodiumIon`: the calendar term K_CAL (25 °C
cells), the full-depth cycling rate FADE_PER_EFC (the four 1C cells, after taking out their
calendar part), the depth factor (with data/rehm2026), and the check of the 20 % windows.
The archives sent hold check-ups 0, 1, 3, 5, 7 and 9 of the calendar cells; the authors'
reduced tables (`NaIon_Cal_DMA_reduced.mat`) also have the even ones for one cell per
condition.
