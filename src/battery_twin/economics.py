"""Techno-economic analysis (TEA) of a battery doing energy arbitrage.

Method. The analysis follows the framework of ISO/TS 14076:2025 (environmental
techno-economic assessment, eTEA): goal and scope with the same functional unit as the LCA
(1 kWh delivered), technical analysis (the physics and ageing models), economic analysis
(below), life cycle assessment (environment.py), sensitivity analysis and a combined
interpretation, with all assumptions, parameters and sources documented (tea_documentation).
The economic analysis is a life-cycle costing in the sense of IEC 60300-3-3:2017 and
ISO 15686-5:2017: a cost breakdown into acquisition (CAPEX), operation (charging energy,
grid fees), maintenance (O&M, warranty) and taxes, discounted to a net present value. All
cash flows are NOMINAL (prices rise with inflation), consistent with the nominal discount
rate. CAPEX and O&M are 2025 prices, raised to the year before operation starts.
No disposal cost (see below).

The battery's capacity in each cycle comes straight from the ageing curve. When the
capacity drops below the retirement threshold, or the curve ends because the measured data
end, the battery is retired: from then on it earns nothing and costs nothing to operate.

Data (dollar values converted to euro at the ECB 2025 average, 1.1300 USD per EUR):
- System cost: NREL, Cole et al. (2025), Cost Projections for Utility-Scale Battery
  Storage: 2025 Update (NREL/TP-6A40-93281): 4-hour system, 2025 mid projection $321/kWh,
  lifetime 15 years, round-trip efficiency 85 %. NREL's system is LFP based.
- Chemistry difference: Benchmark Mineral Intelligence, Lithium Ion Battery Cell Price
  Assessment, June 2025: weighted average cell prices LFP $50.2, NCM $66.0, NCA
  $71.7/kWh. Sodium-ion: Keiner et al. (2026), J. Energy Storage 146, 119861: sodium-ion
  cells about 93 €/kWh in 2023, the same as LFP, so the LFP price is used.
- Balance of system (second life): NREL system cost minus the BloombergNEF (December
  2025) stationary pack price, $70/kWh.
- Systems bought later (the second life): NREL's mid projection for the year of purchase (the
  year before operation; Cole et al. 2025, Table 2: $257/kWh in 2033, 2024 dollars), for the
  new system and, in proportion, for the balance of system; then raised by inflation.
- Operation and maintenance: Lazard's Levelized Cost of Storage, version 7.0 (2021):
  general O&M $1.53/kWh per year, rising 2.5 % per year, plus a warranty of 0.9 % of the
  capital cost per year from year 3. Lazard's augmentation cost is NOT included, because
  this program models the fade itself.
- Round-trip efficiency: Viswanathan et al. (2018), PNNL-27237: at 1C the measured
  round-trip efficiency was 91 % without and 83 % with auxiliary loads and rest periods;
  the simulated cell efficiency is multiplied by 83/91.
- Grid fees: ERSE Regulamento Tarifário (Regulamento n.º 1218/2025), article 56: storage
  that does not take part in self-consumption is exempt from network access tariffs on
  energy that is later fed back, until the end of 2029. ERSE Orientação n.º 1/2026:
  system regulation charges exempt on charging, and on injection below 10 MVA. For 2030
  onwards the user chooses: exemption continues, or the 2026 access tariff (ERSE
  Diretiva n.º 10/2025) for MT or BTE.
- Corporate income tax (IRC): 19 % in 2026, 18 % in 2027, 17 % from 2028 (EY Tax Alert on
  the 2026 State Budget, Proposta de Lei n.º 16/XVII). Tax depreciation straight-line at
  20 % a year (PwC: electronic equipment; batteries are not listed). Losses carried forward
  without time limit, deductible up to 65 % of a year's taxable income (PwC).
- Discount rate: Steffen (2020), Energy Economics 88, 104783, Table 2: after-tax nominal
  WACC for Portugal (onshore wind, the closest technology with data), 7.4 %.
- Electricity prices: hourly day-ahead prices of the Portuguese zone of OMIE
  (data/omie_prices_pt_<year>.csv, written by scripts/download_omie_prices.py).
- Second life: NREL B2U Repurposing Cost Calculator (June 2020) at its defaults (5 kWh
  modules at 70 % capacity, 1 GWh a year, regional collection): repurposing (collection,
  testing, labour, facility, warranty) $24.38 per nameplate kWh, battery bought for $19.62
  per nameplate kWh ($28.03 per kWh left). Dong et al. (2023), iScience 26, 107195:
  repurposed EV batteries sell for $44-180/kWh.

- Inflation of electricity prices and grid fees: Banco de Portugal, Boletim Económico June
  2026, HICP projections 3.1 % (2026), 2.4 % (2027), 2.0 % (2028); then the ECB's 2 % target.
- Write-off of the remaining book value at retirement: CIRC art. 38 (now 31.º-B), exceptional
  write-off, accepted if a justified statement is sent to the AT by the end of the following
  month (AT binding ruling PIV 693, 2010).
- No state surcharge (derrama estadual): CIRC art. 87.º-A taxes only taxable profit above
  €1.5M. No municipal surcharge: most municipalities charge 1.5 % (Ofício Circulado
  20288/2026, period 2025), but many, Lisbon among them, exempt companies with a turnover
  of at most €150,000 in the previous period, which covers a battery of this size.
- No disposal cost: Regulation (EU) 2023/1542, art. 61(1): producers take back waste
  industrial and EV batteries free of charge.

Assumptions (documented in tea_documentation): the battery system depreciated at the rate for
"electronic equipment" (DR 25/2009 lists no battery storage; art. 5(3) accepts a rate the AT
finds reasonable for the useful life); a repurposed battery is a used asset (art. 5(2)(a):
depreciated over its remaining useful life), but it is only about a fifth of the second-life
cost, so the whole system keeps the 20 % rate; first year of operation 2026.
"""
import inspect
from pathlib import Path

import numpy as np
import numpy_financial as npf
import pandas as pd

from .constants import CFB_MIN_EOL_SOH, DATA_DIR

# --- Sourced data ------------------------------------------------------------------------
USD_PER_EUR = 1.1300                  # ECB reference rate, 2025 annual average
NREL_SYSTEM_USD_KWH = 321.0           # Cole et al. 2025, 4-hour system, 2025 (mid)
# Cole et al. 2025, Table 2: mid projection of the 4-hour system cost, 2024 $/kWh (before inflation)
NREL_MID_USD_KWH = {2025: 321, 2026: 308, 2027: 301, 2028: 293, 2029: 286, 2030: 279, 2031: 272, 2032: 265, 2033: 257, 2034: 250, 2035: 243, 2036: 239, 2037: 234, 2038: 230, 2039: 226, 2040: 221, 2041: 217, 2042: 213, 2043: 209, 2044: 204, 2045: 200, 2046: 196, 2047: 191, 2048: 187, 2049: 183, 2050: 178}
NREL_LIFETIME_YEARS = 15
NREL_SYSTEM_RTE = 0.85                # whole system, AC to AC
BNEF_STATIONARY_PACK_USD_KWH = 70.0
BENCHMARK_CELL_USD_KWH = {"LFP": 50.2, "NMC": 66.0, "NCA": 71.7}   # June 2025, weighted avg
# Sodium-ion: no market price yet; Keiner et al. 2026 estimate the same cell cost as LFP.
PACK_PRICE_BASIS = {"NMC": "NMC", "NCA": "NCA", "LFP": "LFP", "Na-ion": "LFP"}
LAZARD_OM_USD_KWH_YR = 1.53
LAZARD_OM_ESCALATION = 0.025
LAZARD_WARRANTY_PCT = 0.009
LAZARD_WARRANTY_START_YEAR = 3
STEFFEN_WACC_PORTUGAL = 0.074
# Lazard's capital structure (80 % equity at 12 %, 20 % debt at 8 %, 21 % tax): high case
LAZARD_WACC = 0.8 * 0.12 + 0.2 * 0.08 * (1 - 0.21)
B2U_REPURPOSING_USD_KWH = 24.38        # per nameplate kWh (labour is per module, not per kWh left)
B2U_BUY_USD_KWH_LEFT = 19.62 / 0.70    # price paid for the used battery, per kWh it still holds
SECOND_LIFE_PACK_RANGE_USD = (44.0, 180.0)
# PNNL-27237, Table 2.2, 1C: 83 % at the grid with auxiliary loads and rests, 91 % without
# auxiliary loads (the battery). The simulated cell efficiency is multiplied by this ratio.
PNNL_RTE_WITH_AUX, PNNL_RTE_NO_AUX = 0.83, 0.91
POWER_CONVERSION_RTE = PNNL_RTE_WITH_AUX / PNNL_RTE_NO_AUX
IRC_RATE = {2026: 0.19, 2027: 0.18}   # 17 % from 2028 (IRC_RATE_FROM_2028)
IRC_RATE_FROM_2028 = 0.17
IRC_RATE_BEFORE_2026 = 0.20           # 2025 rate; only used if start_year is set before 2026
# Tax depreciation (PwC Worldwide Tax Summaries, Portugal, Corporate - Deductions, reviewed
# 24 July 2026): maximum straight-line rates, e.g. electronic equipment 20 %, engines and
# machine tools 12.5 %. Batteries are not listed; "electronic equipment" is the closest
# category for a battery system with its power electronics. The minimum rate is half the
# maximum (Decreto Regulamentar 25/2009, as explained by the Ordem dos Contabilistas
# Certificados, parecer PT27497, 2023).
TAX_DEPRECIATION_RATE = 0.20
# Tax losses: carried forward without time limit, but deductible up to 65 % of the taxable
# income of a year (PwC, Net operating losses).
TAX_LOSS_CAP = 0.65
GRID_FEE_EXEMPT_UNTIL = 2029          # Regulamento Tarifário, art. 56
# 2026 network access tariffs (ERSE Diretiva 10/2025, art. 15): energy in "horas cheias"
# (the midday hours in which the battery charges) and contracted power.
GRID_FEE_SCENARIOS = {
    "Exempt (assumed to continue after 2029)": (0.0, 0.0),
    "MT access tariff from 2030": (0.0182, 0.0458),
    "BTE access tariff from 2030": (0.0353, 0.0563),
}
# --- Assumptions -------------------------------------------------------------------------
INFLATION = 0.02                      # ECB inflation target, after the projections below
# Banco de Portugal, Boletim Económico June 2026, HICP projections
INFLATION_PROJECTION = {2026: 0.031, 2027: 0.024, 2028: 0.020}
PRICE_BASE_YEAR = 2025                # the price data (OMIE, costs) are 2025 values
START_YEAR = 2026                     # first year of operation
# Prices used only when no OMIE price file is available (assumptions, base year 2025)
FIXED_ELECTRICITY_PRICE = 0.20        # €/kWh paid when charging
FIXED_SPREAD = 0.10                   # €/kWh: selling price - buying price


def price_index_from_base(calendar_year, inflation=INFLATION):
    """Prices of calendar_year relative to PRICE_BASE_YEAR: the projected inflation of each
    year, then the long-run rate."""
    return float(np.prod([1 + INFLATION_PROJECTION.get(y, inflation)
                          for y in range(PRICE_BASE_YEAR + 1, int(calendar_year) + 1)]))


def usd_to_eur(usd):
    return usd / USD_PER_EUR


def nrel_cost_factor(year):
    """NREL's mid projection of the system cost in `year` relative to 2025 (before
    inflation); held at the ends of the table."""
    year = min(max(int(year), min(NREL_MID_USD_KWH)), max(NREL_MID_USD_KWH))
    return NREL_MID_USD_KWH[year] / NREL_MID_USD_KWH[PRICE_BASE_YEAR]


def system_capex_eur_kwh(chemistry, year=PRICE_BASE_YEAR):
    """Installed system cost [€/kWh, 2025 money] of a system bought in `year`: NREL's mid
    projection (LFP based), plus the Benchmark cell price difference between this chemistry
    and LFP (held at its 2025 value)."""
    cell = BENCHMARK_CELL_USD_KWH[PACK_PRICE_BASIS[chemistry]]
    return usd_to_eur(NREL_SYSTEM_USD_KWH * nrel_cost_factor(year) + cell
                      - BENCHMARK_CELL_USD_KWH["LFP"])


def irc_rate(year):
    if year in IRC_RATE:
        return IRC_RATE[year]
    return IRC_RATE_FROM_2028 if year >= 2028 else IRC_RATE_BEFORE_2026


def balance_of_system_eur_kwh(year=PRICE_BASE_YEAR):
    """Everything except the battery pack [€/kWh, 2025 money], bought in `year`: NREL system
    cost minus the BNEF stationary pack price, falling as NREL's whole system does.
    shortcut: NREL projects the whole system, not its parts; upgrade if a BOS projection appears."""
    return usd_to_eur(NREL_SYSTEM_USD_KWH - BNEF_STATIONARY_PACK_USD_KWH) * nrel_cost_factor(year)


def repurposed_pack_usd_kwh(capacity_left, buy_usd_kwh_left=B2U_BUY_USD_KWH_LEFT):
    """Repurposed battery [$ per nameplate kWh]: bought by the capacity it still holds, plus
    the B2U repurposing cost."""
    return buy_usd_kwh_left * capacity_left + B2U_REPURPOSING_USD_KWH


def second_life_capex_eur_kwh(capacity_left, buy_usd_kwh_left=B2U_BUY_USD_KWH_LEFT,
                              year=PRICE_BASE_YEAR):
    """Second-life system cost [€ per nameplate kWh, 2025 money]: repurposed EV battery
    (B2U, held at its value) plus a new balance of system bought in `year`."""
    return balance_of_system_eur_kwh(year) + usd_to_eur(
        repurposed_pack_usd_kwh(capacity_left, buy_usd_kwh_left))


def om_eur_kwh_year():
    return usd_to_eur(LAZARD_OM_USD_KWH_YR)


# --- Electricity prices ------------------------------------------------------------------
def price_files():
    return sorted(DATA_DIR.glob("omie_prices_pt_*.csv"))


def load_prices(path=None):
    """Hourly prices: columns date, hour, price_eur_mwh. None if no file is available."""
    files = [Path(path)] if path else price_files()
    if not files:
        return None
    df = pd.read_csv(files[-1])
    df.attrs["source"] = files[-1].name
    return df


def _mean_price(prices, hours, cheapest):
    """Mean price over the cheapest (or dearest) `hours` hours; the last hour may be partial.
    NaN if there are not enough hours."""
    if hours > len(prices):
        return np.nan
    p = np.sort(prices) if cheapest else np.sort(prices)[::-1]
    full = int(hours)
    total = p[:full].sum() + (hours - full) * (p[full] if full < len(p) else 0.0)
    return total / hours


def daily_arbitrage(prices, c_charge, c_discharge, dod=1.0, rte=NREL_SYSTEM_RTE):
    """Best single cycle of each day, with perfect foresight of that day's prices.

    The battery charges in the cheapest hours before some hour s and discharges in the
    dearest hours after it, trying every s. It needs dod/c_discharge hours to discharge and
    dod/(rte*c_charge) hours to charge (new battery at its rated C-rates).
    Returns one row per day, in €/kWh: mean buying price, mean selling price and the margin
    per kWh delivered (sell - buy / rte)."""
    h_dis = dod / c_discharge
    h_ch = dod / (rte * c_charge)
    rows = []
    for date, day in prices.groupby("date", sort=True):
        p = day.sort_values("hour")["price_eur_mwh"].to_numpy() / 1000.0     # €/kWh
        best = (np.nan, np.nan, -np.inf)
        for s in range(1, len(p)):
            buy = _mean_price(p[:s], h_ch, cheapest=True)
            sell = _mean_price(p[s:], h_dis, cheapest=False)
            if np.isfinite(buy) and np.isfinite(sell) and sell - buy / rte > best[2]:
                best = (buy, sell, sell - buy / rte)
        if np.isfinite(best[2]):
            rows.append({"date": date, "buy [€/kWh]": best[0], "sell [€/kWh]": best[1],
                         "margin [€/kWh]": best[2]})
    return pd.DataFrame(rows)


def arbitrage_prices(daily, cycles_per_year):
    """Mean buying price and spread for TEA inputs, using the cycles_per_year best days.

    The battery cycles at most once a day here; above 365 cycles per year the extra cycles
    are given the same mean prices (an optimistic simplification)."""
    best = daily.sort_values("margin [€/kWh]", ascending=False)
    used = best.head(int(min(cycles_per_year, len(best))))
    buy = float(used["buy [€/kWh]"].mean())
    sell = float(used["sell [€/kWh]"].mean())
    return {"electricity_price": buy, "spread": sell - buy, "days_used": len(used),
            "profitable_days": int((daily["margin [€/kWh]"] > 0).sum())}


# --- TEA ---------------------------------------------------------------------------------
def capacity_in_cycles(soh_curve, first_cycle, last_cycle):
    """Capacity fractions for cycles first_cycle..last_cycle (1 = first cycle).
    Cycles beyond the end of the curve count as NaN (no data, battery retired)."""
    soh_curve = np.asarray(soh_curve, dtype=float)
    cycles = np.arange(first_cycle, last_cycle + 1)
    values = np.full(len(cycles), np.nan)
    inside = cycles <= len(soh_curve)
    values[inside] = soh_curve[cycles[inside] - 1]
    return values


def calculate_tea(soh_curve,
                  capex_eur_kwh=system_capex_eur_kwh("LFP"),
                  capacity_kwh=60.0,
                  electricity_price=FIXED_ELECTRICITY_PRICE,   # €/kWh (base year)
                  spread=FIXED_SPREAD,
                  round_trip_eff=NREL_SYSTEM_RTE,
                  cycles_per_year=365,
                  dod=1.0,
                  years=NREL_LIFETIME_YEARS,
                  wacc=STEFFEN_WACC_PORTUGAL,
                  om_eur_kwh_yr=om_eur_kwh_year(),    # Lazard general O&M
                  om_escalation=LAZARD_OM_ESCALATION,
                  warranty_pct=LAZARD_WARRANTY_PCT,
                  warranty_start=LAZARD_WARRANTY_START_YEAR,
                  inflation=INFLATION,                # escalation of prices and grid fees
                  grid_fee_eur_kwh=0.0,               # access tariff on charging energy
                  grid_fee_eur_kw_day=0.0,            # access tariff on contracted power
                  charge_power_kw=None,               # None: capacity_kwh (1C)
                  income_tax=True,
                  depreciation_rate=TAX_DEPRECIATION_RATE,
                  start_year=START_YEAR,
                  retire_below=CFB_MIN_EOL_SOH):      # same end of life as the LCA
    """Life-cycle cost and cash-flow analysis. Returns the indicators and a table with one
    row per year (the cost breakdown)."""
    if charge_power_kw is None:
        charge_power_kw = capacity_kwh
    # capex_eur_kwh and om_eur_kwh_yr are 2025 prices: a system bought later pays that year's
    level = price_index_from_base(start_year - 1, inflation)
    capex = capex_eur_kwh * capacity_kwh * level
    annual_depreciation = capex * depreciation_rate   # straight line
    book_value = capex

    rows = []
    retired_year = None
    tax_loss = 0.0                                    # tax losses carried forward
    for year in range(1, years + 1):
        calendar_year = start_year + year - 1
        first = cycles_per_year * (year - 1) + 1
        last = cycles_per_year * year
        soh = capacity_in_cycles(soh_curve, first, last)
        working = soh[soh >= retire_below]            # NaN never passes this test

        # The battery is retired at its first cycle below the threshold.
        if retired_year is None and len(working) < len(soh):
            retired_year = year
        if retired_year is not None and retired_year < year:
            working = working[:0]                     # retired in an earlier year
        active = len(working) > 0

        price_index = price_index_from_base(calendar_year, inflation)
        e_out = capacity_kwh * dod * float(np.sum(working))   # kWh delivered
        e_in = e_out / round_trip_eff                          # kWh bought
        charging = e_in * electricity_price * price_index
        revenue = e_out * (electricity_price + spread) * price_index
        om = 0.0
        if active:
            om = om_eur_kwh_yr * level * capacity_kwh * (1 + om_escalation) ** (year - 1)
            if year >= warranty_start:
                om += warranty_pct * capex
        fees = 0.0
        if active and calendar_year > GRID_FEE_EXEMPT_UNTIL:
            fees = (e_in * grid_fee_eur_kwh + charge_power_kw * grid_fee_eur_kw_day * 365) \
                * price_index
        ebitda = revenue - charging - om - fees
        # Straight-line depreciation; a retired battery is written off (remaining book value)
        depreciation = book_value if (retired_year == year) else min(annual_depreciation, book_value)
        book_value -= depreciation
        taxable = ebitda - depreciation
        tax = 0.0
        if income_tax:
            if taxable < 0:
                tax_loss += -taxable
            else:
                used = min(tax_loss, TAX_LOSS_CAP * taxable)
                tax_loss -= used
                tax = irc_rate(calendar_year) * (taxable - used)
        rows.append({"Year": year, "Calendar year": calendar_year,
                     "Energy delivered [kWh]": e_out, "Energy bought [kWh]": e_in,
                     "Revenue [€]": revenue, "Charging cost [€]": charging,
                     "O&M and warranty [€]": om, "Grid fees [€]": fees,
                     "EBITDA [€]": ebitda, "Tax depreciation [€]": depreciation,
                     "Income tax [€]": tax, "Cash flow [€]": ebitda - tax})

    table = pd.DataFrame(rows)
    cash_flow = np.concatenate([[-capex], table["Cash flow [€]"].to_numpy()])
    discount = (1 + wacc) ** np.arange(years + 1)
    table["Discounted cash flow [€]"] = cash_flow[1:] / discount[1:]
    npv = float(np.sum(cash_flow / discount))

    irr = npf.irr(cash_flow)
    irr_pct = float(irr) * 100 if np.isfinite(irr) else np.nan

    cumulative = np.cumsum(cash_flow / discount)
    payback = int(np.argmax(cumulative >= 0)) if np.any(cumulative >= 0) else np.nan

    # Levelised cost of storage (before tax): discounted life-cycle costs per discounted
    # kWh delivered (the functional unit of the LCA)
    costs = table["Charging cost [€]"] + table["O&M and warranty [€]"] + table["Grid fees [€]"]
    disc_costs = capex + np.sum(costs.to_numpy() / discount[1:])
    disc_energy = np.sum(table["Energy delivered [kWh]"].to_numpy() / discount[1:])
    lcos = disc_costs / disc_energy if disc_energy > 0 else np.nan

    end_soh = capacity_in_cycles(soh_curve, cycles_per_year * years, cycles_per_year * years)[0]
    return {
        "CAPEX [€]": capex,
        "NPV [€]": npv,
        "IRR [%]": irr_pct,
        "Discounted payback [years]": payback,
        "LCOS [€/kWh]": lcos,
        "Retired in year": retired_year,      # None = still working at the end
        "SOH at end [%]": 100 * end_soh,      # NaN = below the data (< 50 %)
        "Cash flow [€]": cash_flow,
        "Table": table,
    }


# The defaults of calculate_tea, read from its signature so that they exist in one place only.
TEA_DEFAULTS = {name: p.default for name, p in inspect.signature(calculate_tea).parameters.items()
                if p.default is not inspect.Parameter.empty}


def with_defaults(tea_inputs):
    """The inputs of calculate_tea with every missing input set to its default."""
    return {**TEA_DEFAULTS, **tea_inputs}


def best_retirement(base_inputs, thresholds=None):
    """NPV for each retirement threshold, and the threshold with the highest NPV.

    Idea from Thelen et al. (2023), who chose when to retire each cell from its predicted
    curve (there by several attributes; here by NPV only). A retired battery earns nothing
    and costs nothing (see calculate_tea), and it has no resale value, so the best threshold
    is where one more year of operation at the lower capacity no longer pays for itself.
    The default thresholds stop at 50 %, where the ageing data end.
    Returns (table, best row)."""
    if thresholds is None:
        thresholds = np.round(np.arange(0.50, 0.951, 0.05), 2)
    rows = []
    for threshold in thresholds:
        tea = calculate_tea(**dict(base_inputs, retire_below=float(threshold)))
        rows.append({"Retire below [%]": 100 * float(threshold), "NPV [€]": tea["NPV [€]"],
                     "Retired in year": tea["Retired in year"],
                     "LCOS [€/kWh]": tea["LCOS [€/kWh]"]})
    table = pd.DataFrame(rows)
    return table, table.loc[table["NPV [€]"].idxmax()]


def tea_at_best_retirement(base_inputs, thresholds=None):
    """The TEA with the battery retired at the threshold of highest NPV (best_retirement).

    This threshold is the program's one end of life: the dashboard and both reports use it,
    for the TEA and for the LCA. Returns (inputs with that retire_below, TEA result,
    best_retirement table, best row)."""
    table, best = best_retirement(base_inputs, thresholds)
    inputs = dict(base_inputs, retire_below=float(best["Retire below [%]"]) / 100)
    return inputs, calculate_tea(**inputs), table, best


def sensitivity(base_inputs, change=0.20, base_npv=None):
    """Tornado data: NPV change when one input moves ±20 % (one at a time).
    base_npv: the NPV of base_inputs if it is already known."""
    if base_npv is None:
        base_npv = calculate_tea(**base_inputs)["NPV [€]"]
    full = with_defaults(base_inputs)     # a value of 0 is a value, not a missing input
    rows = []
    for name, key in [("CAPEX", "capex_eur_kwh"),
                      ("Electricity price level", "electricity_price"),
                      ("Arbitrage spread", "spread"),
                      ("Discount rate", "wacc"),
                      ("Round-trip efficiency", "round_trip_eff"),
                      ("O&M cost", "om_eur_kwh_yr")]:
        base = full[key]
        low = dict(base_inputs, **{key: base * (1 - change)})
        high = dict(base_inputs, **{key: min(base * (1 + change), 1.0)
                                    if key == "round_trip_eff" else base * (1 + change)})
        rows.append({
            "Parameter": name,
            "ΔNPV at -20% [€]": calculate_tea(**low)["NPV [€]"] - base_npv,
            "ΔNPV at +20% [€]": calculate_tea(**high)["NPV [€]"] - base_npv,
        })
    return pd.DataFrame(rows)


def second_life_vs_new(base_inputs, second_curve, capex_second_eur_kwh, new_curve, start_year,
                       years):
    """A repurposed EV battery against a new LFP storage system (the market standard, NREL's
    LFP-based cost and round-trip efficiency) on the same storage cycle over the same years.

    second_curve and new_curve: capacity fraction per storage cycle (the second one from
    ageing.second_life_curve). CAPEX of the second life = repurposed battery plus a new balance
    of system (second_life_capex_eur_kwh, for the year before start_year); the new system is
    bought at NREL's projected cost of that year. Each system is retired at its own threshold of highest
    NPV, the program's one end-of-life rule (tea_at_best_retirement).
    Returns (second-life TEA, new-system TEA), each with its "Retire below [%]"; the second also
    has "SOH at start [%]"."""
    common = dict(with_defaults(base_inputs), start_year=int(start_year), years=int(years))
    results = []
    for curve, capex, rte in ((second_curve, capex_second_eur_kwh, common["round_trip_eff"]),
                              (new_curve, system_capex_eur_kwh("LFP", int(start_year) - 1),
                               NREL_SYSTEM_RTE)):
        used, tea, _, _ = tea_at_best_retirement(dict(common, soh_curve=curve,
                                                      capex_eur_kwh=capex, round_trip_eff=rte))
        tea["Retire below [%]"] = 100 * used["retire_below"]
        results.append(tea)
    results[0]["SOH at start [%]"] = 100 * float(np.asarray(second_curve)[0])
    return results[0], results[1]


def om_text():
    """Plain-language description of the O&M and warranty inputs (dashboard and reports)."""
    return (f"Lazard LCOS 7.0: €{om_eur_kwh_year():.2f}/kWh per year, rising "
            f"{100 * LAZARD_OM_ESCALATION:g} % a year, plus a warranty of "
            f"{100 * LAZARD_WARRANTY_PCT:g} % of CAPEX a year from year "
            f"{LAZARD_WARRANTY_START_YEAR}")


def inflation_text():
    """The projected inflation, e.g. "3.1 % in 2026, 2.4 % in 2027, 2 % in 2028"."""
    return ", ".join(f"{100 * rate:g} % in {year}" for year, rate in INFLATION_PROJECTION.items())


def irc_text():
    """Plain-language description of the corporate income tax inputs."""
    rates = ", ".join(f"{100 * rate:g} % in {year}" for year, rate in IRC_RATE.items())
    return (f"Corporate income tax (IRC) {rates}, {100 * IRC_RATE_FROM_2028:g} % from 2028; "
            f"losses carried forward, deductible up to {100 * TAX_LOSS_CAP:g} % of a year's "
            "taxable income")


def capex_source():
    return (f"NREL Cole et al. 2025 (${NREL_SYSTEM_USD_KWH:g}/kWh) + Benchmark June 2025 cell "
            f"price difference to LFP, {USD_PER_EUR:g} $/€")


def rte_source():
    return (f"Simulated cell efficiency x {100 * PNNL_RTE_WITH_AUX:g}/{100 * PNNL_RTE_NO_AUX:g} "
            "(PNNL-27237, Table 2.2)")


def tea_documentation(inputs, chemistry, price_source=None):
    """All parameters of a TEA run with their source or status (ISO/TS 14076, clause 7)."""
    i = with_defaults(inputs)
    i.pop("soh_curve", None)
    prices = (f"OMIE day-ahead, Portugal ({price_source})" if price_source
              else "Assumption (no price file)")
    return {
        "method": "Environmental techno-economic assessment following the framework of "
                  "ISO/TS 14076:2025; life-cycle costing as in IEC 60300-3-3:2017 and "
                  "ISO 15686-5:2017 (nominal cash flows, NPV). Not reviewed.",
        "functional_unit": "1 kWh of energy delivered over the service life (same as the LCA)",
        "chemistry": chemistry,
        "parameters": {
            "capex_eur_kwh": [i["capex_eur_kwh"], capex_source()],
            "capacity_kwh": [i["capacity_kwh"], "Setting"],
            "electricity_price_eur_kwh": [i["electricity_price"], prices],
            "spread_eur_kwh": [i["spread"], prices],
            "round_trip_eff": [i["round_trip_eff"], rte_source()],
            "dod": [i["dod"], "Simulated cycle"],
            "cycles_per_year": [i["cycles_per_year"], "Setting"],
            "years": [i["years"], "NREL Cole et al. 2025"],
            "wacc_nominal": [i["wacc"], "Steffen 2020, Table 2"],
            "om_eur_kwh_yr": [i["om_eur_kwh_yr"],
                              f"Lazard LCOS 7.0, +{100 * i['om_escalation']:g} %/year"],
            "warranty_pct_capex": [i["warranty_pct"],
                                   f"Lazard LCOS 7.0, from year {i['warranty_start']}"],
            "grid_fee_eur_kwh_and_eur_kw_day_from_2030": [
                (i["grid_fee_eur_kwh"], i["grid_fee_eur_kw_day"]),
                f"ERSE Regulamento Tarifário art. 56 (exempt to {GRID_FEE_EXEMPT_UNTIL}); "
                "Diretiva 10/2025 (2026 tariffs)"],
            "income_tax_rate": [{**IRC_RATE, "2028+": IRC_RATE_FROM_2028},
                                "EY Tax Alert OE 2026 (Proposta de Lei 16/XVII)"],
            "tax_depreciation_rate": [i["depreciation_rate"],
                                      "PwC Worldwide Tax Summaries Portugal (electronic "
                                      "equipment, maximum straight-line rate); DR 25/2009"],
            "tax_loss_cap": [TAX_LOSS_CAP, "PwC Worldwide Tax Summaries Portugal"],
            "inflation": [{**INFLATION_PROJECTION, "later": i["inflation"]},
                          "Banco de Portugal, Boletim Económico June 2026 (HICP projections); "
                          "then the ECB target"],
            "write_off_at_retirement": [True, "CIRC art. 38 (now 31.º-B); AT ruling PIV 693"],
            "irc_surcharges": [0.0, "State: CIRC art. 87.º-A (profit above €1.5M only); "
                               "municipal: exempt at turnover up to €150,000 in Lisbon and "
                               "other municipalities (Ofício Circulado 20288/2026)"],
            "disposal_cost": [0.0, "Regulation (EU) 2023/1542, art. 61(1): producers take "
                              "back waste EV and industrial batteries free of charge"],
            "retire_below": [i["retire_below"], "Threshold with the highest NPV (dashboard); "
                             "also the end of service life of the LCA"],
        },
        "assumptions": ["Battery system classified as 'electronic equipment' for tax "
                        "depreciation (DR 25/2009 lists no battery storage; art. 5(3))",
                        "One year of prices repeated every year; perfect daily foresight",
                        f"First year of operation {i['start_year']}"],
    }
