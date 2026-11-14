# Validation dossier: NCA

Condensed from README sections 4, 6.5, 9 and 10.1; the numbers are the same. Re-run the scripts
named here to reproduce them.

## 1. Cells

| Part | Cell | Note |
|---|---|---|
| Physics | Samsung INR21700-50E (NCA / graphite-SiOx), Schmitt et al. 2023 | Thermal properties from Chen 2020, electrolyte from Landesfeind & Gasteiger 2019 |
| Ageing, calendar | Panasonic NCR18650B (NREL BLAST-Lite, Keil et al. 2016) | A different NCA cell |
| Ageing, cycling | Depth effect from the Panasonic cell (Preger et al. 2020), level from the 50E (REBELION) | |
| LCA | Degen et al. 2024 NCA factors | Cell level |

## 2. Fitted

| What | Data | Script | Fit error |
|---|---|---|---|
| Cycling term A, B_DOD, C_RATE, P | Preger et al. 2020, Panasonic NCR18650B (18 points) | `scripts/fit_ageing.py` | 2.0 %-points RMS; 8 of 9 tests within about 15 % in cycles to 80 % |
| Level of the 50E (LEVEL_50E = 0.381) | Two 50E cells, 0-100 %, about 530 full cycles (REBELION) | `scripts/fit_ageing.py` step 2 | 0.63 %-points RMS |
| Charge-rate term K_CH, T_CH | 50E at 0.5 and 1C, 0, 23 and 40 °C (Huang et al. 2026, read by eye) | `scripts/fit_ageing.py` step 3 | 2.2 %-points RMS |

## 3. Independent checks

| Data (not used in the fit) | Script | Result | Verdict |
|---|---|---|---|
| Schmitt et al.'s discharges, 0.04-1C at 25 °C | `scripts/validate_nca.py` | capacity within 1 %, 15-24 mV RMS | good |
| Two Wuppertal 50E cells, 25 °C (research-only data) | `scripts/validate_nca_thermal.py` | capacity within 1 %; 0.75C warming matches; C/5 warming a quarter of measured (no entropic heat) | good except low-current heat |
| Ohneseit 21700 NCA at 20 °C, 1C | `tests/test_ageing.py` | 1,470 vs about 1,300-1,500 cycles | good |
| AVILOO fleet, Tesla Model 3 NCA at 100,000 km (grey literature) | `tests/test_ageing.py` | 88.2 vs 88-90 % | inside |
| 254 retired 50E cells, 1C 10 s pulse resistance | `scripts/extract_hppc_resistance.py` | median 43.7 mΩ, CV 55 % | spread only (no capacity per cell) |

## 4. Range of validity

From `ageing.NcaRefit.experimental_range`: cycling temperature 15-35 °C, depth of discharge
20-100 %, charge up to 1C, discharge up to 2C. The physics set cannot discharge at 3C. Curves
stop at 50 % capacity.

## 5. Known gaps

- The knee and sudden failure of 50E cells charged without a CV hold or held at 2.5 V
  (after 390-430 cycles).
- Faster fade at 40 °C (14.5 vs 18 % at 750 cycles), the 2C discharge's earlier end, and
  failure at 0 °C within 50 cycles (outside the range; a warning).
- Entropy coefficients of the 50E (no open measurement; Geng et al. 2021 give a method).
- Resistance growth against health: needs the raw Wuppertal capacity tests.
- No peer-reviewed NCA car fleet data.
