"""Home and business batteries: the site model (site.py) and its link to the TEA."""
import numpy as np
import pandas as pd
import pytest

from battery_twin.economics import calculate_tea
from battery_twin.site import (TARIFFS, bill, period_shares, read_load_csv, simulate_site,
                               site_tea_inputs, year_frame)


@pytest.fixture(scope="module")
def home():
    return year_frame("btn_b", 10612, 5.0, "Lisboa")


def test_year_frame_lines_up_load_pv_and_prices(home):
    assert len(home) == 8760 and abs(home["load"].sum() - 10612) < 1e-6
    assert 7000 < home["pv"].sum() < 9000                     # 5 kWp in Lisbon, about 1,600 kWh/kWp
    assert home.loc[home.hour.isin([0, 1, 2, 3]), "pv"].sum() == 0    # no sun at night
    assert 200 < home["summer"].sum() / 24 < 220               # legal summer time, end of March to October


def test_time_periods_follow_the_erse_daily_cycle():
    hours = np.arange(24)
    winter = period_shares(hours, [False] * 24, "tetra")
    summer = period_shares(hours, [True] * 24, "tri")
    assert winter["ponta"][18] == 1 and winter["ponta"][9] == 1 and winter["ponta"][10] == 0.5
    assert winter["super_vazio"][3] == 1 and winter["vazio_normal"][23] == 1
    assert summer["ponta"][11] == 1 and summer["ponta"][10] == 0.5 and summer["vazio"][7] == 1
    for shares in (winter, summer, period_shares(hours, [False] * 24, "bi")):
        assert np.allclose(sum(shares.values()), 1.0)


@pytest.mark.parametrize("mode, tariff", [("self", "BTN simple"), ("tou", "BTE")])
def test_energy_balance_and_window(home, mode, tariff):
    shares = period_shares(home.hour, home.summer, TARIFFS[tariff]["periods"])
    f = simulate_site(home, 10.0, 5.0, dod=0.8, rte=0.9, mode=mode, shares=shares)
    used_pv = home["pv"] - f["export"] - f["charge_pv"]
    # every hour: load = PV used directly + battery + grid (less what the grid charges)
    assert np.allclose(home["load"], used_pv + f["discharge"] + f["import"] - f["charge_grid"])
    assert (f >= -1e-9).all().all()
    stored = np.cumsum((f["charge_pv"] + f["charge_grid"]) * np.sqrt(0.9)
                       - f["discharge"] / np.sqrt(0.9)) + 10 * 0.1
    assert stored.min() >= 10 * 0.1 - 1e-6 and stored.max() <= 10 * 0.9 + 1e-6


def test_no_pv_no_export_and_self_consumption_does_nothing(home):
    dark = home.assign(pv=0.0)
    f = simulate_site(dark, 10.0, 5.0, mode="self")
    assert f["export"].sum() == 0 and f["discharge"].sum() == 0


def test_time_of_use_lowers_the_peak_hour_power_charge():
    shop = year_frame("btn_a", 60000, 0.0)
    shares = period_shares(shop.hour, shop.summer, "tetra")
    f = simulate_site(shop, 60.0, 30.0, mode="tou", shares=shares)
    none = {"import": shop["load"], "export": np.zeros(len(shop))}
    assert bill(shop, f, "BTE")[1] < 0.5 * bill(shop, none, "BTE")[1]
    inputs, saving = site_tea_inputs(shop, f, "BTE", 60.0, 0.9)
    assert inputs["fixed_savings_eur_yr"] > 0 and saving > inputs["fixed_savings_eur_yr"]


def test_tea_gets_the_same_saving_as_the_bill(home):
    f = simulate_site(home, 10.0, 5.0, mode="self")
    inputs, saving = site_tea_inputs(home, f, "BTN simple", 10.0, 0.9)
    tea = calculate_tea(np.ones(20000), capex_eur_kwh=0.0, capacity_kwh=10.0, years=1,
                        income_tax=False, start_year=2026, om_eur_kwh_yr=0.0, warranty_pct=0.0,
                        **inputs)
    year1 = tea["Table"].iloc[0]
    # the first year's net income is the bill saving (in 2026 prices), within the energy left
    # in the battery at the end of the year
    assert abs(year1["EBITDA [€]"] / 1.031 - saving) / saving < 0.02


def test_fixed_savings_count_only_while_the_battery_works():
    curve = np.r_[np.ones(365 * 3), np.full(365 * 12, 0.6)]          # below 70 % from year 4
    base = dict(capex_eur_kwh=0.0, capacity_kwh=10.0, years=6, spread=0.0, income_tax=False)
    a = calculate_tea(curve, **base)["Table"]["Revenue [€]"]
    b = calculate_tea(curve, fixed_savings_eur_yr=100.0, **base)["Table"]["Revenue [€]"]
    extra = (b - a).to_numpy()
    assert (extra[:3] > 99).all() and (extra[3:] == 0).all()     # year 4 starts below 70 %


def test_read_load_csv_checks_its_input():
    t = pd.date_range("2025-01-01", periods=365 * 96, freq="15min")
    df = pd.DataFrame({"t": t, "kwh": 0.1})
    out = read_load_csv(df)
    assert len(out) == 8760 and abs(out.sum() - 0.1 * 96 * 365) / (0.1 * 96 * 365) < 0.01
    with pytest.raises(ValueError):
        read_load_csv(df.head(1000))                               # less than a year
    with pytest.raises(ValueError):
        read_load_csv(df.assign(kwh=-1.0))
