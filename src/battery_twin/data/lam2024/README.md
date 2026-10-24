# Stanford long-term calendar ageing: K2 Energy LFP cells (Lam et al.)

- **Data:** V. Lam et al., *A decade of insights:
  delving into calendar aging trends and implications*, Joule (2024/2025). Data on OSF
  (osf.io/ju325); cell list `Joule_cell_id.csv` in github.com/viveklam/Joule-Decade-Calendar-Aging.
  The OSF record and the repository state no licence; only these derived capacities are kept,
  with attribution, for the model check.
- **Cells:** K2 Energy LFP18650E and LFP18650P (LFP / graphite 18650), five cells per
  condition, stored at 24 and 45 °C at 50 and 100 % SOC (60 and 85 °C cells not kept).

| File | Content |
|---|---|
| `lfp_calendar.csv` | One row per cell and diagnostic (3,254, 40 cells): cell, cell type, temperature, SOC, days since the first diagnostic, first C/5 discharge capacity [Ah] (`RPT0.2C_0_D_capacity` of the summary files). Written by `scripts/extract_lam2024.py <joule_declass_sum folder> Joule_cell_id.csv`. |

Median capacity left: 24 °C after 7.5 years 85.6 / 91.9 % (18650E / P, 50 % SOC) and 82.3 / 86.3 %
(100 % SOC); 45 °C after 4 years 75.8 % (18650E, 50 %) and 70.1 / 74.1 % (100 %).

Used by `scripts/validate_lfp_calendar.py`: the LFP calendar term at room temperature over a
second life's span, and in the heat.
