"""Hourly PV yield per kWp for three Portuguese cities from PVGIS -> data/pvgis/pv_yield_2023.csv.

PVGIS 5.3 (European Commission, Joint Research Centre), hourly radiation series (SARAH-3) for
2023, crystalline silicon, 1 kWp, 14 % system losses, fixed mounting at the optimal tilt and
azimuth PVGIS computes for each site. The UTC timestamps are converted to Portuguese legal
time, so the rows line up with the E-Redes load profiles (date, hour starting 0-23; the
clock-change days have 23 and 25 hours). Reuse of JRC data: Commission Decision 2011/833/EU,
with attribution.

Run (on a computer that can reach re.jrc.ec.europa.eu):
    python scripts/download_pvgis.py
"""
import json
import urllib.request

import pandas as pd

from battery_twin.constants import DATA_DIR

OUT = DATA_DIR / "pvgis" / "pv_yield_2023.csv"
SITES = {"Lisboa": (38.722, -9.139), "Porto": (41.150, -8.611), "Faro": (37.019, -7.930)}
URL = ("https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?lat={lat}&lon={lon}&peakpower=1&loss=14"
       "&pvcalculation=1&optimalangles=1&startyear=2023&endyear=2023&outputformat=json")


def site_yield(lat, lon):
    """kWh per kWp in each hour of 2023, indexed by UTC time."""
    with urllib.request.urlopen(URL.format(lat=lat, lon=lon), timeout=120) as r:
        hourly = json.load(r)["outputs"]["hourly"]
    d = pd.DataFrame(hourly)
    t = pd.to_datetime(d.time, format="%Y%m%d:%H%M", utc=True).dt.floor("h")
    return pd.Series(d.P.to_numpy() / 1000.0, index=t)


if __name__ == "__main__":
    series = {name: site_yield(*xy) for name, xy in SITES.items()}
    d = pd.DataFrame(series)
    local = d.index.tz_convert("Europe/Lisbon")
    d.insert(0, "date", local.strftime("%Y-%m-%d"))
    d.insert(1, "hour", local.hour)
    OUT.parent.mkdir(exist_ok=True)
    d.round(4).to_csv(OUT, index=False)
    print(d[list(SITES)].sum().round(0).to_string(), f"\nkWh/kWp a year; written {OUT}")
