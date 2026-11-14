# Validation dossier: NMC

Condensed from README sections 5, 6.4, 9 and 10.1; the numbers are the same. Re-run the scripts
named here to reproduce them.

## 1. Cells

| Part | Cell | Note |
|---|---|---|
| Physics | LG INR21700-M50T (NMC811 / graphite-SiOx), PyBaMM set Chen2020 | Calibrated to the same cell |
| Ageing, calendar | LG M50 (NREL BLAST-Lite, Truong Bui et al. 2021) | Same cell family |
| Ageing, cycling | LG HG2 (NMC / graphite + SiO), plus Preger, Wittman and Ohneseit data | A power cell, not the M50 energy cell |
| Car field factors | Smart e.d. fleet (Li-Tec NMC), Rücker et al. 2024 | Automotive cells age more slowly than the laboratory cells |
| LCA | Degen et al. 2024 NMC factors | Cell level |

## 2. Fitted

| What | Data | Script | Fit error |
|---|---|---|---|
| Initial concentration, SEI diffusivity and activation energy, cooling | Kirkaldy et al. 2024, LG M50T at 25 and 40 °C | `scripts/calibrate.py` | lithium loss 0.40 %-points RMSE |
| Electrolyte diffusivity factor | Catenaro & Onori 2021, 2C and 3C at 25 and 35 °C | `scripts/fit_electrolyte.py` | capacity within 0.07 Ah |
| Cycling term (K_BASE, K_PL, N_CH, T_PL, B_DOD) | 24 conditions, 0-40 °C, 0.33-1.67C charge (`published_ageing.csv`) | `scripts/fit_ageing.py` | typical error ×1.42 in cycles to 80 % |
| Heat term K_HOT | Zhu et al. 2022, NCM at 35 and 45 °C | `scripts/fit_ageing.py` | life ratio 0.65 vs 0.61 |
| Car field factors (calendar ×0.54, cycling ×0.21) | Six Smart e.d. cars | `scripts/fit_field_ageing.py` | 1.5 points RMSE |

## 3. Independent checks

| Data (not used in the fit) | Script | Result | Verdict |
|---|---|---|---|
| Kirkaldy 10 °C cells (lithium loss) | `scripts/validate.py` | 2.56 %-points RMSE | fair |
| Kirkaldy 70-85 % window (capacity) | `scripts/fit_ageing.py` | 1.2-1.6 %-points (BLAST-Lite's original: 7-12) | good |
| Catenaro 1-5C at 25-35 °C | `scripts/validate_thermal.py` | capacity ±0.07 Ah, can temperature 3.8 K RMS | good |
| Catenaro at 5 °C | `scripts/fit_electrolyte.py` | 0.3-0.6 Ah too much capacity | optimistic in the cold |
| 42 TUM LG MJ1 cells | `scripts/validate_nmc_mj1.py` | 4.8 %-points RMS at 0.5C charge or slower; 10 s pulse resistance ×1.09 vs the model's ×1.21 at 80-85 % | good; fails for faster charges (warning) |
| VW ID.3 test car, 60,000 km (Schreiber et al. 2025) | `scripts/fit_field_ageing.py` | 94.4 vs 98.0 % | slightly pessimistic |
| ID.3 cell highway test, about 1,100 fast charges | `scripts/fit_field_ageing.py` | 94.2 vs 92.2 % | good |
| Two Peugeot iOn | `scripts/fit_field_ageing.py` | 95.0-95.1 vs 87.2-93.7 % | optimistic for an older cell |
| AVILOO fleet, LG NMC at 100,000 km (grey literature) | `tests/test_ageing.py` (NCA band) | 92.1 vs 91.5 % | inside |
| O'Kane coupled physics, default duty, 1,000 days | `scripts/check_okane_knee.py` | no knee forms | shape check only |
| 21 home storage systems (Figgener et al. 2024), storage model | `scripts/fit_field_ageing.py` | 2.7 points a year vs 1.9 (operating data) and 3.2 (capacity tests) | inside the range |
| Path dependence (aged cell re-simulated) | `scripts/check_path_dependence.py` | 398 to 379 cycles (-4.8 %) | small |

Worst fitted points: 5/3C at 40 °C (model 345 vs 635), 20-80 % cycling (878 vs 1,650; cells
ranged 780-2,150), Wittman's 15 °C cells (306 vs 170).

## 4. Range of validity

From `ageing.NmcRefit.experimental_range` and `ageing.validity_warnings`:
cycling temperature 0-45 °C, depth of discharge 10-100 %, charge up to 1.67C, discharge up to
3C. The dashboard warns outside this range, and when an energy cell is charged at 0.66C or
faster over half or more of its capacity (the MJ1 cells lost 40-70 % in a few hundred cycles
there). Curves stop at 50 % capacity.

## 5. Known gaps

- Cold physics: optimistic at 5 °C; O'Regan's temperature-dependent functions made it worse
  as a drop-in swap (`scripts/validate_oregan.py`).
- No energy-cell fast-charge term: needs M50 tests above 0.7C (Pozzato et al. 2022, OSF qsabn,
  not yet used).
- No knee; avoiding the lowest state of charge (Luh & Blank) is not captured.
- Second-life NMC fade of modern packs: no open data.
