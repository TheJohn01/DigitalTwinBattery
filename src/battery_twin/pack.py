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
from statistics import NormalDist

import numpy as np

from .ageing import add_rest, predict_capacity

# Cell-to-cell variation: standard deviation of log cycle life of 48 cells from one production
# lot aged identically (Baumhöfer et al., J. Power Sources 247 (2014) 332, NMC/graphite 18650,
# 20-80 % at 25 °C, channels checked): lives to 84 % of 850-1,200 cycles, a range of
# ln(1200/850) = 4.47 standard deviations for 48 normal samples. Severson et al.'s fast-charged
# A123 cells gave 0.18 (an upper bound; tests/test_pack.py).
CELL_LOG_LIFE_SD = 0.077
PACK_VOLTAGE = 400.0      # assumed: a typical 400 V electric-car or storage pack

# Coolants: specific heat [J/(kg K)] and density [kg/m3]. Air at 300 K: Incropera et al.,
# Fundamentals of Heat and Mass Transfer, Table A.4. Water-glycol 50 wt% at 25 °C: MEGlobal,
# Ethylene Glycol product guide, Fig. 8 (cp = 0.81485 + 7.3219e-4 T Btu/lb/°F = 3,490 J/kg/K)
# and Fig. 17 (specific gravity 1.0625 at 77 °F, interpolated between the 50 and 100 °F fits).
COOLANTS = {
    "Air": {"cp": 1007.0, "rho": 1.16},
    "Water-glycol 50/50": {"cp": 3490.0, "rho": 1060.0},
}


def mean_heat_w(efficiency_row, cycle_duration_h):
    """Mean heat released by one cell over a cycle [W]: the energy charged in minus the
    energy discharged, spread over the cycle."""
    loss_wh = efficiency_row["Charge energy [Wh]"] - efficiency_row["Discharge energy [Wh]"]
    return max(float(loss_wh), 0.0) / float(cycle_duration_h)


def coolant_temperatures(n_cells, heat_w, inlet_c, flow_l_min, coolant):
    """Coolant temperature after each cell [°C] (eq. 4 above): each cell adds Q / (m_dot cp)."""
    c = COOLANTS[coolant]
    m_cp = c["rho"] * flow_l_min / 60000.0 * c["cp"]          # W/K
    return float(inlet_c) + heat_w / m_cp * np.arange(1, int(n_cells) + 1)


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


def spread_factor(n_cells, cell_voltage, sd=CELL_LOG_LIFE_SD, pack_voltage=PACK_VOLTAGE):
    """Loss of the weakest parallel group / loss of a mean cell. The pack is n_cells cells,
    pack_voltage / cell_voltage groups in series; a group of p parallel cells varies by
    sd / sqrt(p), and the weakest of the series groups sits at the 1 / (groups + 1) quantile.
    shortcut: life spread used as loss spread (fade close to linear), log-normal assumed."""
    series = max(1, round(pack_voltage / cell_voltage))
    parallel = max(1.0, n_cells / series)
    return float(np.exp(-sd / np.sqrt(parallel) * NormalDist().inv_cdf(1 / (series + 1))))


def weakest_cell_curve(chemistry, t, soc, temp, cycle_end_s, offsets, n_cycles, spread=1.0):
    """Capacity of the pack's weakest cell after 1..n_cycles of a cycle (t, soc, temp, with
    the rest after cycle_end_s already added): each cell is warmer by its offset while it
    cycles and rests at the same temperature; spread multiplies the loss (spread_factor)."""
    cycling = np.asarray(t) <= cycle_end_s
    caps = [predict_capacity(chemistry, t, soc, np.asarray(temp) + dt * cycling, n_cycles)
            for dt in offsets]
    return np.clip(1 - spread * (1 - np.min(caps, axis=0)), 0.0, 1.0)
