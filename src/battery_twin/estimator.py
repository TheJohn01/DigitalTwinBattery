"""SOC and SOH estimation from measured current and voltage, as a battery management system
would do it, on the simulated cycles.

SOC: an extended Kalman filter (EKF) with state x = [SOC, R]:
    predict:  SOC <- SOC - I dt / (3600 Q)          (I > 0 = discharge; R constant)
    measure:  V = OCV(SOC) - R I                    (OCV(SOC) known from the new cell)
SOH: at the end of every rest the cell has relaxed, so its SOC is read from the OCV curve;
between two rests (full and empty) the capacity Q = Ah moved / SOC change, the median of all
such pairs so far (the field method of Figgener et al. 2024, Nature Energy 9, 1438). The
filter uses that Q from then on. SOH = Q / the new cell's capacity.
The filter starts from a wrong SOC (50 %) and the new cell's capacity and resistance, and
only sees the current and voltage with sensor noise. Plett, J. Power Sources 134 (2004)
252-261 and 277-292, describes the EKF (here with a resistance instead of RC elements).

The "true" SOC used to score it is counted from the simulated current: every cycle starts
fully charged (after the CC-CV charge) and holds the cell's discharge capacity at the test
rate.
shortcut: no RC elements and no hysteresis in the filter's model; upgrade if the SOC error
during a step must be smaller than the few % it shows now.
"""
import numpy as np
import pandas as pd

V_NOISE, I_NOISE = 0.005, 0.01      # sensor noise: 5 mV, 1 % of the 1C current
MODEL_ERROR = 0.02                  # V: what the simple measurement model leaves out


def coulomb_soc(t_s, i_a, capacity_ah):
    """SOC from the current, starting full at t_s[0]."""
    q = np.concatenate([[0.0], np.cumsum(0.5 * (i_a[1:] + i_a[:-1]) * np.diff(t_s))]) / 3600
    return 1.0 - q / capacity_ah


def ocv_curve(series, capacity_ah):
    """OCV against SOC from one simulated window: (SOC grid, OCV), SOC increasing."""
    t = series["Time [min]"].to_numpy() * 60
    soc = coulomb_soc(t, series["Current [A]"].to_numpy(), capacity_ah)
    bins = np.linspace(0, 1, 51)
    frame = pd.DataFrame({"soc": soc, "ocv": series["Open-circuit voltage [V]"].to_numpy()})
    mean = frame.groupby(np.digitize(frame.soc.clip(0, 1), bins)).mean()
    return mean.soc.to_numpy(), mean.ocv.to_numpy()


def resistance(series, capacity_ah, ocv_soc, ocv_v):
    """Least-squares R in V = OCV(SOC) - R I (the new cell's value, the filter's start)."""
    t = series["Time [min]"].to_numpy() * 60
    i = series["Current [A]"].to_numpy()
    soc = coulomb_soc(t, i, capacity_ah)
    drop = np.interp(soc, ocv_soc, ocv_v) - series["Voltage [V]"].to_numpy()
    return float(np.sum(drop * i) / np.sum(i * i))


def rest_capacities(t_s, i_meas, v_meas, ocv_soc, ocv_v, q0):
    """[(index, Q in Ah)] for each pair of consecutive rests more than 50 % SOC apart."""
    resting = np.abs(i_meas) < 0.02 * q0
    ends = np.flatnonzero(resting[:-1] & ~resting[1:])          # last sample of each rest
    soc = np.interp(v_meas[ends], np.maximum.accumulate(ocv_v), ocv_soc)
    out = []
    for (a, sa), (b, sb) in zip(zip(ends, soc), zip(ends[1:], soc[1:])):
        ah = np.sum(0.5 * (i_meas[a:b] + i_meas[a + 1:b + 1]) * np.diff(t_s[a:b + 1])) / 3600
        if abs(sa - sb) > 0.5:
            out.append((b, abs(ah / (sa - sb))))
    return out


def ekf(t_s, i_meas, v_meas, ocv_soc, ocv_v, q0, r0, soc0=0.5):
    """Run the filter; returns arrays of SOC, capacity Q [Ah] and R [Ohm] after each sample."""
    found = rest_capacities(t_s, i_meas, v_meas, ocv_soc, ocv_v, q0)
    q_at = np.full(len(t_s), q0)
    for n, (k, _) in enumerate(found):
        q_at[k:] = np.median([q for _, q in found[:n + 1]])
    x = np.array([soc0, r0])
    P = np.diag([0.3 ** 2, r0 ** 2])
    slope = np.gradient(ocv_v, ocv_soc)
    out = np.zeros((len(t_s), 3))
    out[0] = [x[0], q0, x[1]]
    for k in range(1, len(t_s)):
        dt, i, q = t_s[k] - t_s[k - 1], i_meas[k], q_at[k]
        x[0] -= 0.5 * (i + i_meas[k - 1]) * dt / (3600 * q)   # predict
        P = P + np.diag([(I_NOISE * q0 * dt / 3600 / q) ** 2, (1e-3 * r0) ** 2])
        s = np.clip(x[0], ocv_soc[0], ocv_soc[-1])           # update with the voltage
        H = np.array([np.interp(s, ocv_soc, slope), -i])
        y = v_meas[k] - (np.interp(s, ocv_soc, ocv_v) - x[1] * i)
        K = P @ H / (H @ P @ H + V_NOISE ** 2 + MODEL_ERROR ** 2)
        x = x + K * y
        P = (np.eye(2) - np.outer(K, H)) @ P
        out[k] = [x[0], q, x[1]]
    return out[:, 0], out[:, 1], out[:, 2]


def estimate(window, new_window, capacity_ah, new_capacity_ah, seed=0):
    """Estimate SOC and SOH on one simulated window (DataFrame with Time [min], Current [A],
    Voltage [V], Open-circuit voltage [V]); the OCV curve and the starting capacity and
    resistance come from the new cell's window. Returns (DataFrame, summary dict)."""
    ocv_soc, ocv_v = ocv_curve(new_window, new_capacity_ah)
    r0 = resistance(new_window, new_capacity_ah, ocv_soc, ocv_v)
    rng = np.random.default_rng(seed)
    t = window["Time [min]"].to_numpy() * 60
    t = t - t[0]
    i = window["Current [A]"].to_numpy()
    v = window["Voltage [V]"].to_numpy()
    i_meas = i + rng.normal(0, I_NOISE * new_capacity_ah, len(i))
    v_meas = v + rng.normal(0, V_NOISE, len(v))
    soc, q, r = ekf(t, i_meas, v_meas, ocv_soc, ocv_v, new_capacity_ah, r0)
    true_soc = coulomb_soc(t, i, capacity_ah)
    df = pd.DataFrame({"Time [h]": t / 3600, "True SOC [%]": 100 * true_soc,
                       "Estimated SOC [%]": 100 * soc,
                       "Estimated SOH [%]": 100 * q / new_capacity_ah})
    half = t >= t[-1] / 2                       # second half: after the filter has settled
    summary = {"SOC error, second half (RMS) [%-points]":
               float(np.sqrt(np.mean((100 * (soc - true_soc)[half]) ** 2))),
               "Estimated SOH [%]": float(100 * q[-1] / new_capacity_ah),
               "True SOH [%]": float(100 * capacity_ah / new_capacity_ah),
               "Estimated resistance / new": float(r[-1] / r0)}
    return df, summary
