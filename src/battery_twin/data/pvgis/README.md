# PVGIS hourly PV yield, 2023

- **Source:** PVGIS 5.3, European Commission Joint Research Centre,
  https://re.jrc.ec.europa.eu/pvg_tools/ (API `seriescalc`, SARAH-3 radiation). Reuse of JRC
  data with attribution (Commission Decision 2011/833/EU).
- **Settings:** crystalline silicon, 1 kWp, 14 % system losses, fixed mounting at the optimal
  tilt and azimuth for each site; Lisboa (38.722, -9.139), Porto (41.150, -8.611), Faro
  (37.019, -7.930).

| File | Content |
|---|---|
| `pv_yield_2023.csv` | 8,760 hours of 2023 in Portuguese legal time: date, hour (start, 0-23), and kWh per kWp for each site. Yearly: Lisboa 1,611, Porto 1,519, Faro 1,778 kWh/kWp. Written by `scripts/download_pvgis.py`. |

Used by `battery_twin.site`; the year is lined up with the 2026 load profiles by month, day and
hour.
