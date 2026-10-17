"""Download one year of hourly Portuguese day-ahead prices from OMIE.

The prices are the marginal price of the Portuguese zone of the Iberian day-ahead market
(OMIE, https://www.omie.es). The daily files are fetched with the OMIEData package, but read
here: since 1 October 2025 the files hold 96 quarter-hour prices per day, and OMIEData's own
reader keeps only the first 25 values (00:00-06:15). Quarter-hour prices are averaged to
hourly prices.

Run (on a computer that can reach www.omie.es):
    pip install OMIEData
    python scripts/download_omie_prices.py 2025

Writes src/battery_twin/data/omie_prices_pt_<year>.csv with the columns
    date, hour, price_eur_mwh
(hour 1 = 00:00-01:00; days with a clock change have 23 or 25 hours).
"""
import datetime as dt
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from OMIEData.Downloaders.marginal_price_downloader import MarginalPriceDownloader

PT_LINE = "Precio marginal en el sistema portugu"     # "...portugués (EUR/MWh)" or "(Cent/kWh)"


def parse_day(text):
    """(date, hourly prices in €/MWh) from the text of one OMIE file, or None."""
    lines = text.splitlines()
    dates = re.findall(r"\d\d/\d\d/\d\d\d\d", lines[0]) if lines else []
    if len(dates) != 2:
        return None
    date = dt.datetime.strptime(dates[1], "%d/%m/%Y").date()
    for line in lines:
        if line.startswith(PT_LINE):
            cells = [c.strip() for c in line.split(";")[1:]]
            values = np.array([float(c.replace(".", "").replace(",", ".")) for c in cells if c])
            if "Cent/kWh" in line.split(";")[0]:
                values = values * 10.0                      # c€/kWh -> €/MWh
            if len(values) >= 92:                           # quarter-hours: 92, 96 or 100
                values = values.reshape(-1, 4).mean(axis=1)
            return date, values
    return None


def main(year):
    out = Path(__file__).parents[1] / "src" / "battery_twin" / "data" / f"omie_prices_pt_{year}.csv"
    print(f"Downloading OMIE prices for {year} (one file per day, takes a few minutes)...")
    rows = []
    responses = MarginalPriceDownloader().url_responses(dt.date(year, 1, 1), dt.date(year, 12, 31))
    for response in responses:
        day = parse_day(response.text) if response.ok else None
        if day is None:
            print(f"  skipped {response.url} (no data)")
            continue
        date, prices = day
        rows += [{"date": date, "hour": h + 1, "price_eur_mwh": round(float(p), 3)}
                 for h, p in enumerate(prices)]
    df = pd.DataFrame(rows)
    df.to_csv(out, index=False)
    days = df["date"].nunique()
    print(f"Saved {len(df)} hourly prices for {days} days to {out}")
    if days < 365:
        print("Warning: some days are missing.")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2025)
