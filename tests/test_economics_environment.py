import numpy as np

from battery_twin.chemistry import CHEMISTRIES
from battery_twin.economics import calculate_tea, second_life
from battery_twin.environment import calculate_lca

NEW_FOREVER = np.ones(20000)                    # a battery that never ages


def linear_fade(per_cycle):
    """Capacity curve losing per_cycle each cycle, cut at 50 % like the dashboard."""
    q = 1 - per_cycle * np.arange(1, 20001)
    return np.where(q >= 0.5, q, np.nan)


def test_npv_falls_when_capex_rises():
    assert (calculate_tea(NEW_FOREVER, capex_eur_kwh=200)["NPV [€]"]
            < calculate_tea(NEW_FOREVER, capex_eur_kwh=100)["NPV [€]"])


def test_battery_without_ageing_is_never_retired():
    assert calculate_tea(NEW_FOREVER)["Retired in year"] is None


def test_worn_out_battery_has_no_costs_after_retirement():
    # 0.1 %/cycle at 365 cycles/year: 50 % is reached in year 2 (cycle 501). Afterwards the
    # cash flow must be zero, not "operating costs of a dead battery".
    r = calculate_tea(linear_fade(0.001), years=15)
    assert r["Retired in year"] == 2
    r_short = calculate_tea(linear_fade(0.001), years=3)
    assert abs(r["NPV [€]"] - r_short["NPV [€]"]) < 1e-6


def test_slower_fade_gives_higher_npv():
    assert (calculate_tea(linear_fade(0.0001))["NPV [€]"]
            > calculate_tea(linear_fade(0.001))["NPV [€]"])


def test_second_life_starts_at_the_right_capacity():
    sl = second_life({"soh_curve": linear_fade(0.0001)}, 1000, 20.0, 8)
    assert abs(sl["SOH at start [%]"] - 90.0) < 1e-9


def test_lca_levelised_carbon_positive():
    for chem in CHEMISTRIES:
        _, ind = calculate_lca(chem, 60)
        assert ind["Levelised carbon [kg CO2eq/MWh delivered]"] > 0


def test_npv_is_always_a_number():
    # Even a curve that ends immediately (all NaN) must give a finite NPV.
    for curve in [linear_fade(0.001), linear_fade(0.01), np.full(20000, np.nan)]:
        assert np.isfinite(calculate_tea(curve)["NPV [€]"])
