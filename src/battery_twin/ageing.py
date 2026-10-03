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

    Carter et al. (2025) measured about 0.1 % capacity loss per cycle at C/3, 100 % depth
    of discharge, in a 25 °C chamber. Klick et al. (Batteries & Supercaps 2025) found
    similar fade rates at 25 °C and 40 °C for another commercial sodium-ion cell, so no
    temperature dependence is applied between 25 and 40 °C.
    """
    FADE_PER_EFC = 0.001
    experimental_range = {"cycling_temperature": [25, 40], "dod": [1.0, 1.0],
                          "max_rate_charge": 0.33, "max_rate_discharge": 0.33,
                          "max_cycles": 100}


AGEING_MODELS = {
    "NMC": Nmc811_GrSi_LGM50_5Ah_Battery,
    "LFP": Lfp_Gr_SonyMurata3Ah_Battery,
    "NCA": Nca_Gr_Panasonic3Ah_Battery,
    "Na-ion": SodiumIonNVPF,
}


def _sigmoid(x, y_inf, k, p):
    return 2 * y_inf * (0.5 - 1 / (1 + np.exp((k * x) ** p)))


def predict_capacity(chemistry, t_secs, soc, temp_c, n_cycles):
    """Relative capacity (1 = new) at the end of cycles 1..n_cycles.

    t_secs, soc, temp_c describe ONE representative cycle (from the physics model),
    which is assumed to repeat. The BLAST-Lite models compute their degradation rates
    from this cycle; because the rates are then constant, their capacity-loss
    trajectories have the closed forms used below (exact, and independent of step size).
    """
    t_secs = np.asarray(t_secs, dtype=float) - float(np.asarray(t_secs)[0])
    soc = np.clip(np.asarray(soc, dtype=float), 0.0, 1.0)
    temp_c = np.asarray(temp_c, dtype=float)

    n = np.arange(1, int(n_cycles) + 1)
    efc_per_cycle = np.sum(np.abs(np.diff(soc))) / 2
    days_per_cycle = t_secs[-1] / 86400
    efc, t_days = n * efc_per_cycle, n * days_per_cycle

    if chemistry == "Na-ion":
        q = 1 - SodiumIonNVPF.FADE_PER_EFC * efc
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
