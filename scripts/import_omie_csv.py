"""Hourly Portuguese day-ahead prices from yearly OMIE CSV exports (columns date, year,
month, day, hour, price_es, price_pt), in the format of scripts/download_omie_prices.py.

Check first which column is Portugal: in the exports used here (2023-2026) the two zone
columns are swapped. Their "price_pt" means are Spain's published averages (CNMC: 87.10
€/MWh in 2023, 63.04 in 2024), and their "price_es" equals the OMIE Portuguese file the
program used before (every hour of January-September 2025). Hence --zone-column price_es.
Quarter-hour prices (from 1 October 2025: 92, 96 or 100 a day) are averaged to hours.

Run:  python scripts/import_omie_csv.py omie_marginal_prices_2024.csv --zone-column price_es
Writes src/battery_twin/data/omie_prices_pt_<year>.csv (date, hour, price_eur_mwh).
"""
import argparse

import pandas as pd

from battery_twin.constants import DATA_DIR


def hourly(day):
    """One day's prices as hours (1 = 00:00-01:00); quarter-hours are averaged."""
    p = day.sort_values("hour").price.to_numpy()
    if len(p) >= 92:
        p = p.reshape(-1, 4).mean(axis=1)
    return pd.DataFrame({"hour": range(1, len(p) + 1), "price_eur_mwh": p.round(3)})


if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    arg.add_argument("csv", nargs="+")
    arg.add_argument("--zone-column", required=True)
    a = arg.parse_args()
    for path in a.csv:
        d = pd.read_csv(path).rename(columns={a.zone_column: "price"})
        d["date"] = d.date.str[:10]
        out = d.groupby("date").apply(hourly, include_groups=False).reset_index(level=0)
        year = int(out.date.iloc[0][:4])
        days = out.date.nunique()
        dest = DATA_DIR / f"omie_prices_pt_{year}.csv"
        out.to_csv(dest, index=False)
        print(f"{year}: {days} days, {len(out)} hours -> {dest}"
              + ("" if days >= 365 else "  (incomplete year)"))
