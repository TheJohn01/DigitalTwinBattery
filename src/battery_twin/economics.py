"""Techno-economic analysis (TEA) of a battery doing energy arbitrage.

One function, calculate_tea, is used for the main result, the sensitivity
(tornado) chart and the second-life value, so all three always agree.
"""
import numpy as np
import numpy_financial as npf
import pandas as pd


def soh_after(cycles, sqrt_fade_pct):
    """SOH fraction after a number of cycles, using loss[%] = a * sqrt(cycles)."""
    return max(1.0 - sqrt_fade_pct / 100.0 * np.sqrt(max(cycles, 0.0)), 0.0)


def calculate_tea(capex_eur_kwh=125.0,
                  capacity_kwh=60.0,
                  electricity_price=0.20,     # €/kWh paid when charging
                  spread=0.10,                # €/kWh: selling price - buying price
                  round_trip_eff=0.90,
                  sqrt_fade_pct=0.0,          # from chemistry.fit_sqrt_fade
                  cycles_per_year=365,
                  dod=0.80,
                  years=15,
                  wacc=0.07,
                  opex_pct_of_capex=0.015,
                  start_cycles=0):            # >0 for a second-life battery
    capex = capex_eur_kwh * capacity_kwh
    opex = capex * opex_pct_of_capex

    cash_flow = [-capex]
    energy_out = []
    charging_cost = []
    for year in range(1, years + 1):
        cycles_mid_year = start_cycles + cycles_per_year * (year - 0.5)
        soh = soh_after(cycles_mid_year, sqrt_fade_pct)
        e_out = capacity_kwh * soh * dod * cycles_per_year     # kWh delivered
        e_in = e_out / round_trip_eff                           # kWh bought
        cost = e_in * electricity_price
        revenue = e_out * (electricity_price + spread)
        cash_flow.append(revenue - cost - opex)
        energy_out.append(e_out)
        charging_cost.append(cost)

    cash_flow = np.array(cash_flow)
    discount = (1 + wacc) ** np.arange(years + 1)
    discounted = cash_flow / discount
    npv = float(np.sum(discounted))

    irr = npf.irr(cash_flow)
    irr_pct = float(irr) * 100 if np.isfinite(irr) else np.nan

    cumulative = np.cumsum(discounted)
    payback = int(np.argmax(cumulative >= 0)) if np.any(cumulative >= 0) else np.nan

    # Levelised cost of storage: discounted costs / discounted energy delivered
    disc_costs = capex + np.sum((opex + np.array(charging_cost)) / discount[1:])
    disc_energy = np.sum(np.array(energy_out) / discount[1:])
    lcos = disc_costs / disc_energy if disc_energy > 0 else np.nan

    return {
        "CAPEX [€]": capex,
        "NPV [€]": npv,
        "IRR [%]": irr_pct,
        "Discounted payback [years]": payback,
        "LCOS [€/kWh]": lcos,
        "SOH at end [%]": 100 * soh_after(start_cycles + cycles_per_year * years, sqrt_fade_pct),
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
                  start_cycles=first_life_cycles,
                  years=int(years))
    result = calculate_tea(**inputs)
    result["SOH at start [%]"] = 100 * soh_after(first_life_cycles, base_inputs["sqrt_fade_pct"])
    return result
