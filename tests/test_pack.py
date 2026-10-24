"""Coolant-channel temperature spread (battery_twin.pack)."""
import numpy as np

from battery_twin.chemistry import standard_profile
from battery_twin.ageing import add_rest, predict_capacity
from battery_twin.pack import (COOLANTS, SEVERSON_LOG_LIFE_SD, coolant_temperatures,
                               mean_heat_w, pack_ageing, spread_factor, weakest_cell_curve)


def test_energy_balance():
    # All the heat of the cells ends up in the coolant: m_dot * cp * (T_out - T_in) = n * Q
    temps = coolant_temperatures(10, 2.0, 25.0, 1.0, "Water-glycol 50/50")
    c = COOLANTS["Water-glycol 50/50"]
    m_cp = c["rho"] * 1.0 / 60000 * c["cp"]
    assert np.isclose(m_cp * (temps[-1] - 25.0), 10 * 2.0)
    assert np.all(np.diff(temps) > 0)


def test_more_flow_smaller_spread():
    slow = coolant_temperatures(12, 1.0, 20.0, 30.0, "Air")
    fast = coolant_temperatures(12, 1.0, 20.0, 300.0, "Air")
    assert slow[-1] - 20.0 > fast[-1] - 20.0 > 0


def test_mean_heat():
    row = {"Charge energy [Wh]": 20.0, "Discharge energy [Wh]": 18.0}
    assert np.isclose(mean_heat_w(row, 4.0), 0.5)


def test_hotter_lfp_cells_age_faster_and_no_heat_means_identical_cells():
    t, soc = standard_profile(0.5, 1.0)
    profile = {"Time [s]": t, "SOC": soc, "Temperature [°C]": np.full(len(t), 25.0)}
    _, caps = pack_ageing("LFP", profile, 5, 3.0, 20.0, "Air", 365, 20.0, 2000)
    assert caps[-1, -1] < caps[0, -1]
    _, same = pack_ageing("LFP", profile, 5, 0.0, 20.0, "Air", 365, 20.0, 2000)
    assert np.allclose(same, same[0])


def test_coolant_rise_is_the_same_for_every_cell():
    # Each cell passes the same heat Q to the coolant, so the coolant warms by Q / (m_dot cp)
    # per cell: an arithmetic progression from the inlet.
    temps = coolant_temperatures(5, 2.0, 25.0, 1.0, "Water-glycol 50/50")
    assert np.allclose(np.diff(np.concatenate([[25.0], temps])), temps[0] - 25.0)


def test_severson_spread_is_recomputed_from_the_data():
    from battery_twin.severson import EXCLUDED_BATCH, load_cells
    d = load_cells()
    d = d[d.batch_date != EXCLUDED_BATCH]
    dev = [np.log(g) - np.log(g).mean() for _, g in d.groupby("charging_policy").cycle_life
           if len(g) > 1]
    dof = sum(len(x) - 1 for x in dev)
    assert abs(np.sqrt(np.sum(np.concatenate(dev) ** 2) / dof) - SEVERSON_LOG_LIFE_SD) < 0.005


def test_weakest_cell_and_spread():
    # many parallel cells average out; single large cells in series do not
    assert 1.0 < spread_factor(3300, 3.7) < 1.15 < spread_factor(140, 3.2)
    t, soc = standard_profile(0.5, 1.0)
    end = t[-1]
    t, soc, temp, _ = add_rest(t, soc, np.full(len(t), 25.0), 365, 20.0)
    mean = predict_capacity("LFP", t, soc, temp, 3000)
    assert np.allclose(weakest_cell_curve("LFP", t, soc, temp, end, [0.0], 3000), mean)
    weak = weakest_cell_curve("LFP", t, soc, temp, end, [0.0, 5.0], 3000, spread=1.5)
    assert np.allclose(weak, 1 - 1.5 * (1 - weakest_cell_curve("LFP", t, soc, temp, end,
                                                               [0.0, 5.0], 3000)))
    assert weak[-1] < mean[-1]
