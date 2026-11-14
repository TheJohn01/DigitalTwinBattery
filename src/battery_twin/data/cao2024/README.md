# Commercial 100 Ah LFP cells, new and retired from electric forklifts (Cao et al. 2024)

- **Source:** Z. Cao, W. Gao, Y. Fu, C. Turchiano, N. Vosoughi Kurdkandi, J. Gu, C. Mi.
  *Second-Life Assessment of Commercial LiFePO4 Batteries Retired from EVs.* Batteries 10, 306
  (2024), https://doi.org/10.3390/batteries10090306, CC BY 4.0. Values read from the text and
  Table 2 (no raw data published).
- **Cells:** prismatic LFP / graphite, 100 Ah rated (107 Ah measured when new). Cells 01 and 02
  new; cells 03 and 04 retired from electric forklifts after four years. Cycled at 23 °C
  (cell 03 partly at a higher, unstated temperature), mostly at 60 A charge (0.56C) and
  100 A discharge (0.93C) between about 2.8-3.1 V and 3.45-3.6 V; the windows and currents
  changed between stages (their Fig. 4). Depth per cycle = full equivalent cycles / cycles
  (0.77 for cell 01, 0.59 for cells 03 and 04; not given for cell 02).

| Column | Content |
|---|---|
| `start_pct`, `end_pct` | capacity at the start and end of the test, % of 107.1 Ah |
| `cycles`, `fec` | test cycles and full equivalent cycles (empty: not given) |
| `temp_c` | chamber temperature (empty: partly unstated) |

Used by `scripts/validate_lfp_second_life.py`.
