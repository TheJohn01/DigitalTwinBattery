# Samsung INR21700-50E: capacity, HPPC and self-heating of two cells (Univ. Wuppertal)

- **Data:** University of Wuppertal, Institute of Electric Mobility and Energy Storage Systems,
  "Samsung INR21700-50E Capacity and HPPC tests", Zenodo https://zenodo.org/records/10891871,
  batch 17 (files `Report_Samsung_INR21700-50E_Zelltester_MCU2_2024-03-07_15.48.38.csv` and
  `..._MCU7_2024-03-07_15.48.43.csv`, 1 kHz). The Zenodo record states its licence (CC BY-NC
  when this was written): non-commercial use with attribution.
- **Described in:** S. Qaadan, A. Alshare, A. Popp, M. Tiemann, U. Spaeth, B. Schmuelling. *Data on
  battery health and performance: Analysing Samsung INR21700-50E cells with advanced feature
  engineering.* Data in Brief 59, 111346 (2025), https://doi.org/10.1016/j.dib.2025.111346; and
  A. Popp, U. Spaeth, B. Schmuelling, IEEE ITEC 2024, https://doi.org/10.1109/ITEC60657.2024.10599066
  (cells from former mobility applications, sorted for second-life storage).
- **Test:** 25 °C climate chamber; CC-CV charge at C/2 (2.45 A) to 4.2 V, cutoff 98 mA; rest;
  C/5 discharge (0.98 A) to 2.5 V; rest; charge; HPPC with 1C pulses and 0.5C discharges in 10 %
  steps; charge at 0.75C (3.67 A). Cell temperature on the middle of the can (0.1 K steps; it
  reads about 0.9 K above the chamber at rest, so only rises are used).

| File | Content |
|---|---|
| `samsung50e_steps.csv` | Every constant-current step longer than 5 minutes of both cells: cell (MCU), start, mean current, charge moved, voltage at start and end, can temperature at start and end. Written by `scripts/validate_nca_thermal.py <folder>`. |
