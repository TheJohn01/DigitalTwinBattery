# Validation dossier: sodium-ion

Condensed from README sections 4, 6.7 and 10.1; the numbers are the same. Re-run the scripts
named here to reproduce them.

## 1. Cells

| Part | Cell | Note |
|---|---|---|
| Physics | Mushang NA18650-1250 (layered oxide / hard carbon), Schneider et al. 2025 | Commercial cell; PyBaMM's DFN equations |
| Ageing | The same Mushang cell (TUM: Bahrke et al. 2026, Rehm et al. 2026) | Same cell as the physics |
| LCA | Degen et al. 2024 sodium-ion factors (NaNFM442) | A different sodium-ion cell |

## 2. Fitted

| What | Data | Script | Fit error |
|---|---|---|---|
| Calendar loss K_CAL(SOC) √years | 24 cells stored at 10-90 % SOC for 1.5 years | `scripts/fit_sodium.py` | median of three cells per SOC |
| Cycling loss per full cycle (0.0175 %, median; worst 0.034 %) | Four cells cycled 0-100 % at 1C | `scripts/fit_sodium.py` | 80 % after 532-1,361 cycles (the cells differ) |
| Depth factor 0.068 at 60 % depth (worst 0.46) | Four cells at 20-80 % (Rehm et al. 2026) | `scripts/fit_sodium.py` | calendar part removed |

## 3. Independent checks

| Data (not used in the fit) | Script | Result | Verdict |
|---|---|---|---|
| Schneider et al.'s discharges, C/100 to 5C at 25 °C | `scripts/validate_sodium.py` | 18-49 mV RMS (theirs 10-52), capacity within 2 %, warming 2.9 vs 3.2 K at 1C, 15.4 vs 17.2 K at 5C | good |
| Rehm et al. 2025 round-trip efficiency | `scripts/validate_sodium.py` | 93.9 vs 89-92 % at 1C | about 2 points high (no hysteresis) |
| 20 % windows at every SOC (TUM) | `tests/test_ageing.py` | loss equals the calendar loss | good |

## 4. Range of validity

From `ageing.SodiumIon.experimental_range`: cycling temperature 25-40 °C, depth of discharge
20-100 %, charge and discharge up to 1C, up to 2,800 cycles. The physics' temperature
dependence was measured at 10-40 °C; below 10 °C it is extrapolated, and fast charging in the
cold can stop the solver (the program retries other meshes, then reports an error). No
temperature term in the ageing: cells stored at 45 °C aged no faster than at 25 °C.

## 5. Known gaps

- 80 % depth is interpolated between 60 and 100 %; storage beyond 1.5 years is extrapolated.
- Below 80 %: the full-depth cells kept falling faster than the straight line.
- Other makers' cells fade faster (0.05 %/cycle, Liu et al. 2026): the cycling rate is a
  sidebar input.
- No pulse resistance in the check-ups in hand, so resistance growth is unchecked.
