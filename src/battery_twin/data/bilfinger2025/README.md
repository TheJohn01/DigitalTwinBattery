# TUM Tesla Model 3 (LFP) capacity checks (Bilfinger et al., 2025)

- **Paper:** P. Bilfinger, M. Schreiber, P. Rosner, K. Abo Gamra, J. Schöberl, C. Grosu,
  M. Lienkamp. *Why we need a standardized state of health measurement procedure for electric
  vehicle battery packs — a proposal for energy- and capacity-based metrics.* npj Clean Energy
  1, 10 (2025). https://doi.org/10.1038/s44406-025-00010-8 (title corrected in
  https://doi.org/10.1038/s44406-025-00018-0). Data on mediaTUM, CC BY 4.0.
- **Car:** the TUM 2020 Tesla Model 3 Standard Range Plus (106 CATL LFP cells in series,
  161.5 Ah nominal; 55.1 kWh beginning-of-life energy reported by its BMS), fully charged at
  6 A from a household socket (Juice Booster) in a 20 °C workshop at 1,000 km (2021) and at
  80,100 km (January 2025) (paper, Methods).

| File | Content |
|---|---|
| `charge_2021.csv`, `charge_2025.csv` | The two charges, one row a minute (last sample of each minute): time, pack current (+ = charging), mean of the 106 cell voltages, BMS SOC, Ah charged. Written by `scripts/validate_estimator_tesla.py`; used to test the SOC filter. |
| `model3_lfp_capacity.csv` | Charge counted from `Tesla_Model_3_JB_6A_CEE7_FTM_2021.feather` and `..._2025.feather` (trapezoidal sum of the pack current). Two capacities: charged Ah / (SOC end − SOC start) of the BMS, and the Ah between 335 and 360 V of the pack voltage (forward mean filter over 1 % of the points, as in the paper). The paper's window is 335–365 V, but the 2021 charge stops at 365.6 V, so 360 V is used for both. The 2021 file has no date. |

Result: 163.6 → 149.0 Ah (91.1 %) in the BMS window, 158.4 → 145.4 Ah (91.8 %) in the voltage
window, after 79,100 km in about four years. The paper's Supplementary Table 1 gives 159.6 →
146.7 Ah (335–365 V, 91.9 %), the same loss. `scripts/fit_field_ageing.py` compares this with the LFP car model (not
scaled; no fit).
