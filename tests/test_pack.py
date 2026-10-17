"""Coolant-channel temperature spread (battery_twin.pack)."""
import numpy as np

from battery_twin.chemistry import standard_profile
from battery_twin.pack import COOLANTS, coolant_temperatures, mean_heat_w, pack_ageing


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
