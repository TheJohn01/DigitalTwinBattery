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


def test_nca_matches_preger(monkeypatch):
    # Preger et al. 2020 (Panasonic NCR18650B), 0-100 %, 25 °C, 1C discharge: about 430
    # cycles to 80 %, at the Panasonic level
    monkeypatch.setattr(NcaRefit, "LEVEL_50E", 1.0)
    monkeypatch.setattr(NcaRefit, "DIS_RATE", NcaRefit.C_RATE)
    assert 350 < cycles_to_80("NCA", 0, 1, 1.0, 25) < 520


def test_nca_is_at_the_samsung_50e_level():
    # The program's NCA cell (Samsung 50E) fitted to REBELION's cells: about 1,500 cycles to
    # 80 % at 0-100 %, 1C, like Ohneseit's 21700 NCA cells (about 1,300-1,500 at 20 °C)
    assert 1200 < cycles_to_80("NCA", 0, 1, 1.0, 25) < 1900


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


def test_nmc_life_at_45_vs_35_degrees_like_zhu():
    # Zhu et al. 2022 NCM cells, 0.5C charge / 1C discharge: 45 °C life = 0.61 x 35 °C life
    ratio = cycles_to_80("NMC", 0, 1, 1.0, 45) / cycles_to_80("NMC", 0, 1, 1.0, 35)
    assert 0.5 < ratio < 0.8


@pytest.mark.parametrize("chemistry", ["NMC", "LFP", "NCA"])
def test_storage_ages_faster_when_hotter(chemistry):
    # NMC cycling ages faster when COLD (lithium plating; Preger, Wittman, Luh & Blank),
    # but storage (calendar ageing) is faster when hot for every chemistry.
    t, soc = np.array([0.0, 86400.0]), np.array([0.8, 0.8])
    cool = predict_capacity(chemistry, t, soc, np.full(2, 15.0), 365)[-1]
    hot = predict_capacity(chemistry, t, soc, np.full(2, 40.0), 365)[-1]
    assert hot < cool


def test_sodium_full_cycles_reach_80_percent_within_the_tum_cells():
    # TUM, Mushang cells cycled 0-100 % at 1C back to back: 80 % after 532-1,361 EFC
    t, soc = standard_profile(1.0, 1.0)
    q = predict_capacity("Na-ion", t, soc, np.full(len(t), 25.0), 3000)
    assert 532 <= cycles_to(q, 0.8) <= 1361


def test_sodium_constants_match_the_tum_data():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "fit_sodium.py"
    spec = importlib.util.spec_from_file_location("fit_sodium", path)
    fs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fs)
    f = fs.fit()
    from battery_twin.ageing import SodiumIon as S
    assert np.allclose(f["K_CAL"], S.K_CAL, atol=1e-4)
    assert abs(f["FADE_PER_EFC"] - S.FADE_PER_EFC) < 1e-6
    assert abs(f["FADE_PER_EFC_WORST"] - S.FADE_PER_EFC_WORST) < 1e-6
    assert abs(f["PARTIAL_FACTOR"] - S.PARTIAL_FACTOR) < 0.002
    assert abs(f["PARTIAL_FACTOR_WORST"] - S.PARTIAL_FACTOR_WORST) < 0.002
    # the 20 % windows lost no more than the calendar loss of their SOC (within 1 point)
    w = fs.window_check(fs.checkups(), f["K_CAL"])
    assert (w["measured loss [%]"] <= w["calendar alone [%]"] + 1).all()


def test_sodium_fade_rate_is_an_input():
    t, soc = standard_profile(0.3, 0.3)
    cyc = predict_capacity("Na-ion", t, soc, np.full(len(t), 25.0), 100, na_fade_per_efc=0.0001,
                           parts=True)[1]
    assert abs(cyc[-1] - 0.01) < 0.001


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


def test_sodium_rest_adds_calendar_loss_by_soc():
    # TUM storage tests: about 1 % per sqrt(year) at 10-30 % SOC, 5-6.6 % at 50-90 %
    t, soc = standard_profile(0.3, 0.3)
    temp = np.full(len(t), 25.0)
    t2, soc2, temp2, _ = add_rest(t, soc, temp, 365, 25.0)
    assert np.all(predict_capacity("Na-ion", t2, soc2, temp2, 100)
                  < predict_capacity("Na-ion", t, soc, temp, 100))
    day = np.array([0.0, 86400.0])
    low, high = (predict_capacity("Na-ion", day, np.full(2, s), np.full(2, 25.0), 365, parts=True)[0][-1]
                 for s in (0.1, 0.5))
    assert abs(low - 0.0103) < 0.001 and abs(high - 0.0508) < 0.001


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
    # a loss the storage cycle never reaches within its search is held
    held = second_life_curve("Na-ion", t, soc, temp, 10, (0.9, 0.0))
    assert np.allclose(held, np.clip(second_life_curve("Na-ion", t, soc, temp, 10, (0.0, 0.0))
                                     - 0.9, 0, 1), atol=0.02)


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
    assert 0.85 < all_fast < slow - 0.01     # 20-80 % trips at 1.2C: a little more wear


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
    default = ev_first_life("Na-ion", 8, 50.0, 60.0, 0.16, 0.3, 20.0)[2][1]
    slow = ev_first_life("Na-ion", 8, 50.0, 60.0, 0.16, 0.3, 20.0, na_fade_per_efc=0.0001)[2][1]
    # the car's shallow cycles fade at SodiumIon.PARTIAL_FACTOR of the full-cycle rate, and
    # the cycling loss scales with the rate given
    from battery_twin.ageing import SodiumIon
    assert abs(default / slow - SodiumIon.FADE_PER_EFC / 0.0001) < 0.01


def test_lfp_knee_keeps_cycle_life_and_lowers_mid_life_fade(monkeypatch):
    # Severson's fast-charged LFP cells stay nearly flat and then drop: the knee must leave
    # the cycle life (80 %) about where it was fitted and show less fade at half of it than
    # a straight line. Slow charging (no fast-charge wear) has no knee.
    from battery_twin.ageing import LfpAdjusted, cycles_to
    slow_t, slow_soc = standard_profile(0.5, 1.0)
    slow = predict_capacity("LFP", slow_t, slow_soc, np.full(len(slow_t), 25.0), 3000)
    from battery_twin.severson import CHAMBER_C, severson_cycle
    t, soc = severson_cycle("4.8C(80%)-4.8C")
    temp = np.full(len(t), CHAMBER_C)
    knee = predict_capacity("LFP", t, soc, temp, 6000)
    monkeypatch.setattr(LfpAdjusted, "KNEE", 1.0)
    straight = predict_capacity("LFP", t, soc, temp, 6000)
    life = cycles_to(straight, 0.8)
    assert abs(cycles_to(knee, 0.8) / life - 1) < 0.15
    half = int(life) // 2
    assert knee[half] > straight[half] + 0.03
    assert np.allclose(slow, predict_capacity("LFP", slow_t, slow_soc,
                                              np.full(len(slow_t), 25.0), 3000))


def test_lfp_fade_below_80_percent_like_wheeler():
    # 20 A123 cells aged at 50 °C to 31-64 % (Wheeler et al. 2025). Slowly charged cells at
    # 70 % depth fade steadily below 80 % (R = cycles 70->60 % / cycles 90->80 %, 1.04-1.45).
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "validate_lfp_wheeler.py"
    spec = importlib.util.spec_from_file_location("validate_lfp_wheeler", path)
    w = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(w)
    cells = w.measured()
    slow = cells[cells.group <= 3].R.dropna()
    q = w.model_curve(1, 12_000)
    assert slow.min() <= w.shape_ratio(np.arange(1, len(q) + 1), q) <= slow.max()
    # the dashboard's storage cycle: no knee, and not a slower late fade than those cells
    assert 0.9 < w.default_storage_r() <= slow.median()


def test_lfp_second_life_after_a_knee_is_faster_than_the_model():
    # UConn-MathWorks cells retired at 70-76 % after a knee, then cycled at 0.5C to 47 %: the
    # program's second life (loss matched on the storage curve, no memory of a knee) shows a
    # small part of that loss. Documented limit (README Section 10.1); update if it changes.
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "validate_lfp_second_life.py"
    spec = importlib.util.spec_from_file_location("validate_lfp_second_life", path)
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    d = v.compare()
    assert (d["measured at the end [%]"] < 50).all()
    assert (d["measured loss / model loss"] > 10).all()


def _validate_lfp_calendar():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "validate_lfp_calendar.py"
    spec = importlib.util.spec_from_file_location("validate_lfp_calendar", path)
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    return v


def test_lfp_calendar_within_stanford_cells_at_24_c():
    # K2 Energy LFP cells stored 7.5 years at 24 °C (Lam et al.): the model stays within the two
    # cell types' medians, give or take 1.5 points
    t = _validate_lfp_calendar().stanford().loc[24]
    lo, hi = t[["LFP18650E", "LFP18650P"]].min(axis=1), t[["LFP18650E", "LFP18650P"]].max(axis=1)
    assert ((t.model >= lo - 1.5) & (t.model <= hi + 1.5)).all()


def test_lfp_heat_term_matches_offenburg_cells_at_52_c():
    # 200 Ah LFP cells cycled at 36.5 and 52 °C (Yagci et al.): the heat term brings the hot
    # cells within 3 points RMS; without it they are 5 points off
    d = _validate_lfp_calendar().offenburg_cycling()
    hot = d[d.chamber_c == 50]
    assert np.sqrt(np.mean((hot.model - hot.rel) ** 2)) < 0.03
    assert np.sqrt(np.mean((hot["no heat term"] - hot.rel) ** 2)) > 0.04


def test_nmc_matches_the_tum_mj1_cells():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "validate_nmc_mj1.py"
    spec = importlib.util.spec_from_file_location("validate_nmc_mj1", path)
    mj1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mj1)
    s = mj1.summary(mj1.evaluate())
    # charged at the rated rate or slower: within 5 %-points, and right at 10 % depth
    assert s["RMS error over their check-ups [%-points]"] < 5.5
    assert abs(s["10 % depth cells, mean error at the end [%-points]"]) < 2
    # faster and deep: the cells fail far sooner than the model says (a warning, not a fit)
    assert s["  measured capacity at the end, median [%]"] < 60
    from battery_twin.ageing import validity_warnings
    assert any("MJ1" in n for n in validity_warnings("NMC", 25, 1.0, 1.0, 1.0))
    assert not any("MJ1" in n for n in validity_warnings("NMC", 25, 0.3, 1.0, 1.0))
    # resistance: the aged windows' 1 / capacity rule is a little above the measured growth
    g = mj1.resistance_growth()
    ratio = g["1 / capacity"] / g["measured R / R new"]
    assert (ratio >= 1.0).all() and (ratio < 1.16).all()


def test_sodium_depth_factor_shape():
    from battery_twin.ageing import SodiumIon
    assert SodiumIon.dod_factor(1.0) == 1.0
    assert SodiumIon.dod_factor(0.6) == SodiumIon.dod_factor(0.13) == SodiumIon.PARTIAL_FACTOR
    assert SodiumIon.PARTIAL_FACTOR < SodiumIon.dod_factor(0.8) < 1.0


def test_nca_charge_rate_matches_the_50e_at_23_and_40_c():
    # Huang et al. 2026, Samsung 50E, 0-100 %, 1C discharge: 1C charge reaches 80 % after
    # about 430 cycles at 23 °C and 790 at 40 °C; 0.5C charge at 23 °C had lost only 10 % at
    # 500 cycles. (At 40 °C and 0.5C the model lasts too long: about 1,200 vs 850.)
    assert 380 < cycles_to_80("NCA", 0, 1, 1.0, 23, c_charge=1.0) < 600
    assert 600 < cycles_to_80("NCA", 0, 1, 1.0, 40, c_charge=1.0) < 1000
    assert cycles_to_80("NCA", 0, 1, 1.0, 23, c_charge=0.5) > 2 * 430


def test_storage_cycle_halves_the_swing_and_the_warming():
    from battery_twin.ageing import storage_cycle
    t, soc, temp = [0, 1, 2], [1.0, 0.0, 1.0], [25.0, 35.0, 25.0]
    same = storage_cycle(t, soc, temp, 1.0, 25.0)
    assert np.allclose(same[1], soc) and np.allclose(same[2], temp)
    _, soc_h, temp_h = storage_cycle(t, soc, temp, 0.5, 25.0)
    assert np.allclose(soc_h, [0.75, 0.25, 0.75]) and np.allclose(temp_h, [25.0, 30.0, 25.0])


def test_lfp_level_restores_the_model_after_an_error():
    from battery_twin.ageing import LfpAdjusted, lfp_level
    scale, hot = LfpAdjusted.SCALE, LfpAdjusted.K_HOT
    try:
        with lfp_level(2.0, K_HOT=0.0):
            assert LfpAdjusted.SCALE == 2 * scale and LfpAdjusted.K_HOT == 0.0
            raise ValueError
    except ValueError:
        pass
    assert (LfpAdjusted.SCALE, LfpAdjusted.K_HOT) == (scale, hot)


def test_used_battery_continues_the_new_curve_from_its_soh():
    import pytest
    from battery_twin.ageing import ev_first_life, from_soh
    q = np.array([1.0, 0.95, 0.9, 0.85, 0.8])
    assert np.allclose(from_soh(q, 0.9, 4)[:3], [0.9, 0.85, 0.8]) and np.isnan(from_soh(q, 0.9, 4)[3])
    with pytest.raises(ValueError):
        from_soh(q, 0.5, 3)
    new, checks, _ = ev_first_life("NMC", 16, 50.0, 60.0, 0.16, 0.3, 20.0)
    used, checks_used, _ = ev_first_life("NMC", 8, 50.0, 60.0, 0.16, 0.3, 20.0, start_soh=0.9)
    k = int(np.argmax(new <= 0.9))
    assert used[0] <= 0.9 and np.allclose(used[:365], new[k:k + 365])
    assert checks_used[0][:2] == checks[0][:2]     # Euro 7 checks stay those of the car from new
