"""Empirical capacity-fade models, each fitted to peer-reviewed ageing data.

The physics model (chemistry.py) simulates a few cycles in full. This module takes
the operating conditions of those cycles (state of charge over time, cell
temperature) and predicts capacity fade over thousands of cycles with an empirical
model fitted to measured data for a commercial cell of the same chemistry.

Sources (see also README.md):
- NMC  : calendar term from NREL BLAST-Lite, LG M50 21700 (Truong Bui et al., IEEE 2021);
         cycling term with lithium plating refitted to LG HG2 data (NmcRefit below).
- LFP  : NREL BLAST-Lite, Sony-Murata 3 Ah 18650 (Naumann et al. 2018, 2020;
         model identification Gasper et al., J. Electrochem. Soc. 2022), with the
         cycling term rescaled and given a fast-charging factor (LfpAdjusted below).
- NCA  : Panasonic NCR18650B. Calendar term from NREL BLAST-Lite (Keil et al. 2016);
         cycling term refitted to Preger et al. 2020 (NcaRefit below).
- Na-ion: linear fade of 0.1 %/equivalent full cycle measured on a commercial
         hard-carbon/NVPF cell (Carter et al., Energies 18, 661, 2025).

The refitted numbers come from scripts/fit_ageing.py, which fits them to the published
values in data/published_ageing.csv (read from the papers' figures and text) and writes
them to ageing_fit.json. They are read from data/ageing_fit.json, as the physics
calibration is read from data/calibration.json, so nothing is copied by hand.
"""
import json

import numpy as np

from ._vendor.blast_lite import (Lfp_Gr_SonyMurata3Ah_Battery, Nca_Gr_Panasonic3Ah_Battery,
                                 Nmc811_GrSi_LGM50_5Ah_Battery)
from .constants import DATA_DIR

with open(DATA_DIR / "ageing_fit.json") as _f:
    FIT = json.load(_f)

MIN_SOH = 50.0              # the ageing data do not go below this capacity [%]


class NcaRefit(Nca_Gr_Panasonic3Ah_Battery):
    """Panasonic NCR18650B: BLAST-Lite calendar term + cycling term refitted to Preger 2020.

    BLAST-Lite's own cycling term for this cell predicts about 5,000 equivalent full cycles
    (EFC) to 80 % at 0-100 %, 25 °C, 1C, where Preger et al. measured about 430 on the same
    cell. Its temperature and C-rate constants are so small that they have no effect. The
    cycling loss is therefore refitted to Preger's data:

        cycling loss = A * dod**B_DOD * c_dis**(-C_RATE) * EFC**P

    dod is the depth of discharge (0-1) and c_dis the mean discharge C-rate, clipped to the
    tested 0.5-2C. Preger found no clear temperature effect on cycling between 15 and 35 °C,
    so the cycling term has none; temperature still acts through the calendar term. Faster discharge giving slower fade
    is what Preger measured at all three temperatures (cause unclear).
    """
    # Fitted by scripts/fit_ageing.py to 18 points (RMS error 2.0 %-points of capacity)
    A, B_DOD, C_RATE, P = (FIT["NCA"][k] for k in ("A", "B_DOD", "C_RATE", "P"))

    def __init__(self):
        super().__init__()
        self.experimental_range = {"cycling_temperature": [15, 35], "dod": [0.2, 1.0],
                                   "soc": [0, 1], "max_rate_charge": 0.5,
                                   "max_rate_discharge": 2}


class NmcRefit(Nmc811_GrSi_LGM50_5Ah_Battery):
    """NMC: BLAST-Lite LG M50 calendar term + a cycling term refitted to measured data.

        cycling loss = dod**B_DOD * (K_BASE + K_PL * c_ch**N_CH * exp(-(T_ch - 25) / T_PL)) * EFC**P

    The second term grows with the charge rate c_ch (charge-weighted mean) and with colder
    cell temperature while charging, T_ch; Luh & Blank attribute this fast loss to lithium
    plating. The fit uses the LG HG2 (NMC, graphite +
    SiO) data of Luh & Blank 2024 (charge 1/3, 1 and 5/3C at 0, 10, 25 and 40 °C), Preger
    et al. 2020 and Wittman et al. 2023 (same cell), and Ohneseit et al. 2025 (NMC811 + Si
    21700). Discharge rate has no clear effect in these data (Preger: 0.5-3C; Luh & Blank:
    1/3 and 1C; Ohneseit: 1 and 2C), so it is not in the model. BLAST-Lite's own LG M50
    cycling term is not used: it aged faster when warmer and gave about 10x the life at
    3C discharge as at 1C.
    """
    # Fitted by scripts/fit_ageing.py to 24 points (typical error x1.38 in cycles to 80 %).
    # P is fixed at BLAST-Lite's LG M50 value (see the fit script).
    K_BASE, K_PL, N_CH, T_PL, P, B_DOD = (FIT["NMC"][k] for k in
                                          ("K_BASE", "K_PL", "N_CH", "T_PL", "P", "B_DOD"))

    def __init__(self):
        super().__init__()
        self.experimental_range = {"cycling_temperature": [0, 40], "dod": [0.2, 1.0],
                                   "soc": [0, 1], "max_rate_charge": 1.67,
                                   "max_rate_discharge": 3}


class LfpAdjusted(Lfp_Gr_SonyMurata3Ah_Battery):
    """Sony-Murata 3 Ah LFP (BLAST-Lite) with the cycling term multiplied by
    SCALE * max(1, c_ch / C_TH)**M_CH.

    The Sony-Murata cell is an unusually durable high-power cell: the BLAST-Lite model gives
    about 8,000 cycles to 80 % for full cycles at 20 °C and 1C. Ohneseit et al. 2025
    measured about 1,450-1,900 for a commercial 21700 LFP cell under that test (same lab,
    protocol and cell format as the NMC data), so SCALE is fitted to about 1,600.

    Fast charging: Severson et al. 2019 charged A123 LFP cells (30 °C) at 3.6-8C; life fell
    steeply with charge rate. Preger et al. 2020 cycled the same A123 cell with 0.5C
    charging. Together they set C_TH, the charge rate above which life starts to fall, and
    M_CH, how fast it falls. No data exist between 0.5 and 3.6C for this cell, and none
    for fast charging below 30 °C.
    """
    SCALE, C_TH, M_CH = FIT["LFP"]["SCALE"], FIT["LFP"]["C_TH"], FIT["LFP"]["M_CH"]

    def __init__(self):
        super().__init__()
        self.experimental_range = dict(self.experimental_range, max_rate_charge=6)


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
    "NMC": NmcRefit,
    "LFP": LfpAdjusted,
    "NCA": NcaRefit,
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
    with np.errstate(over="ignore"):       # exp overflows to inf for large x: limit is y_inf
        return 2 * y_inf * (0.5 - 1 / (1 + np.exp((k * x) ** p)))


def cycles_to(q, level):
    """First cycle (1-based) whose capacity fraction q is below level; inf if never.
    NaN (below the ageing data) counts as below. The one definition used everywhere."""
    below = np.flatnonzero(~(np.asarray(q, dtype=float) >= level))
    return float(below[0] + 1) if len(below) else float("inf")


def cut_at_data_end(q):
    """Capacity fractions below MIN_SOH become NaN: the ageing data end there."""
    q = np.asarray(q, dtype=float)
    return np.where(q >= MIN_SOH / 100, q, np.nan)


def depth_and_discharge_rate(t_secs, soc):
    """Depth of discharge (0-1) and mean discharge C-rate of one cycle."""
    t_secs = np.asarray(t_secs, dtype=float)
    soc = np.asarray(soc, dtype=float)
    dod = float(soc.max() - soc.min())
    d_soc = np.diff(soc)
    d_hours = np.diff(t_secs) / 3600
    falling = d_soc < 0
    if not falling.any():
        return dod, 0.0
    return dod, float(-d_soc[falling].sum() / d_hours[falling].sum())


def charge_conditions(t_secs, soc, temp_c):
    """Mean charge C-rate (weighted by charge, so a CV tail counts little) and mean cell
    temperature while charging."""
    t_secs = np.asarray(t_secs, dtype=float)
    soc = np.asarray(soc, dtype=float)
    temp_c = np.asarray(temp_c, dtype=float)
    d_soc = np.diff(soc)
    d_hours = np.diff(t_secs) / 3600
    rising = (d_soc > 0) & (d_hours > 0)
    if not rising.any():
        return 0.0, float(temp_c.mean())
    rate = d_soc[rising] / d_hours[rising]
    c_ch = float(np.sum(rate * d_soc[rising]) / np.sum(d_soc[rising]))
    t_mid = (temp_c[:-1] + temp_c[1:]) / 2
    t_ch = float(np.sum(t_mid[rising] * d_hours[rising]) / np.sum(d_hours[rising]))
    return c_ch, t_ch


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

    dod, c_dis = depth_and_discharge_rate(t_secs, soc)
    c_ch, t_ch = charge_conditions(t_secs, soc, temp_c)

    if chemistry == "NMC":       # calendar (BLAST-Lite LG M50) + refitted cycling with plating
        c = NmcRefit
        plating = c.K_PL * c_ch ** c.N_CH * np.exp(-(t_ch - 25.0) / c.T_PL)
        k_cyc = dod ** c.B_DOD * (c.K_BASE + plating) if dod > 0 else 0.0
        loss = r["k_cal"] * (t_days / 1e4) ** p["p_cal"] + k_cyc * efc ** c.P
    elif chemistry == "NCA":     # Panasonic NCR18650B: calendar (BLAST-Lite) + refitted cycling
        c = NcaRefit
        k_cyc = c.A * dod ** c.B_DOD * np.clip(c_dis, 0.5, 2.0) ** (-c.C_RATE) if dod > 0 else 0.0
        loss = r["k_cal"] * t_days ** p["qcal_p"] + k_cyc * efc ** c.P
    else:                        # LFP Sony-Murata: sigmoid in time, power law in throughput
        loss = (_sigmoid(t_days, r["q1"], p["q2"], r["q3"])
                + LfpAdjusted.SCALE * max(1.0, c_ch / LfpAdjusted.C_TH) ** LfpAdjusted.M_CH
                * (r["q5"] * efc) ** p["q6"])
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
