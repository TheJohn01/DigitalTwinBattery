"""Techno-economic analysis (TEA) of a battery doing energy arbitrage.

The battery's capacity in each cycle comes straight from the ageing curve
(capacity fraction for cycle 1, 2, 3, ...). When the capacity drops below the
retirement threshold, or the curve ends because the measured data end, the
battery is retired: from then on it earns nothing and costs nothing.

One function, calculate_tea, is used for the main result, the sensitivity
(tornado) chart, the second-life value and the chemistry comparison, so they
always agree.
"""
import numpy as np
import numpy_financial as npf
import pandas as pd


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
                  capex_eur_kwh=125.0,
                  capacity_kwh=60.0,
                  electricity_price=0.20,     # €/kWh paid when charging
                  spread=0.10,                # €/kWh: selling price - buying price
                  round_trip_eff=0.90,
                  cycles_per_year=365,
                  dod=0.80,
                  years=15,
                  wacc=0.07,
                  opex_pct_of_capex=0.015,
                  retire_below=0.50,          # retire when capacity < 50 % (end of the data)
                  start_cycles=0):            # >0 for a second-life battery
    capex = capex_eur_kwh * capacity_kwh
    opex = capex * opex_pct_of_capex

    cash_flow = [-capex]
    energy_out = []
    charging_cost = []
    retired_year = None
    for year in range(1, years + 1):
        first = start_cycles + cycles_per_year * (year - 1) + 1
        last = start_cycles + cycles_per_year * year
        soh = capacity_in_cycles(soh_curve, first, last)
        working = soh[soh >= retire_below]            # NaN never passes this test

        # The battery is retired at its first cycle below the threshold.
        if retired_year is None and len(working) < len(soh):
            retired_year = year
        if retired_year is not None and retired_year < year:
            working = working[:0]                     # retired in an earlier year

        e_out = capacity_kwh * dod * float(np.sum(working))   # kWh delivered
        e_in = e_out / round_trip_eff                          # kWh bought
        cost = e_in * electricity_price
        revenue = e_out * (electricity_price + spread)
        year_opex = opex if len(working) > 0 else 0.0
        cash_flow.append(revenue - cost - year_opex)
        energy_out.append(e_out)
        charging_cost.append(cost + year_opex)

    # Guarantee finite numbers: NPV must always be a number, never blank.
    cash_flow = np.nan_to_num(np.array(cash_flow, dtype=float))
    energy_out = np.nan_to_num(np.array(energy_out, dtype=float))
    charging_cost = np.nan_to_num(np.array(charging_cost, dtype=float))
    discount = (1 + wacc) ** np.arange(years + 1)
    discounted = cash_flow / discount
    npv = float(np.sum(discounted))

    irr = npf.irr(cash_flow)
    irr_pct = float(irr) * 100 if np.isfinite(irr) else np.nan

    cumulative = np.cumsum(discounted)
    payback = int(np.argmax(cumulative >= 0)) if np.any(cumulative >= 0) else np.nan

    # Levelised cost of storage: discounted costs / discounted energy delivered
    disc_costs = capex + np.sum(np.array(charging_cost) / discount[1:])
    disc_energy = np.sum(np.array(energy_out) / discount[1:])
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
    }


def sensitivity(base_inputs, change=0.20):
    """Tornado data: NPV change when CAPEX, electricity price or spread move ±20%."""
    base_npv = calculate_tea(**base_inputs)["NPV [€]"]
    rows = []
    for name, key in [("CAPEX", "capex_eur_kwh"),
                      ("Electricity price", "electricity_price"),
                      ("Arbitrage spread", "spread")]:
        low = dict(base_inputs, **{key: base_inputs[key] * (1 - change)})
        high = dict(base_inputs, **{key: base_inputs[key] * (1 + change)})
        rows.append({
            "Parameter": name,
            "ΔNPV at -20% [€]": calculate_tea(**low)["NPV [€]"] - base_npv,
            "ΔNPV at +20% [€]": calculate_tea(**high)["NPV [€]"] - base_npv,
        })
    return pd.DataFrame(rows)


def second_life(base_inputs, first_life_cycles, repurpose_eur_kwh, years):
    """EV battery reused for stationary storage after first_life_cycles.
    Same TEA model; CAPEX is replaced by the repurposing cost."""
    inputs = dict(base_inputs,
                  capex_eur_kwh=repurpose_eur_kwh,
                  start_cycles=int(first_life_cycles),
                  years=int(years))
    result = calculate_tea(**inputs)
    start = capacity_in_cycles(base_inputs["soh_curve"], first_life_cycles, first_life_cycles)[0]
    result["SOH at start [%]"] = 100 * start
    return result
