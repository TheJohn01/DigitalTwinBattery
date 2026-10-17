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
rate. Disposal costs are not included (no source).

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
- Second life: Dong et al. (2023), iScience 26, 107195: repurposed EV batteries sell for
  $44-180/kWh (Neubauer et al.); $72/kWh (Liu) is used as the default.

Assumptions (not sourced, documented in tea_documentation): inflation 2 % a year (the ECB
target) for electricity prices and grid fees; the battery system classified as
"electronic equipment" for tax depreciation; the remaining book value written off when
the battery is retired; no municipal or state surcharges on IRC; no disposal cost; first
year of operation 2026.
"""
from pathlib import Path

import numpy as np
import numpy_financial as npf
import pandas as pd

DATA = Path(__file__).parent / "data"

# --- Sourced data ------------------------------------------------------------------------
USD_PER_EUR = 1.1300                  # ECB reference rate, 2025 annual average
NREL_SYSTEM_USD_KWH = 321.0           # Cole et al. 2025, 4-hour system, 2025 (mid)
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
SECOND_LIFE_PACK_USD_KWH = 72.0
SECOND_LIFE_PACK_RANGE_USD = (44.0, 180.0)
# PNNL-27237, Table 2.2, 1C: 83 % at the grid with auxiliary loads and rests, 91 % without
# auxiliary loads (the battery). The simulated cell efficiency is multiplied by this ratio.
PNNL_RTE_WITH_AUX, PNNL_RTE_NO_AUX = 0.83, 0.91
POWER_CONVERSION_RTE = PNNL_RTE_WITH_AUX / PNNL_RTE_NO_AUX
IRC_RATE = {2026: 0.19, 2027: 0.18}   # 17 % from 2028 (IRC_RATE_FROM_2028)
IRC_RATE_FROM_2028 = 0.17
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
INFLATION = 0.02                      # ECB inflation target
START_YEAR = 2026                     # first year of operation


def usd_to_eur(usd):
    return usd / USD_PER_EUR


def system_capex_eur_kwh(chemistry):
    """Installed system cost [€/kWh]: NREL's system cost (LFP based), plus the Benchmark
    cell price difference between this chemistry and LFP."""
    cell = BENCHMARK_CELL_USD_KWH[PACK_PRICE_BASIS[chemistry]]
    return usd_to_eur(NREL_SYSTEM_USD_KWH + cell - BENCHMARK_CELL_USD_KWH["LFP"])


def irc_rate(year):
    return IRC_RATE.get(year, IRC_RATE_FROM_2028 if year >= 2028 else 0.20)


def balance_of_system_eur_kwh():
    """Everything except the battery pack [€/kWh]: NREL system cost minus the BNEF
    stationary pack price."""
    return usd_to_eur(NREL_SYSTEM_USD_KWH - BNEF_STATIONARY_PACK_USD_KWH)


def second_life_capex_eur_kwh(pack_usd_kwh=SECOND_LIFE_PACK_USD_KWH):
    """Second-life system cost [€/kWh]: repurposed EV battery plus a new balance of system."""
    return balance_of_system_eur_kwh() + usd_to_eur(pack_usd_kwh)


def om_eur_kwh_year():
    return usd_to_eur(LAZARD_OM_USD_KWH_YR)


# --- Electricity prices ------------------------------------------------------------------
def price_files():
    return sorted(DATA.glob("omie_prices_pt_*.csv"))


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
            "profitable_days": int((daily["margin [€/kWh]"] > 0).sum()),
            "mean_margin": float(used["margin [€/kWh]"].mean())}


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
                  capex_eur_kwh=None,                 # None: sourced LFP system cost
                  capacity_kwh=60.0,
                  electricity_price=0.20,             # €/kWh paid when charging (base year)
                  spread=0.10,                        # €/kWh: selling price - buying price
                  round_trip_eff=NREL_SYSTEM_RTE,
                  cycles_per_year=365,
                  dod=1.0,
                  years=NREL_LIFETIME_YEARS,
                  wacc=STEFFEN_WACC_PORTUGAL,
                  om_eur_kwh_yr=None,                 # None: Lazard general O&M
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
                  retire_below=0.70,                  # same end of life as the LCA
                  start_cycles=0):                    # >0 for a second-life battery
    """Life-cycle cost and cash-flow analysis. Returns the indicators and a table with one
    row per year (the cost breakdown)."""
    if capex_eur_kwh is None:
        capex_eur_kwh = system_capex_eur_kwh("LFP")
    if om_eur_kwh_yr is None:
        om_eur_kwh_yr = om_eur_kwh_year()
    if charge_power_kw is None:
        charge_power_kw = capacity_kwh
    capex = capex_eur_kwh * capacity_kwh
    annual_depreciation = capex * depreciation_rate   # straight line
    book_value = capex

    rows = []
    retired_year = None
    tax_loss = 0.0                                    # tax losses carried forward
    for year in range(1, years + 1):
        calendar_year = start_year + year - 1
        first = start_cycles + cycles_per_year * (year - 1) + 1
        last = start_cycles + cycles_per_year * year
        soh = capacity_in_cycles(soh_curve, first, last)
        working = soh[soh >= retire_below]            # NaN never passes this test

        # The battery is retired at its first cycle below the threshold.
        if retired_year is None and len(working) < len(soh):
            retired_year = year
        if retired_year is not None and retired_year < year:
            working = working[:0]                     # retired in an earlier year
        active = len(working) > 0

        price_index = (1 + inflation) ** year         # base-year prices are 2025
        e_out = capacity_kwh * dod * float(np.sum(working))   # kWh delivered
        e_in = e_out / round_trip_eff                          # kWh bought
        charging = e_in * electricity_price * price_index
        revenue = e_out * (electricity_price + spread) * price_index
        om = 0.0
        if active:
            om = om_eur_kwh_yr * capacity_kwh * (1 + om_escalation) ** (year - 1)
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

    table = pd.DataFrame(rows).fillna(0.0)
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

    end_soh = capacity_in_cycles(soh_curve, start_cycles + cycles_per_year * years,
                                 start_cycles + cycles_per_year * years)[0]
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


def sensitivity(base_inputs, change=0.20):
    """Tornado data: NPV change when one input moves ±20 % (one at a time)."""
    base_npv = calculate_tea(**base_inputs)["NPV [€]"]
    defaults = {"capex_eur_kwh": system_capex_eur_kwh("LFP"), "electricity_price": 0.20,
                "spread": 0.10, "wacc": STEFFEN_WACC_PORTUGAL,
                "round_trip_eff": NREL_SYSTEM_RTE, "om_eur_kwh_yr": om_eur_kwh_year()}
    rows = []
    for name, key in [("CAPEX", "capex_eur_kwh"),
                      ("Electricity price level", "electricity_price"),
                      ("Arbitrage spread", "spread"),
                      ("Discount rate", "wacc"),
                      ("Round-trip efficiency", "round_trip_eff"),
                      ("O&M cost", "om_eur_kwh_yr")]:
        base = base_inputs.get(key) or defaults[key]
        low = dict(base_inputs, **{key: base * (1 - change)})
        high = dict(base_inputs, **{key: min(base * (1 + change), 1.0)
                                    if key == "round_trip_eff" else base * (1 + change)})
        rows.append({
            "Parameter": name,
            "ΔNPV at -20% [€]": calculate_tea(**low)["NPV [€]"] - base_npv,
            "ΔNPV at +20% [€]": calculate_tea(**high)["NPV [€]"] - base_npv,
        })
    return pd.DataFrame(rows)


def second_life(base_inputs, first_life_cycles, capex_second_eur_kwh, years):
    """EV battery reused for stationary storage after first_life_cycles.
    Same TEA model; CAPEX is replaced by the second-life system cost (repurposed battery
    plus a new balance of system, see second_life_capex_eur_kwh)."""
    inputs = dict(base_inputs,
                  capex_eur_kwh=capex_second_eur_kwh,
                  start_cycles=int(first_life_cycles),
                  years=int(years))
    result = calculate_tea(**inputs)
    start = capacity_in_cycles(base_inputs["soh_curve"], first_life_cycles, first_life_cycles)[0]
    result["SOH at start [%]"] = 100 * start
    return result


def tea_documentation(inputs, chemistry, price_source=None):
    """All parameters of a TEA run with their source or status (ISO/TS 14076, clause 7)."""
    i = dict(inputs)
    i.pop("soh_curve", None)
    fee = (i.get("grid_fee_eur_kwh", 0.0), i.get("grid_fee_eur_kw_day", 0.0))
    return {
        "method": "Environmental techno-economic assessment following the framework of "
                  "ISO/TS 14076:2025; life-cycle costing as in IEC 60300-3-3:2017 and "
                  "ISO 15686-5:2017 (nominal cash flows, NPV). Not reviewed.",
        "functional_unit": "1 kWh of energy delivered over the service life (same as the LCA)",
        "chemistry": chemistry,
        "parameters": {
            "capex_eur_kwh": [i.get("capex_eur_kwh"), "NREL Cole et al. 2025 ($321/kWh) + "
                              "Benchmark June 2025 cell price difference to LFP, 1.13 $/€"],
            "capacity_kwh": [i.get("capacity_kwh"), "Setting"],
            "electricity_price_eur_kwh": [i.get("electricity_price"),
                                          f"OMIE day-ahead, Portugal ({price_source})"
                                          if price_source else "Assumption (no price file)"],
            "spread_eur_kwh": [i.get("spread"), f"OMIE day-ahead, Portugal ({price_source})"
                               if price_source else "Assumption (no price file)"],
            "round_trip_eff": [i.get("round_trip_eff"),
                               "Simulated cell efficiency x 83/91 (PNNL-27237, Table 2.2)"],
            "dod": [i.get("dod"), "Simulated cycle"],
            "cycles_per_year": [i.get("cycles_per_year"), "Setting"],
            "years": [i.get("years", NREL_LIFETIME_YEARS), "NREL Cole et al. 2025"],
            "wacc_nominal": [i.get("wacc", STEFFEN_WACC_PORTUGAL), "Steffen 2020, Table 2"],
            "om_eur_kwh_yr": [om_eur_kwh_year(), "Lazard LCOS 7.0, +2.5 %/year"],
            "warranty_pct_capex": [LAZARD_WARRANTY_PCT, "Lazard LCOS 7.0, from year 3"],
            "grid_fee_eur_kwh_and_eur_kw_day_from_2030": [fee, "ERSE Regulamento Tarifário "
                                                          "art. 56 (exempt to 2029); "
                                                          "Diretiva 10/2025 (2026 tariffs)"],
            "income_tax_rate": [{**IRC_RATE, "2028+": IRC_RATE_FROM_2028},
                                "EY Tax Alert OE 2026 (Proposta de Lei 16/XVII)"],
            "tax_depreciation_rate": [i.get("depreciation_rate", TAX_DEPRECIATION_RATE),
                                      "PwC Worldwide Tax Summaries Portugal (electronic "
                                      "equipment, maximum straight-line rate); DR 25/2009"],
            "tax_loss_cap": [TAX_LOSS_CAP, "PwC Worldwide Tax Summaries Portugal"],
            "retire_below": [i.get("retire_below", 0.70), "Setting (default = LCA end of life)"],
        },
        "assumptions": ["Inflation 2 %/year (ECB target) on electricity prices and grid fees",
                        "Battery system classified as 'electronic equipment' for tax "
                        "depreciation; book value written off at retirement",
                        "No derramas (municipal and state surcharges)",
                        "No disposal cost (no source)",
                        "One year of prices repeated every year; perfect daily foresight",
                        "First year of operation 2026"],
    }
