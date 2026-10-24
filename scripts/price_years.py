"""The storage economics at the dashboard's defaults for every year of OMIE prices in
src/battery_twin/data (omie_prices_pt_<year>.csv): the daily arbitrage (mean buying and
selling price of the best cycle of each day) and, for each chemistry, the NPV and LCOS with
the battery retired at its threshold of highest NPV. The dashboard itself uses the newest
year (economics.load_prices); this shows how much the result depends on that choice.

Defaults as in README Section 9: 20 °C, forced air (25 W/m²K), 0.3C charge, 1C discharge,
storage cycle at 80 % depth, 365 cycles a year, 60 kWh, grid fees exempt, after tax.

Run:  python scripts/price_years.py          (about two minutes: four physics runs)
"""
import numpy as np
import pandas as pd

from battery_twin.ageing import cut_at_data_end, predict_capacity, storage_cycle
from battery_twin.chemistry import choose_model, run_battery_test
from battery_twin.economics import (GRID_FEE_SCENARIOS, NREL_LIFETIME_YEARS,
                                    POWER_CONVERSION_RTE, STEFFEN_WACC_PORTUGAL,
                                    arbitrage_prices, daily_arbitrage, load_prices, price_files,
                                    system_capex_eur_kwh, tea_at_best_retirement)

DOD, PACK, C_CH, C_DIS, AMBIENT = 0.8, 60.0, 0.3, 1.0, 20.0


def storage_inputs(chem):
    """(capacity curve of the storage cycle, whole-system round-trip efficiency)."""
    r = run_battery_test(chem, choose_model(chem, C_CH), C_CH, C_DIS, 2920, AMBIENT, 25.0,
                         cycles_per_year=365, cycling_c=AMBIENT)
    t, soc, temp = storage_cycle(*r["ageing_cycle"], DOD, AMBIENT)
    q = cut_at_data_end(predict_capacity(chem, t, soc, temp, 30000))
    rte_cell = float(r["efficiency"]["Energy efficiency [%]"].mean() / 100)
    return q, round(float(np.clip(rte_cell * POWER_CONVERSION_RTE, 0.5, 0.98)), 2)


def year_row(path, chem, q, rte):
    prices = load_prices(path)
    daily = daily_arbitrage(prices, C_CH, C_DIS, DOD, rte)
    arb = arbitrage_prices(daily, 365)
    fee = GRID_FEE_SCENARIOS[list(GRID_FEE_SCENARIOS)[0]]
    _, tea, _, best = tea_at_best_retirement({
        "soh_curve": q, "capex_eur_kwh": system_capex_eur_kwh(chem), "capacity_kwh": PACK,
        "electricity_price": arb["electricity_price"], "spread": arb["spread"],
        "round_trip_eff": rte, "cycles_per_year": 365, "dod": DOD,
        "years": NREL_LIFETIME_YEARS, "wacc": STEFFEN_WACC_PORTUGAL,
        "grid_fee_eur_kwh": fee[0], "grid_fee_eur_kw_day": fee[1],
        "charge_power_kw": PACK * C_CH, "depreciation_rate": 0.2})
    return {"year": path.stem[-4:], "chemistry": chem,
            "buy [€/MWh]": 1000 * arb["electricity_price"],
            "sell [€/MWh]": 1000 * (arb["electricity_price"] + arb["spread"]),
            "profitable days [%]": 100 * float((daily["margin [€/kWh]"] > 0).mean()),
            "retire below [%]": float(best["Retire below [%]"]),
            "NPV [€]": tea["NPV [€]"], "LCOS [€/kWh]": tea["LCOS [€/kWh]"]}


if __name__ == "__main__":
    rows = []
    for chem in ("NMC", "LFP", "NCA", "Na-ion"):
        q, rte = storage_inputs(chem)
        rows += [year_row(p, chem, q, rte) for p in price_files()]
    pd.set_option("display.width", 160)
    print(pd.DataFrame(rows).round({"buy [€/MWh]": 0, "sell [€/MWh]": 0, "profitable days [%]": 0,
                                    "NPV [€]": 0, "LCOS [€/kWh]": 3}).to_string(index=False))
