"""Empirical ageing models: exactness, physical trends and validity warnings."""
import json
from functools import cache

import numpy as np
import pytest

from battery_twin.ageing import (AGEING_MODELS, LfpAdjusted, NcaRefit, NmcRefit, add_rest,
                                 cycles_to, predict_capacity, validity_warnings)
from battery_twin.chemistry import CHEMISTRIES, run_battery_test, standard_profile
from battery_twin.constants import DATA_DIR


@cache
def default_run(chemistry, model_type="SPMe"):
    """run_battery_test with its default settings, run once per chemistry for all tests."""
    return run_battery_test(chemistry, model_type)


@pytest.mark.parametrize("chemistry", ["NMC", "LFP", "NCA"])
def test_calendar_term_matches_blast_stepping(chemistry):
    # All three keep BLAST-Lite's calendar term: storage (no cycling) must still match.
    t, soc = np.array([0.0, 86400.0]), np.array([0.8, 0.8])
    temp = np.full(2, 25.0)
    q = predict_capacity(chemistry, t, soc, temp, 300)
    model = AGEING_MODELS[chemistry]()
    for _ in range(300):
        model.update_battery_state(t, soc, temp)
    assert abs(q[-1] - model.outputs["q"][-1]) < 0.002


def cycles_to_80(chemistry, soc_low, soc_high, c_discharge, temp_c, c_charge=0.5):
    """Equivalent full cycles to 80 %, cycling back to back."""
    dod = soc_high - soc_low
    t_dis = 3600 * dod / c_discharge
    t = np.array([0, t_dis, t_dis + 3600 * dod / c_charge])
    soc = np.array([soc_high, soc_low, soc_high])
    q = predict_capacity(chemistry, t, soc, np.full(3, temp_c), 30000)
    return cycles_to(q, 0.8) * dod


def test_nca_matches_preger():
    # Preger et al. 2020, same cell, 0-100 %, 25 °C, 1C discharge: about 430 cycles to 80 %
    assert 350 < cycles_to_80("NCA", 0, 1, 1.0, 25) < 520


def test_nmc_matches_wittman_and_ohneseit():
    # Wittman 2023 (LG HG2, 25 °C, 1C): about 460; Ohneseit 2025 (20 °C, 1C): about 500
    assert 370 < cycles_to_80("NMC", 0, 1, 1.0, 25) < 560
    assert 330 < cycles_to_80("NMC", 0, 1, 1.0, 20) < 760


def test_nmc_fast_and_cold_charging_match_luh_blank():
    # Luh & Blank 2024 (LG HG2, 0-100 %, 1C discharge): 1C charge at 25 °C about 280;
    # 5/3C charge at 0 °C about 40 cycles to 80 %
    assert 200 < cycles_to_80("NMC", 0, 1, 1.0, 25, c_charge=1.0) < 400
    assert 25 < cycles_to_80("NMC", 0, 1, 1.0, 0, c_charge=1.67) < 70


def test_nmc_faster_or_colder_charging_ages_faster():
    slow = cycles_to_80("NMC", 0, 1, 1.0, 25, c_charge=0.33)
    assert cycles_to_80("NMC", 0, 1, 1.0, 25, c_charge=1.67) < slow
    assert cycles_to_80("NMC", 0, 1, 1.0, 0, c_charge=0.33) < slow


def test_nmc_discharge_rate_has_no_effect():
    # Preger 0.5-3C, Luh & Blank 1/3-1C, Ohneseit 1-2C: no clear effect
    one = cycles_to_80("NMC", 0, 1, 1.0, 25)
    assert abs(cycles_to_80("NMC", 0, 1, 3.0, 25) / one - 1) < 0.1


def test_lfp_fast_charging():
    # Severson 2019: life falls steeply above about 3C charging; slow charging unaffected
    slow = cycles_to_80("LFP", 0, 1, 1.0, 30, c_charge=0.5)
    assert abs(cycles_to_80("LFP", 0, 1, 1.0, 30, c_charge=1.0) / slow - 1) < 0.05
    assert cycles_to_80("LFP", 0, 1, 1.0, 30, c_charge=4.0) < 0.6 * slow


def test_lfp_matches_ohneseit():
    # Ohneseit 2025, 21700 LFP, 20 °C, 1C, 0-100 %: about 1,450-1,900 cycles to 80 %
    assert 1300 < cycles_to_80("LFP", 0, 1, 1.0, 20) < 2000


def test_lfp_outlasts_nmc_about_three_times():
    # Same study (Ohneseit 2025): LFP about 1,600 vs NMC about 500 cycles to 80 %
    ratio = cycles_to_80("LFP", 0, 1, 1.0, 20) / cycles_to_80("NMC", 0, 1, 1.0, 20)
    assert 2.0 < ratio < 5.0


@pytest.mark.parametrize("chemistry", ["NMC", "NCA"])
def test_shallow_cycling_lasts_longer(chemistry):
    full = cycles_to_80(chemistry, 0, 1, 0.5, 25)
    assert cycles_to_80(chemistry, 0.2, 0.8, 0.5, 25) > full
    assert cycles_to_80(chemistry, 0.4, 0.6, 0.5, 25) > 2 * full


@pytest.mark.parametrize("chemistry", list(CHEMISTRIES))
def test_capacity_falls_with_cycles(chemistry):
    t, soc = standard_profile(0.5, 1.0)
    q = predict_capacity(chemistry, t, soc, np.full(len(t), 25.0), 2000)
    assert q[0] <= 1 and np.all(np.diff(q) <= 1e-12) and q[-1] < q[0]


@pytest.mark.parametrize("chemistry", ["LFP", "NCA"])
def test_hotter_ages_faster(chemistry):
    t, soc = standard_profile(0.5, 1.0)
    cool = predict_capacity(chemistry, t, soc, np.full(len(t), 15.0), 1000)[-1]
    hot = predict_capacity(chemistry, t, soc, np.full(len(t), 40.0), 1000)[-1]
    assert hot < cool


@pytest.mark.parametrize("chemistry", ["NMC", "LFP", "NCA"])
def test_storage_ages_faster_when_hotter(chemistry):
    # NMC cycling ages faster when COLD (lithium plating; Preger, Wittman, Luh & Blank),
    # but storage (calendar ageing) is faster when hot for every chemistry.
    t, soc = np.array([0.0, 86400.0]), np.array([0.8, 0.8])
    cool = predict_capacity(chemistry, t, soc, np.full(2, 15.0), 365)[-1]
    hot = predict_capacity(chemistry, t, soc, np.full(2, 40.0), 365)[-1]
    assert hot < cool


def test_sodium_default_fade_reaches_80_percent_near_400_cycles():
    # Liu et al. 2026: commercial layered-oxide 18650 cells, full cycles, 80 % after ~400-450
    t, soc = standard_profile(0.3, 0.3)
    q = predict_capacity("Na-ion", t, soc, np.full(len(t), 25.0), 600)
    assert 380 <= int(np.argmax(q < 0.8)) + 1 <= 460


def test_sodium_fade_rate_is_an_input():
    t, soc = standard_profile(0.3, 0.3)
    q = predict_capacity("Na-ion", t, soc, np.full(len(t), 25.0), 100, na_fade_per_efc=0.0001)
    assert abs((1 - q[-1]) - 0.01) < 0.001


def test_default_settings_inside_data_for_lithium():
    for chemistry in ["NMC", "LFP", "NCA"]:
        assert default_run(chemistry)["meta"]["ageing_warnings"] == []


def test_warning_outside_tested_range():
    assert validity_warnings("NMC", 45, 2.0, 1.0, 1.0)
    assert not validity_warnings("NCA", 25, 0.5, 1.0, 1.0)


def test_battery_test_reaches_10000_cycles():
    r = run_battery_test("LFP", "SPMe", n_cycles=10000)
    assert r["cycles"]["Cycle"].iloc[-1] == 10000
    assert 50 < r["cycles"]["SOH [%]"].iloc[999] < 100        # after 1,000 cycles


@pytest.mark.parametrize("chemistry", ["NMC", "LFP", "NCA"])
def test_resting_between_cycles_adds_calendar_ageing(chemistry):
    # One cycle a day must age the battery more than the same cycles run back to back,
    # because the battery also ages while it rests.
    t, soc = standard_profile(0.5, 1.0)
    temp = np.full(len(t), 25.0)
    back_to_back = predict_capacity(chemistry, t, soc, temp, 3000)[-1]
    t2, soc2, temp2, used = add_rest(t, soc, temp, 365, 25.0)
    daily = predict_capacity(chemistry, t2, soc2, temp2, 3000)[-1]
    assert used == 365 and t2[-1] == 86400
    assert daily < back_to_back


def test_rest_not_added_when_cycles_are_too_long():
    t, soc = standard_profile(0.5, 1.0)                 # about 3 hours per cycle
    t2, _, _, used = add_rest(t, soc, np.full(len(t), 25.0), 10000, 25.0)
    assert len(t2) == len(t) and used < 10000


def test_sodium_fade_ignores_rest():
    # The sodium-ion model counts cycles only, so a rest must not change it.
    t, soc = standard_profile(0.3, 0.3)
    temp = np.full(len(t), 25.0)
    t2, soc2, temp2, _ = add_rest(t, soc, temp, 365, 25.0)
    assert np.allclose(predict_capacity("Na-ion", t, soc, temp, 100),
                       predict_capacity("Na-ion", t2, soc2, temp2, 100))


@pytest.mark.parametrize("chemistry", ["NMC", "Na-ion"])
def test_range_band_contains_expected_curve(chemistry):
    r = default_run(chemistry, "DFN" if chemistry == "Na-ion" else "SPMe")
    p = r["projection"].dropna(subset=["SOH low [%]"])
    assert (p["SOH low [%]"] <= p["SOH [%]"] + 1e-9).all()
    assert (p["SOH [%]"] <= p["SOH high [%]"] + 1e-9).all()
    low80, high80 = r["meta"]["cycles_to_80pct_range"]
    assert low80 <= r["meta"]["cycles_to_80pct"] <= high80


def test_fitted_values_come_from_the_fit_file():
    # As for the physics calibration: the values are read from data/ageing_fit.json (written
    # by scripts/fit_ageing.py), never copied by hand.
    with open(DATA_DIR / "ageing_fit.json") as f:
        fit = json.load(f)
    for cls, name in ((NcaRefit, "NCA"), (NmcRefit, "NMC"), (LfpAdjusted, "LFP")):
        for key, value in fit[name].items():
            assert getattr(cls, key) == value


def test_default_run_metadata():
    meta = default_run("NMC")["meta"]
    q = default_run("NMC")["projection"]["SOH [%]"].to_numpy() / 100
    assert meta["cycles_to_80pct"] == cycles_to(q, 0.8)
    assert meta["h_cooling"] > 0 and meta["cycling_c"] == 20.0


def test_ev_first_life_and_second_life_start():
    from battery_twin.ageing import ev_first_life, second_life_curve
    q, checks, (cal, cyc) = ev_first_life("LFP", 8, 50.0, 60.0, 0.16, 0.18, 20.0)
    assert len(q) == 8 * 365 and np.all(np.diff(q) <= 1e-12)        # only fades
    assert [day for _, day, _ in checks] == [1825, 2920]             # 5 y / 8 y come first
    assert abs(1 - cal - cyc - q[-1]) < 1e-12
    t, soc, temp = np.array([0.0, 3600, 7200, 86400]), np.array([1.0, 0.0, 1.0, 1.0]), np.full(4, 25.0)
    second = second_life_curve("LFP", t, soc, temp, 1000, (cal, cyc))
    assert abs(second[0] - q[-1]) < 0.002 and np.all(np.diff(second) <= 1e-12)
    # mostly calendar loss in the car: the storage calendar term has slowed down by then,
    # so the second life fades less than a new battery's storage curve from that capacity
    fresh = predict_capacity("LFP", t, soc, temp, 20000)
    i = int(np.flatnonzero(fresh <= q[-1])[0])
    assert q[-1] - second[-1] < fresh[i] - fresh[i + 999]
    # a loss the storage cycle never reaches is held (sodium-ion has no calendar loss)
    held = second_life_curve("Na-ion", t, soc, temp, 10, (0.3, 0.0))
    assert np.allclose(held, second_life_curve("Na-ion", t, soc, temp, 10, (0.0, 0.0)) - 0.3)


def test_lfp_resistance_growth_is_held_beyond_the_data():
    from battery_twin.lfp_blade_params import ageing_resistance
    assert ageing_resistance(1.0) == 0.0
    assert ageing_resistance(0.95) < ageing_resistance(0.92) == ageing_resistance(0.7)


def test_nmc_car_first_life_matches_the_smart_fleet():
    # Rücker et al. 2024: Smart-1 (NMC) lost 6.8 % in 719 days and 27,028 km (Table D.13);
    # the field-scaled model gives 5.6 % (charged to 80 % here), the laboratory model 16.2 %
    from battery_twin.ageing import ev_first_life
    q, _, _ = ev_first_life("NMC", 718.6 / 365, 27028 / 718.6, 17.6, 0.157, 0.55, 10.0)
    assert abs((1 - q[-1]) - 0.068) < 0.025


def test_fast_charging_in_the_car_ages_nmc_more():
    from battery_twin.ageing import ev_first_life
    slow = ev_first_life("NMC", 8, 50.0, 60.0, 0.16, 0.3, 20.0)[0][-1]
    some = ev_first_life("NMC", 8, 50.0, 60.0, 0.16, 0.3, 20.0, fast_share=0.2)[0][-1]
    all_fast = ev_first_life("NMC", 8, 50.0, 60.0, 0.16, 0.3, 20.0, fast_share=1.0)[0][-1]
    assert all_fast < some < slow


def test_nmc_second_life_uses_the_car_cells_field_factors():
    # a car's NMC cells keep their slower ageing in storage (Schreiber et al. 2025 highway test)
    import battery_twin.ageing as ageing
    t, soc, temp = np.array([0.0, 3600, 7200, 86400]), np.array([1.0, 0.0, 1.0, 1.0]), np.full(4, 25.0)
    _, _, car = ageing.ev_first_life("NMC", 8, 50.0, 60.0, 0.16, 0.3, 20.0)
    field = ageing.second_life_curve("NMC", t, soc, temp, 1000, car)[-1]
    lab = ageing.second_life_curve("NMC", t, soc, temp, 1000, car, field=False)[-1]
    assert field > lab


def test_sodium_car_life_uses_the_fade_rate_given():
    from battery_twin.ageing import ev_first_life
    default = ev_first_life("Na-ion", 8, 50.0, 60.0, 0.16, 0.3, 20.0)[0][-1]
    slow = ev_first_life("Na-ion", 8, 50.0, 60.0, 0.16, 0.3, 20.0, na_fade_per_efc=0.0001)[0][-1]
    assert slow > default + 0.1          # 0.01 %/cycle: about 96 % left instead of about 80 %
