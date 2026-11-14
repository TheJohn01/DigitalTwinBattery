"""A battery at a home or a business: a year of hourly load, PV and tariffs.

Two uses besides grid arbitrage (economics.daily_arbitrage):
- "self": PV self-consumption (homes). The battery charges from PV surplus and discharges to
  cover the load; it never charges from the grid.
- "tou": time-of-use shifting with PV (businesses). As "self", plus: it charges from the grid
  in the off-peak (vazio) hours, and in the peak (ponta) hours it discharges first, which lowers
  the billed peak-hour power. It keeps its discharge for the peak hours.

The result is mapped onto the inputs of economics.calculate_tea (site_tea_inputs), so the
cash flows, retirement, sensitivity and reports are those of the arbitrage case.

Data:
- Load: E-Redes 2026 BTN profiles A, B, C (data/eredes2026), or the user's own meter data.
- PV: PVGIS 5.3 hourly yield per kWp, 2023 (data/pvgis), for Lisboa, Porto and Faro.
- Tariffs: ERSE Diretiva 4/2026 (prices from 1 October 2026, "período IV"), transitional
  tariffs of the last-resort supplier, without VAT and taxes: BTN up to 20.7 kVA (simple,
  bi-hourly, tri-hourly), BTE and MT (four periods, power in peak hours). Time periods: the
  daily cycle in force until 2027 (ERSE; Diretiva 3/2026 moves it from 2027).
- Surplus sold at 90 % of the hourly OMIE price (assumption: the order of a self-consumer's
  sale to an aggregator; check the actual contract).
shortcut: hourly steps (contracted power, a 15-minute maximum, is not reduced in the results);
upgrade with 15-minute meter data.
"""
import numpy as np
import pandas as pd

from .constants import DATA_DIR
from .economics import load_prices, price_index_from_base

PROFILES = DATA_DIR / "eredes2026" / "btn_profiles_2026.csv"
PV_FILE = DATA_DIR / "pvgis" / "pv_yield_2023.csv"
PROFILE_CLASSES = {"btn_a": "BTN A (above 13.8 kVA)",
                   "btn_b": "BTN B (up to 13.8 kVA, over 7,140 kWh a year)",
                   "btn_c": "BTN C (up to 13.8 kVA, up to 7,140 kWh a year)"}
PV_SITES = ("Lisboa", "Porto", "Faro")
TARIFF_YEAR = 2026
EXPORT_SHARE_OF_OMIE = 0.90

# ERSE Diretiva 4/2026, período IV, without VAT. Energy €/kWh by period; power €/(kW.day) in
# peak hours (BTE, MT). The fixed and contracted-power terms do not change with a battery.
TARIFFS = {
    "BTN simple": {"periods": "flat", "energy": {"all": 0.1711}},
    "BTN bi-hourly": {"periods": "bi", "energy": {"fora_vazio": 0.2045, "vazio": 0.1143}},
    "BTN tri-hourly": {"periods": "tri",
                       "energy": {"ponta": 0.2553, "cheias": 0.1747, "vazio": 0.1143}},
    "BTE": {"periods": "tetra", "peak_power": 0.5521,
            "energy": {"ponta": 0.1577, "cheias": 0.1452, "vazio_normal": 0.1211,
                       "super_vazio": 0.1083}},
    "MT": {"periods": "tetra", "peak_power": 0.2435,
           "energy": {"ponta": 0.1279, "cheias": 0.1190, "vazio_normal": 0.0998,
                      "super_vazio": 0.0917}},
}

# ERSE daily cycle (in force until 2027), half hours from 00:00. Ponta: winter 09:00-10:30 and
# 18:00-20:30, summer 10:30-13:00 and 19:30-21:00; cheias the rest of 08:00-22:00; vazio
# 22:00-08:00, of which super vazio 02:00-06:00. Summer = legal summer time.
_PONTA = {False: [(18, 21), (36, 41)], True: [(21, 26), (39, 42)]}   # half-hour slots [a, b)


def _slot_period(slot, summer):
    """Tetra-hourly period of a half-hour slot (0 = 00:00-00:30)."""
    if 4 <= slot < 12:
        return "super_vazio"
    if slot < 16 or slot >= 44:
        return "vazio_normal"
    if any(a <= slot < b for a, b in _PONTA[summer]):
        return "ponta"
    return "cheias"


def period_shares(hours, summer, periods):
    """Share of each tariff period in each hour (two half-hour slots): dict period -> array."""
    names = {"flat": ["all"], "bi": ["fora_vazio", "vazio"], "tri": ["ponta", "cheias", "vazio"],
             "tetra": ["ponta", "cheias", "vazio_normal", "super_vazio"]}[periods]
    out = {n: np.zeros(len(hours)) for n in names}
    for half in (0, 1):
        for i, (h, s) in enumerate(zip(hours, summer)):
            p = _slot_period(2 * h + half, s)
            if periods == "flat":
                p = "all"
            elif periods == "bi":
                p = "fora_vazio" if p in ("ponta", "cheias") else "vazio"
            elif periods == "tri" and p in ("vazio_normal", "super_vazio"):
                p = "vazio"
            out[p][i] += 0.5
    return out


def _by_day_hour(df, column):
    """Mean of a column by (month-day, hour) of legal time, for lining up different years."""
    key = df["date"].str[5:] + " " + df["hour"].astype(str)
    return df.groupby(key, sort=False)[column].mean()


def year_frame(profile="btn_c", annual_kwh=3000.0, pv_kwp=0.0, pv_site="Lisboa", load=None):
    """One year of hours (the 2026 calendar of the E-Redes profiles): date, hour, summer, load
    [kWh], pv [kWh], OMIE price [€/kWh]. load: the user's own hourly series of the same length
    (read_load_csv), else the profile times annual_kwh."""
    d = pd.read_csv(PROFILES)
    d["load"] = (annual_kwh * d[profile] / d[profile].sum() if load is None    # exact after rounding
                 else np.asarray(load, dtype=float))
    key = d["date"].str[5:] + " " + d["hour"].astype(str)
    d["pv"] = pv_kwp * key.map(_by_day_hour(pd.read_csv(PV_FILE), pv_site)).fillna(0.0)
    prices = load_prices()
    prices = prices.assign(hour=prices["hour"] - 1)                 # OMIE hour 1 = 00:00-01:00
    d["omie"] = key.map(_by_day_hour(prices, "price_eur_mwh")).ffill().bfill() / 1000.0
    noon = pd.to_datetime(d["date"]) + pd.Timedelta(hours=12)
    d["summer"] = [t.dst().total_seconds() > 0 for t in noon.dt.tz_localize("Europe/Lisbon")]
    return d[["date", "hour", "summer", "load", "pv", "omie"]]


def read_load_csv(df, hours=8760):
    """Hourly load [kWh] from a table whose first column is a date-time and second the energy
    of each interval [kWh] (15-minute or hourly), at least a year. Returns a series in the
    order of the profile year (by month-day and hour), scaled to the file's yearly total.
    Raises ValueError if the data cannot be used."""
    if df.shape[1] < 2:
        raise ValueError("Need two columns: date-time and kWh.")
    t = pd.to_datetime(df.iloc[:, 0], errors="coerce", dayfirst=False)
    e = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    ok = t.notna() & e.notna()
    if (e[ok] < 0).any():
        raise ValueError("Negative energy values.")
    s = pd.Series(e[ok].to_numpy(), index=t[ok]).sort_index()
    if len(s) < 2 or s.index[-1] - s.index[0] < pd.Timedelta(days=364):
        raise ValueError("Need at least a year of data.")
    hourly = s.resample("h").sum()
    frame = pd.DataFrame({"date": hourly.index.strftime("%Y-%m-%d"),
                          "hour": hourly.index.hour, "kwh": hourly.to_numpy()})
    shape = _by_day_hour(frame, "kwh")
    prof = pd.read_csv(PROFILES)
    key = prof["date"].str[5:] + " " + prof["hour"].astype(str)
    out = key.map(shape).fillna(0.0).to_numpy()
    yearly = hourly.sum() * 8760 / max(len(hourly), 1)
    return out * yearly / out.sum() if out.sum() > 0 else out


def simulate_site(year, capacity_kwh, power_kw, dod=0.8, rte=0.9, mode="self", shares=None):
    """Hour-by-hour operation for one year. year: year_frame. The battery cycles between
    50 % -/+ dod/2 of capacity_kwh, at most power_kw, with the round-trip losses split evenly
    between charge and discharge. shares: period_shares of the tariff ("tou" needs it).
    Returns a DataFrame per hour: import, export, charge (from PV and grid), discharge [kWh]."""
    load, pv = year["load"].to_numpy(), year["pv"].to_numpy()
    eta = np.sqrt(rte)
    e_min, e_max = capacity_kwh * (0.5 - dod / 2), capacity_kwh * (0.5 + dod / 2)
    peak = shares.get("ponta", np.zeros(len(load))) if shares else np.zeros(len(load))
    off = (shares.get("vazio", 0) + shares.get("vazio_normal", 0) + shares.get("super_vazio", 0)
           if shares else np.zeros(len(load)))
    e = e_min
    rows = np.zeros((len(load), 5))            # import, export, charge PV, charge grid, discharge
    for k in range(len(load)):
        net = load[k] - pv[k]
        ch_pv = min(max(-net, 0.0), power_kw, (e_max - e) / eta)
        e += ch_pv * eta
        ch_grid = 0.0
        if mode == "tou" and off[k] >= 0.5:            # off-peak: fill up from the grid
            ch_grid = min(power_kw - ch_pv, (e_max - e) / eta)
            e += ch_grid * eta
        dis = 0.0
        if net > 0 and (mode == "self" or peak[k] > 0):        # "tou" keeps it for the peak
            dis = min(net, power_kw, (e - e_min) * eta)
            e -= dis / eta
        rows[k] = (max(net, 0.0) - dis + ch_grid, max(-net, 0.0) - ch_pv, ch_pv, ch_grid, dis)
    return pd.DataFrame(rows, columns=["import", "export", "charge_pv", "charge_grid",
                                       "discharge"])


def bill(year, flows, tariff_name):
    """Yearly cost [€] that the battery can change: energy bought by period, the peak-hour
    power charge (BTE, MT: monthly peak-hour energy / peak hours, times the days), minus the
    surplus sold. flows: simulate_site output, or {"import": load - pv, "export": ...}."""
    t = TARIFFS[tariff_name]
    shares = period_shares(year["hour"], year["summer"], t["periods"])
    imp, exp = np.asarray(flows["import"]), np.asarray(flows["export"])
    energy = sum(float(np.sum(imp * shares[p])) * price for p, price in t["energy"].items())
    power = 0.0
    if "peak_power" in t:
        month = year["date"].str[:7].to_numpy()
        for m in np.unique(month):
            sel = month == m
            hours = shares["ponta"][sel].sum()
            power += t["peak_power"] * np.sum(imp[sel] * shares["ponta"][sel]) / hours * sel.sum() / 24
    sold = EXPORT_SHARE_OF_OMIE * float(np.sum(exp * year["omie"].to_numpy()))
    return energy + power - sold, power


def site_tea_inputs(year, flows, tariff_name, capacity_kwh, rte):
    """The battery's effect on the bill as inputs of economics.calculate_tea, in 2025 money
    (the base year of its prices): electricity_price = mean value of a kWh charged (the sale
    forgone or the grid price), spread = mean value of a kWh delivered minus that, so that
    revenue - charging cost = the energy saving; the peak-power saving as a fixed yearly
    saving; dod = energy delivered a year / (365 x capacity), one cycle a day.
    Returns (TEA inputs, the yearly bill saving in 2025 €), or (None, 0) if it never discharges."""
    t = TARIFFS[tariff_name]
    no_battery = {"import": np.maximum(year["load"] - year["pv"], 0.0),
                  "export": np.maximum(year["pv"] - year["load"], 0.0)}
    cost0, power0 = bill(year, no_battery, tariff_name)
    cost1, power1 = bill(year, flows, tariff_name)
    deflate = price_index_from_base(TARIFF_YEAR)
    out = float(flows["discharge"].sum())
    charged = float(flows["charge_pv"].sum() + flows["charge_grid"].sum())
    if out <= 0:
        return None, 0.0
    energy_saving = (cost0 - power0) - (cost1 - power1)
    shares = period_shares(year["hour"], year["summer"], t["periods"])
    grid_price = sum(shares[p] * v for p, v in t["energy"].items())
    buy = (EXPORT_SHARE_OF_OMIE * float(np.sum(flows["charge_pv"] * year["omie"]))
           + float(np.sum(flows["charge_grid"] * grid_price))) / charged
    sell = (energy_saving + buy * charged) / out
    return ({"electricity_price": float(buy / deflate), "spread": float((sell - buy) / deflate),
             "round_trip_eff": rte, "cycles_per_year": 365,
             "dod": out / (365 * capacity_kwh),
             "fixed_savings_eur_yr": float((power0 - power1) / deflate)},
            float((cost0 - cost1) / deflate))
