"""Temperature spread along a coolant channel, and its effect on the ageing of each cell.

The physics model simulates one cell in coolant at the inlet temperature. In a pack the
coolant warms as it passes the cells, so cells further downstream run hotter and age at a
different rate. This module adds that one effect, nothing else.

Coolant energy balance (ThermoWeave, docs/model.md eq. 4, MIT licence,
github.com/mohammadrezwankhan/thermoweave-battery-digital-twin), one channel segment k per
cell, coolant fully mixed in each segment:

    (m_dot * cp + H) * T_c[k] = m_dot * cp * T_c[k-1] + H * T_cell[k]

At steady state each cell passes its own heat Q to the coolant, H * (T_cell[k] - T_c[k]) = Q,
which turns the balance into T_c[k] = T_c[k-1] + Q / (m_dot * cp). The cell's own rise
above its coolant, Q / H, is already in the physics model, so cell k runs
k * Q / (m_dot * cp) warmer than the simulated cell.

Not included: heat conduction between cells, cell-to-cell differences in capacity and
resistance (no measured spread is used here), balancing. The pack's usable capacity is
that of its weakest cell, as for cells in series without capacity balancing.
"""
import numpy as np

from .ageing import add_rest, predict_capacity

# Coolants: specific heat [J/(kg K)] and density [kg/m3]. Air at 300 K: Incropera et al.,
# Fundamentals of Heat and Mass Transfer, Table A.4. Water-glycol 50/50 at about 20 °C:
# typical data-sheet values (an assumption, listed in the Sources tab).
COOLANTS = {
    "Air": {"cp": 1007.0, "rho": 1.16},
    "Water-glycol 50/50": {"cp": 3300.0, "rho": 1070.0},
}


def mean_heat_w(efficiency_row, cycle_duration_h):
    """Mean heat released by one cell over a cycle [W]: the energy charged in minus the
    energy discharged, spread over the cycle."""
    loss_wh = efficiency_row["Charge energy [Wh]"] - efficiency_row["Discharge energy [Wh]"]
    return max(float(loss_wh), 0.0) / float(cycle_duration_h)


def coolant_temperatures(n_cells, heat_w, inlet_c, flow_l_min, coolant):
    """Coolant temperature in each segment [°C], marching from the inlet (eq. 4 above)."""
    c = COOLANTS[coolant]
    m_cp = c["rho"] * flow_l_min / 60000.0 * c["cp"]          # W/K
    temps = []
    t_c = float(inlet_c)
    for _ in range(int(n_cells)):
        t_c = t_c + heat_w / m_cp
        temps.append(t_c)
    return np.array(temps)


def pack_ageing(chemistry, profile, n_cells, heat_w, flow_l_min, coolant, cycles_per_year,
                ambient_c, n_cycles):
    """Relative capacity of each cell along the channel (rows) after cycles 1..n_cycles.

    profile: the simulated cycle (Time [s], SOC, Temperature [°C]). Each cell gets the same
    cycle, warmer by its coolant rise while cycling; all cells rest at ambient_c.
    Returns (offsets in K, capacities of shape n_cells x n_cycles)."""
    offsets = coolant_temperatures(n_cells, heat_w, 0.0, flow_l_min, coolant)
    caps = []
    for dt in offsets:
        t, soc, temp, _ = add_rest(profile["Time [s]"], profile["SOC"],
                                   np.asarray(profile["Temperature [°C]"]) + dt,
                                   cycles_per_year, ambient_c)
        caps.append(predict_capacity(chemistry, t, soc, temp, n_cycles))
    return offsets, np.array(caps)
