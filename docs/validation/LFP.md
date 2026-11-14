# Validation dossier: LFP

Condensed from README sections 4, 6.6, 9 and 10.1; the numbers are the same. Re-run the scripts
named here to reproduce them.

## 1. Cells

| Part | Cell | Note |
|---|---|---|
| Physics | BYD Blade, 135 Ah (Gorsch et al. 2025 teardown; Prada 2013 electrochemistry) | Commercial BEV cell |
| Ageing | Sony-Murata 3 Ah 18650 (NREL BLAST-Lite), cycling scaled to Ohneseit et al.'s 21700 LFP | Different cells of the same chemistry |
| Fast charge, knee | A123 18650 (Severson et al. 2019) | A power cell |
| Heat term | Offenburg 200 Ah stationary cells (Yagci et al. 2025) | |
| LCA | Degen et al. 2024 LFP factors | Cell level |

## 2. Fitted

| What | Data | Script | Fit error |
|---|---|---|---|
| Five Blade physics values (OCP level, two exchange currents, hysteresis, graphite diffusivity) | 280 Ah cell (Gray & Vagg 2026), BYD 4680 (Liu et al. 2025), Blade pulse resistance (Gorsch Fig. 8C) | `scripts/fit_blade.py` | pulse resistance 0.05 mΩ RMS; OCV 8.9 mV RMS |
| Cycling level SCALE | Ohneseit 21700 LFP, 0-100 % at 20 °C, 1C (about 1,600 cycles) | `scripts/fit_ageing.py` | 2C: 1,590 vs about 1,750 |
| Fast-charge factor C_TH, M_CH | Severson's A123 cells, 3.6-8C at 30 °C (82 cells) | `scripts/fit_ageing.py` | typical error ×1.27 |
| Knee κ = 3.31 | 81 Severson cells, cycle by cycle | `scripts/fit_ageing.py` step 0 | 2.7 %-points median RMSE (6.9 without) |
| Heat term K_HOT | Offenburg cells at 36.5 and 52 °C | `scripts/fit_ageing.py` step 3 | 52 °C cells 2.2 %-points RMS |

## 3. Independent checks

| Data (not used in the fit) | Script | Result | Verdict |
|---|---|---|---|
| BYD 4680 pulse resistance | `scripts/validate_blade.py` | 10-14 vs 6-17 Ω·cm² | good |
| 280 Ah cell R(T), C/10 voltage | `scripts/validate_blade.py` | R(15, 35 °C) 1.26, 0.82 vs 1.31, 0.81; 10 mV RMS | good |
| 280 Ah cell, 700 cycles at 1C, about 40 °C | `scripts/validate_blade.py` | 90.0 vs 92.9 % (1.4 %-points RMS) | slightly pessimistic |
| Stanford K2 cells stored 7.5 years at 24 °C (research-only data) | `scripts/validate_lfp_calendar.py` | within the two cell types (±1.5 points) | good at room temperature |
| Stanford cells at 45 °C, 4 years | `scripts/validate_lfp_calendar.py` | 14-18 vs 24-30 % | optimistic in the heat |
| Offenburg storage at 35 and 50 °C | `scripts/validate_lfp_calendar.py` | 0.2-4.6 points pessimistic | fair |
| 20 A123 cells to 31-64 % at 50 °C (Wheeler et al. 2025) | `scripts/validate_lfp_wheeler.py` | steady fade at 70 % depth (R 1.09 vs 1.04-1.45); life ×1.2-1.8 too long at 50 °C | shape good, level optimistic in the heat |
| Two UConn cells after a knee | `scripts/validate_lfp_second_life.py` | model loses 16-23 times less | fails after a knee (the dashboard's car never reaches one) |
| Four Cao et al. 2024 100 Ah cells at 23 °C | `scripts/validate_lfp_second_life.py` | measured / model loss 0.43-0.82 | pessimistic for large stationary cells |
| TUM Tesla Model 3, 80,100 km (Bilfinger et al. 2025) | `scripts/fit_field_ageing.py` | 91.4-94.4 vs 91.9 % | good |
| 21 home storage systems (Figgener et al. 2024) | `scripts/fit_field_ageing.py` | 1.5-1.6 points a year vs 2.0 (operating data) and 2.2 (capacity tests) | slightly optimistic |
| AVILOO fleet, LFP at 100,000 km (grey literature) | `tests/test_ageing.py` | 90.3 vs 93.3 % | pessimistic |

## 4. Range of validity

From `ageing.LfpAdjusted.experimental_range`: cycling temperature 20-50 °C, depth of discharge
80-100 %, charge up to 6C, discharge up to 2C. No data between 0.5 and 3.6C charge, none for
fast charging below 30 °C, and no cold-charge (plating) term: cold results are optimistic and
the dashboard warns below 20 °C. Curves stop at 50 % capacity.

## 5. Known gaps

- The knee is fitted to fast-charged cells only; slowly charged cells measured so far fade
  steadily, but Ohneseit's dropped after about 2,200 cycles.
- Calendar loss in the heat beyond two years.
- A second life that remembers a first-life knee.
- The Blade's own rate capability and resistance at 10 and 40 °C (not read).
