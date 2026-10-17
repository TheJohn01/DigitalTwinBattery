"""Measurement update (battery_twin.update) and the Severson per-cycle data."""
import numpy as np
import pandas as pd

from battery_twin.ageing import cycles_to
from battery_twin.severson import load_cells, load_curves, model_curve
from battery_twin.update import read_measurements, update_scale, updated_curve

N = np.arange(1, 2001)
MODEL = 1 - 0.1 * (N / 1000)          # a simple twin: 10 % loss per 1,000 cycles


def test_no_data_disagreement_keeps_the_twin():
    k = update_scale(N[:300:10], MODEL[:300:10], MODEL)
    assert abs(k - 1) < 1e-3


def test_update_moves_towards_the_measurements():
    measured = 1 - 0.05 * (N / 1000)                 # the real cell fades half as fast
    k = update_scale(N[:500:10], measured[:500:10], MODEL)
    assert 0.5 < k < 0.8                             # the prior keeps it from going all the way
    k_more = update_scale(N[:1500:10], measured[:1500:10], MODEL)
    assert abs(k_more - 0.5) < abs(k - 0.5)          # more data, closer to the truth


def test_prior_dominates_few_noisy_points():
    k = update_scale([100, 200], [0.985, 0.985], MODEL, noise=0.5)
    assert abs(k - 1) < 0.01


def test_updated_curve():
    assert np.allclose(updated_curve(MODEL, 1.0), MODEL)
    assert np.allclose(1 - updated_curve(MODEL, 0.5), 0.5 * (1 - MODEL))


def test_read_measurements_percent_and_junk():
    df = pd.DataFrame({"cycle": ["300", "100", "x", "5000"], "soh": [97.0, 99.0, 98.0, 90.0]})
    n, soh = read_measurements(df, max_cycle=2000)
    assert list(n) == [100, 300]
    assert np.allclose(soh, [0.99, 0.97])


def test_severson_curves_match_published_cycle_life():
    cells = load_cells().set_index("barcode")
    curves = load_curves()
    assert len(curves) == 123
    for barcode, (n, soh) in list(curves.items())[::10]:
        life = cells.loc[barcode, "cycle_life"]
        below = np.where(soh <= 0.8)[0]
        reached = n[below[0]] if len(below) else n[-1] + 1
        assert abs(reached - life) <= 20     # file keeps every 10th cycle; capacity is noisy


def test_model_curve_a123_level_lasts_longer():
    policy = "4C(80%)-4C"
    a123, ohneseit = model_curve(policy, 5000), model_curve(policy, 5000, False)
    assert cycles_to(a123, 0.8) > 2 * cycles_to(ohneseit, 0.8)
