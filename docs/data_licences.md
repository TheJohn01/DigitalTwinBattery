# Data licence register

Every dataset in `src/battery_twin/data/`, what the program does with it, and whether it may be
used in a commercial product. The code is MIT (`LICENSE`); the data keep their own licences.

**Role:**
- *model*: the program reads it at run time, or it was fitted into the model's constants
  (`ageing_fit.json`, `calibration.json`, constants in the code).
- *validation*: used only by a check script or a test; the dashboard does not need it.

**Commercial use:**
- *yes*: the licence allows it with attribution.
- *check*: the record states its own terms, which were not re-read for this register.
- *research only*: not for commercial use as it stands.

| Data | Source | Licence | Role | Commercial use |
|---|---|---|---|---|
| `ageing_fit.json`, `calibration.json` | This project's fits | MIT (code) | model | yes |
| `published_ageing.csv` | Values read from Preger 2020, Wittman 2023, Ohneseit 2025, Luh & Blank 2024 | facts from publications, cited | model (ageing fits) | yes, with citation |
| `severson2019_cycle_life.csv`, `severson2019_capacity.csv` | Severson et al. 2019 (Suppl. Table 9); capacity copy from acthelen/battery_digital_twin (MIT) | MIT copy, data credit to Severson et al. | model (LFP fast-charge factor, knee); update evaluation | yes, with citation |
| `lca_degen2024.csv` | Values read from Degen et al. 2024, Fig. 6-7 | facts from a publication, cited | model (LCA factors) | yes, with citation |
| `omie_prices_pt_<year>.csv` | OMIE day-ahead results | OMIE terms of use | model (prices) | check |
| `kirkaldy2024/` | Zenodo 10637534 | CC BY 4.0 | model (NMC calibration) | yes |
| `catenaro2021/` | Catenaro & Onori 2021, Data in Brief | CC BY 4.0 | model (electrolyte factor); validation | yes |
| `schmitt2023/` | Schmitt et al. 2023, J. Electrochem. Soc. | CC BY 4.0 | model (NCA physics); validation | yes |
| `schneider2025/` | Schneider et al. 2025 | CC BY 4.0 | model (sodium-ion physics); validation | yes |
| `gorsch2025/` | Gorsch et al. 2025, Cell Rep. Phys. Sci. | CC BY 4.0 | model (LFP Blade physics) | yes |
| `rebelion2024/` | REBELION, doi 10.21950/GT4LKX | CC BY 4.0 | model (NCA level) | yes |
| `huang2026/` | Huang et al. 2026, values read from figures | CC BY 4.0 article | model (NCA charge-rate term) | yes |
| `zhu2022/` | Zenodo 6405084 | CC BY 4.0 | model (NMC heat term) | yes |
| `yagci2025/` | Zenodo 22939281 | CC BY 4.0 | model (LFP heat term); validation | yes |
| `bahrke2026/` | mediaTUM 10.14459/2026mp1840745 | CC BY 4.0 | model (sodium-ion ageing) | yes |
| `rehm2026/` | mediaTUM 10.14459/2025mp1837893 | the record's terms | model (sodium-ion depth factor) | check |
| `rucker2024/` | RWTH 10.18154/RWTH-2024-01907 (paper CC BY-NC-ND, data CC BY 4.0) | CC BY 4.0 (data) | model (NMC field factors) | yes (data only) |
| `gray2026/` | Gray & Vagg 2026 | CC BY 4.0 | validation (LFP physics and ageing) | yes |
| `figgener2024/` | Figgener et al. 2024, system 10 | CC BY 4.0 | validation (storage model, estimator) | yes |
| `bilfinger2025/` | Bilfinger et al. 2025 | CC BY 4.0 | validation (LFP car, estimator) | yes |
| `kollmeyer2020/` | Mendeley Data b5mj79w5w9 | the record's terms | validation (estimator drive cycles) | check |
| `tum_mj1_2024/` | mediaTUM 1745519 | CC BY 4.0 | validation (NMC, resistance growth) | yes |
| `wheeler2025/` | Recherche Data Gouv 10.57745/OLBXKT | the record's terms | validation (LFP below 80 %) | check |
| `uconn2025/` | UConn REIL Datasets 3 | CC BY 4.0 | validation (LFP second life) | yes |
| `cao2024/` | Cao et al. 2024, values read from the text | CC BY 4.0 article | validation (LFP second life) | yes |
| `eredes2026/` | E-Redes 2026 BTN consumption profiles | published by the DSO for market settlement; no licence stated | model (home and business load) | check |
| `pvgis/` | PVGIS 5.3 (JRC), 2023 | JRC reuse with attribution (Decision 2011/833/EU) | model (PV yield) | yes |
| ERSE 2026 tariffs (constants in `site.py`) | ERSE Diretiva 4/2026 and the daily cycle in force until 2027 | public regulation | model (bills) | yes |
| `popp2024/hppc_pulse_resistance.csv` | Zenodo 13730404 | CC BY 4.0 | validation (resistance spread) | yes |
| `popp2024/samsung50e_steps.csv` | Zenodo 10891871 | CC BY-NC | validation (NCA heating) | **research only** |
| `lam2024/` | OSF ju325 | no licence stated | validation (LFP calendar) | **research only** |

## What a commercial build must drop or license

Neither research-only dataset feeds the model, so dropping them changes no result of the
dashboard; it removes two checks:

- `src/battery_twin/data/popp2024/samsung50e_steps.csv` and `scripts/validate_nca_thermal.py`
  (the NCA heating check; the CC BY archive `hppc_pulse_resistance.csv` may stay).
- `src/battery_twin/data/lam2024/`, `scripts/extract_lam2024.py`,
  `scripts/validate_lfp_calendar.py` and the test
  `tests/test_ageing.py::test_lfp_calendar_within_stanford_cells_at_24_c` (the LFP calendar
  check at 24 °C; the Offenburg heat check in the same script uses `yagci2025` and must move).

Before a commercial release, also confirm the five *check* rows against their records: OMIE's
terms cover the hourly prices, E-Redes's site terms the load profiles; the other three are
validation or a fitted constant.

When new data are added, add a row here and a README in the data folder with source, licence
and the script that made the file.
