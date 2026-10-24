# Sodium-ion cells cycled 20-80 % at 1C (TUM)

Capacity (SOH, relative to the first check-up) against equivalent full cycles of four
commercial Mushang NA18650-1250 cells (CY_18650-12P-Na: NaNiFeMn layered oxide / hard
carbon, 1.25 Ah; the cell of the sodium-ion physics model), cycled between 20 and 80 % SOC
at 1C in a 25 °C chamber, check-ups every ~200 EFC.

Source: Rehm et al., "Aging of commercial sodium-ion batteries with layered oxides: how to
measure and analyze it?", EES Batteries (2026), doi 10.1039/D5EB00221D; data mediaTUM,
doi 10.14459/2025mp1837893 (`1_cyclig aging data/cycling_aging_data.mat`, a MATLAB table,
read with the `mat-io` package). `sodium_20_80_1c.csv` keeps the columns `Battery_serial`,
`EFC` and `SOH`. Used for `ageing.SodiumIon.PARTIAL_FACTOR` (median fade per EFC at the last
check-up, after taking out the calendar loss of data/bahrke2026, over the same cell's
full-depth rate; `scripts/fit_sodium.py`).
