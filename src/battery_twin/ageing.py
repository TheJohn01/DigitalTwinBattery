"""Empirical capacity-fade models, each fitted to peer-reviewed ageing data.

The physics model (chemistry.py) simulates a few cycles in full. This module takes
the operating conditions of those cycles (state of charge over time, cell
temperature) and predicts capacity fade over thousands of cycles with an empirical
model fitted to measured data for a commercial cell of the same chemistry.

Sources (see also README.md):
- NMC  : NREL BLAST-Lite, LG M50 21700 (Truong Bui et al., IEEE 2021).
- LFP  : NREL BLAST-Lite, Sony-Murata 3 Ah 18650 (Naumann et al. 2018, 2020;
         model identification Gasper et al., J. Electrochem. Soc. 2022).
- NCA  : NREL BLAST-Lite, Panasonic NCR18650B (Keil et al. 2016; Preger et al. 2020).
- Na-ion: linear fade of 0.1 %/equivalent full cycle measured on a commercial
         hard-carbon/NVPF cell (Carter et al., Energies 18, 661, 2025).
"""
import numpy as np

from ._vendor.blast_lite import (Lfp_Gr_SonyMurata3Ah_Battery, Nca_Gr_Panasonic3Ah_Battery,
                                 Nmc811_GrSi_LGM50_5Ah_Battery)

class SodiumIonNVPF:
    """Linear fade per equivalent full cycle (EFC), commercial hard carbon / NVPF cell.

    Carter et al. (2025) measured about 0.1 % capacity loss per cycle over 100 cycles
    (CC-CV, C/3) for this cell. It was the WORST of the four commercial sodium-ion cells
    in that study: two others (layered oxide and Prussian blue cathodes) kept more than
    99 % after 100 cycles, i.e. under 0.01 % per cycle. The authors warn that early
    commercial cells vary a lot in quality and that four cells should not be generalised
    to a whole chemistry. The rate is therefore a user input in the dashboard.
    Klick et al. (Batteries & Supercaps 2025) found similar fade rates at 25 °C and 40 °C
    for another commercial sodium-ion cell, so no temperature dependence is applied.
    """
    FADE_PER_EFC = 0.001          # measured: worst of the four cells
    FADE_PER_EFC_BEST = 0.0001    # upper bound for the two best cells (>99 % after 100)
    experimental_range = {"cycling_temperature": [25, 40], "dod": [1.0, 1.0],
                          "max_rate_charge": 0.33, "max_rate_discharge": 0.33,
                          "max_cycles": 100}


AGEING_MODELS = {
    "NMC": Nmc811_GrSi_LGM50_5Ah_Battery,
    "LFP": Lfp_Gr_SonyMurata3Ah_Battery,
    "NCA": Nca_Gr_Panasonic3Ah_Battery,
    "Na-ion": SodiumIonNVPF,
}


SECONDS_PER_YEAR = 365 * 86400


def add_rest(t_secs, soc, temp_c, cycles_per_year, rest_temp_c):
    """Stretch one cycle so that it lasts as long as it does in real use.

    A battery cycled once a day spends the rest of the day idle, and it keeps ageing
    while idle (calendar ageing). Without this rest the ageing models would assume the
    cycles run back to back and under-count the calendar time. The rest is at the
    final state of charge, with the cell at the ambient temperature.

    Returns (t, soc, temp, cycles_per_year actually possible): if the cycle itself is
    longer than the requested period, no rest is added and the cycles run back to back.
    """
    t = np.asarray(t_secs, dtype=float) - float(np.asarray(t_secs)[0])
    soc = np.asarray(soc, dtype=float)
    temp = np.asarray(temp_c, dtype=float)
    period = SECONDS_PER_YEAR / float(cycles_per_year)
    if period <= t[-1] + 60:
        return t, soc, temp, SECONDS_PER_YEAR / t[-1]
    # one point a minute after the cycle (cell back at ambient), one at the end of the period
    t = np.append(t, [t[-1] + 60, period])
    soc = np.append(soc, [soc[-1], soc[-1]])
    temp = np.append(temp, [rest_temp_c, rest_temp_c])
    return t, soc, temp, float(cycles_per_year)


def _sigmoid(x, y_inf, k, p):
    return 2 * y_inf * (0.5 - 1 / (1 + np.exp((k * x) ** p)))


def predict_capacity(chemistry, t_secs, soc, temp_c, n_cycles,
                     na_fade_per_efc=SodiumIonNVPF.FADE_PER_EFC):
    """Relative capacity (1 = new) at the end of cycles 1..n_cycles.

    t_secs, soc, temp_c describe ONE representative cycle (from the physics model),
    which is assumed to repeat. The BLAST-Lite models compute their degradation rates
    from this cycle; because the rates are then constant, their capacity-loss
    trajectories have the closed forms used below (exact, and independent of step size).
    na_fade_per_efc is only used for sodium-ion (fraction lost per equivalent full cycle).
    """
    t_secs = np.asarray(t_secs, dtype=float) - float(np.asarray(t_secs)[0])
    soc = np.clip(np.asarray(soc, dtype=float), 0.0, 1.0)
    temp_c = np.asarray(temp_c, dtype=float)

    n = np.arange(1, int(n_cycles) + 1)
    efc_per_cycle = np.sum(np.abs(np.diff(soc))) / 2
    days_per_cycle = t_secs[-1] / 86400
    efc, t_days = n * efc_per_cycle, n * days_per_cycle

    if chemistry == "Na-ion":
        q = 1 - float(na_fade_per_efc) * efc
        return np.clip(q, 0.0, 1.0)

    model = AGEING_MODELS[chemistry]()
    model.update_battery_state(t_secs, soc, temp_c)      # computes the degradation rates
    r = {k: float(v[-1]) for k, v in model.rates.items()}
    p = model._params_life

    if chemistry == "NMC":       # LG M50: power laws in time and charge throughput
        loss = r["k_cal"] * (t_days / 1e4) ** p["p_cal"] + r["k_cyc"] * (efc / 1e4) ** p["p_cyc"]
    elif chemistry == "NCA":     # Panasonic NCR18650B: power laws in time and throughput
        loss = r["k_cal"] * t_days ** p["qcal_p"] + r["k_cyc"] * efc ** p["qcyc_p"]
    else:                        # LFP Sony-Murata: sigmoid in time, power law in throughput
        loss = _sigmoid(t_days, r["q1"], p["q2"], r["q3"]) + (r["q5"] * efc) ** p["q6"]
        if efc_per_cycle / days_per_cycle > 3:          # break-in, only for > 3 cycles/day
            loss = loss + _sigmoid(efc, r["q7"], p["q8"], p["q9"])
    return np.clip(1.0 - loss, 0.0, 1.0)


def validity_warnings(chemistry, temp_c, c_charge, c_discharge, dod, n_cycles=0):
    """Plain-language warnings when the conditions are outside the tested range."""
    rng = AGEING_MODELS[chemistry]().experimental_range
    notes = []
    t_low, t_high = rng["cycling_temperature"]
    if not t_low - 2 <= temp_c <= t_high + 2:
        notes.append(f"cell temperature {temp_c:.0f} °C (tested {t_low}–{t_high} °C)")
    if c_charge > rng["max_rate_charge"] + 1e-9:
        notes.append(f"charge rate {c_charge:g}C (tested up to {rng['max_rate_charge']:g}C)")
    if c_discharge > rng["max_rate_discharge"] + 1e-9:
        notes.append(f"discharge rate {c_discharge:g}C (tested up to {rng['max_rate_discharge']:g}C)")
    if dod < min(rng["dod"]) - 0.05:
        notes.append(f"depth of discharge {dod:.0%} (tested from {min(rng['dod']):.0%})")
    if n_cycles > rng.get("max_cycles", float("inf")):
        notes.append(f"{n_cycles:,} cycles (measured up to {rng['max_cycles']} cycles)")
    return notes
