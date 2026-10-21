# TUM Tesla Model 3 (LFP) capacity checks (Bilfinger et al., 2025)

- **Paper:** P. Bilfinger, M. Schreiber, P. Rosner, K. Abo Gamra, J. Schöberl, C. Grosu,
  M. Lienkamp. *Why we need a standardized state of health measurement procedure for electric
  vehicle battery packs — a proposal for energy- and capacity-based metrics.* npj Clean Energy
  1, 10 (2025). https://doi.org/10.1038/s44406-025-00010-8 (title corrected in
  https://doi.org/10.1038/s44406-025-00018-0). Data on mediaTUM, CC BY 4.0.
- **Car:** the TUM Tesla Model 3 (106 LFP cells in series; 55.1 kWh beginning-of-life energy
  reported by its BMS), fully charged at 6 A from a household socket (Juice Booster) in 2021
  and in January 2025.

| File | Content |
|---|---|
| `model3_lfp_capacity.csv` | Charge counted from `Tesla_Model_3_JB_6A_CEE7_FTM_2021.feather` and `..._2025.feather` (trapezoidal sum of the pack current); capacity = charged Ah / (SOC end − SOC start) of the BMS. The 2021 file has no date. |

Result: 163.6 → 149.0 Ah, 8.9 % lost in about four years. `scripts/fit_field_ageing.py` compares
this with the LFP car model (not scaled; no fit). Mileage is not in the data.
