# Smart e.d. fleet capacity tests (Rücker et al., 2024)

- **Paper:** F. Rücker, J. Figgener, I. Schoeneberger, D. U. Sauer. *Battery electric vehicles in
  commercial fleets: Use profiles, battery aging, and open-access data.* J. Energy Storage 86
  (2024) 111030. https://doi.org/10.1016/j.est.2024.111030
- **Data:** RWTH Aachen, doi:10.18154/RWTH-2024-01907, CC BY 4.0 (the paper itself is CC BY-NC-ND;
  only the measured values are used here).
- **Cars:** six Smart e.d. (3rd generation, 17.6 kWh, Li-Tec HEA50 NMC/graphite cells, 93 in
  series) in Berlin (geriatric care and urban carsharing) and Steyerberg (rural carsharing),
  2014-2016; usually charged at 11 kW (about 0.55C).

| File | Content |
|---|---|
| `smart_capacity_tests.csv` | Table D.13: 1C discharge tests on a chassis dynamometer (and two laboratory pack tests), with the capacity in the fixed voltage window 3.914-3.357 V per cell. Initial capacity in that window: 40.76 Ah (Table 6). |

Used by `scripts/fit_field_ageing.py` for the NMC car first life (`ageing.EV_FIELD_SCALE`).
Tests below 12 °C are left out: a cold battery gives less capacity in the window (the paper
notes this for Smart-3 at 6.5 °C).
