"""Empirical ageing models: exactness, physical trends and validity warnings."""
import numpy as np
import pytest

from battery_twin.ageing import AGEING_MODELS, predict_capacity, validity_warnings
from battery_twin.chemistry import CHEMISTRIES, run_battery_test, standard_profile


@pytest.mark.parametrize("chemistry", ["NMC", "LFP", "NCA"])
def test_closed_form_matches_blast_stepping(chemistry):
    t, soc = standard_profile(0.5, 1.0)
    temp = np.full(len(t), 25.0)
    q = predict_capacity(chemistry, t, soc, temp, 300)
    model = AGEING_MODELS[chemistry]()
    model.update_battery_state(t, soc, temp)
    for _ in range(299):
        model.update_battery_state_repeating()
    assert abs(q[-1] - model.outputs["q"][-1]) < 0.002


@pytest.mark.parametrize("chemistry", list(CHEMISTRIES))
def test_capacity_falls_with_cycles(chemistry):
    t, soc = standard_profile(0.5, 1.0)
    q = predict_capacity(chemistry, t, soc, np.full(len(t), 25.0), 2000)
    assert q[0] <= 1 and np.all(np.diff(q) <= 1e-12) and q[-1] < q[0]


@pytest.mark.parametrize("chemistry", ["NMC", "LFP", "NCA"])
def test_hotter_ages_faster(chemistry):
    t, soc = standard_profile(0.5, 1.0)
    cool = predict_capacity(chemistry, t, soc, np.full(len(t), 15.0), 1000)[-1]
    hot = predict_capacity(chemistry, t, soc, np.full(len(t), 40.0), 1000)[-1]
    assert hot < cool


def test_sodium_fades_0p1_percent_per_cycle():
    t, soc = standard_profile(0.3, 0.3)
    q = predict_capacity("Na-ion", t, soc, np.full(len(t), 25.0), 100)
    assert abs((1 - q[-1]) - 0.10) < 0.005


def test_warning_outside_tested_range():
    assert validity_warnings("NMC", 45, 2.0, 1.0, 1.0)
    assert not validity_warnings("NCA", 25, 0.5, 1.0, 1.0)


def test_battery_test_reaches_10000_cycles():
    r = run_battery_test("LFP", "SPMe", n_cycles=10000)
    assert r["cycles"]["Cycle"].iloc[-1] == 10000
    assert 50 < r["cycles"]["SOH [%]"].iloc[-1] < 100
