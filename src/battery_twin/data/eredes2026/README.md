# E-Redes 2026 BTN consumption profiles

- **Source:** E-Redes, "Perfis de Consumo e Injeção 2026" (`Perfil_Consumo_Injeção_E-REDES_2026.xlsx`)
  and its justification document, https://e-redes.pt/en/consumption-and-loss-profiles. The
  profiles settle the consumption of low-voltage customers without interval metering under ERSE
  Diretiva 16/2023. Published by the distribution system operator for market use; no licence is
  stated on the page (see `docs/data_licences.md`).
- **Classes:** BTN A, contracted power above 13.8 kVA (mean 13,878 kWh a year in 2024); B, up to
  13.8 kVA and more than 7,140 kWh a year (10,612 kWh); C, up to 13.8 kVA and at most 7,140 kWh
  (1,987 kWh).

| File | Content |
|---|---|
| `btn_profiles_2026.csv` | 8,760 hours of 2026 in legal time: date, hour (start, 0-23; the clock-change days have 23 and 25 hours), and the share of the year's consumption in that hour for classes A, B and C (each sums to 1). Written by `scripts/import_eredes_profiles.py <xlsx>` from the quarter-hours. |

Used by `battery_twin.site` (home and business batteries).
