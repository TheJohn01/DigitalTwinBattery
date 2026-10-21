"""SOC and SOH estimation from measured current and voltage, as a battery management system
would do it, on the simulated cycles.

SOC: an extended Kalman filter (EKF) with state x = [SOC, V1, R0] (one RC element):
    predict:  SOC <- SOC - I dt / (3600 Q)          (I > 0 = discharge)
              V1  <- a V1 + R1 (1 - a) I,  a = exp(-dt / tau)
    measure:  V = OCV(SOC) + M h - R0 I - V1        (OCV(SOC) known from the new cell)
h is the hysteresis state (Plett 2004, one-state model): it moves towards -1 while
discharging and +1 while charging, within about 1/gamma of the capacity; OCV is the middle
of the charge and discharge curves. OCV, M and gamma are fitted once on the new cell's
simulated open-circuit voltage, R1 and tau on its voltage (least squares); R0 is tracked as
the cell ages. M comes out about 30 mV for LFP and zero for the other cells.
SOH: at the end of every rest the cell has relaxed, so its SOC is read from the OCV curve;
between two rests (full and empty) the capacity Q = Ah moved / SOC change, the median of all
such pairs so far (the field method of Figgener et al. 2024, Nature Energy 9, 1438). The
filter uses that Q from then on. SOH = Q / the new cell's capacity.
The filter starts from a wrong SOC (50 %) and the new cell's capacity and resistance, and
only sees the current and voltage with sensor noise. Plett, J. Power Sources 134 (2004)
252-261 and 277-292, describes the EKF and the RC model.

The "true" SOC used to score it is counted from the simulated current: every cycle starts
fully charged (after the CC-CV charge) and holds the charge it delivers in that cycle's
discharge.
shortcut: one RC element, and M and gamma do not change as the cell ages.
"""
import numpy as np
import pandas as pd

V_NOISE, I_NOISE = 0.005, 0.01      # sensor noise: 5 mV, 1 % of the 1C current
MODEL_ERROR = 0.02                  # V: what the simple measurement model leaves out


def coulomb_soc(t_s, i_a, capacity_ah):
    """SOC from the current, starting full at t_s[0]."""
    q = np.concatenate([[0.0], np.cumsum(0.5 * (i_a[1:] + i_a[:-1]) * np.diff(t_s))]) / 3600
    return 1.0 - q / capacity_ah


def true_soc(series):
    """SOC of a simulated window, cycle by cycle: full at the start of each cycle, empty when
    that cycle's discharge has delivered all its charge."""
    soc = np.empty(len(series))
    for _, rows in series.groupby("Cycle").indices.items():
        t = series["Time [min]"].to_numpy()[rows] * 60
        out = 1.0 - coulomb_soc(t, series["Current [A]"].to_numpy()[rows], 1.0)  # Ah moved
        soc[rows] = 1.0 - out / out.max()
    return soc


def ocv_curve(series, q_ah):
    """Open-circuit voltage of the new cell from one simulated window: (SOC grid, OCV, M,
    gamma), SOC increasing. The simulated OCV = OCV(SOC) + M h: for each gamma of a grid, a
    least-squares fit of the OCV in each 2 % SOC bin and of M; the gamma that fits best."""
    soc = true_soc(series)
    t = series["Time [min]"].to_numpy() * 60
    i = series["Current [A]"].to_numpy()
    ocv = series["Open-circuit voltage [V]"].to_numpy()
    bins = np.digitize(soc.clip(0, 1), np.linspace(0, 1, 51))
    used = np.unique(bins)
    onehot = (bins[:, None] == used[None, :]).astype(float)
    best = None
    for gamma in (10, 30, 100):
        A = np.column_stack([onehot, hysteresis(t, i, q_ah, gamma)])
        x, *_ = np.linalg.lstsq(A, ocv, rcond=None)
        res = float(np.sum((A @ x - ocv) ** 2))
        if best is None or res < best[0]:
            best = (res, x, gamma)
    _, x, gamma = best
    soc_mid = pd.Series(soc).groupby(bins).mean().to_numpy()
    m = max(float(x[-1]), 0.0)
    return soc_mid, x[:-1], m, float(gamma)


def hysteresis(t_s, i_a, q_ah, gamma):
    """Hysteresis state h (-1 after discharging, +1 after charging; I > 0 = discharge),
    starting at 0: it switches within about 1/gamma of the capacity q_ah."""
    h = np.zeros(len(t_s))
    for k in range(1, len(t_s)):
        e = np.exp(-gamma * abs(i_a[k]) * (t_s[k] - t_s[k - 1]) / (3600 * q_ah))
        h[k] = e * h[k - 1] - (1 - e) * np.sign(i_a[k])
    return h


def rc_current(t_s, i_a, tau):
    """Current through the RC element's resistor: I filtered with time constant tau."""
    z = np.zeros(len(t_s))
    for k in range(1, len(t_s)):
        a = np.exp(-(t_s[k] - t_s[k - 1]) / tau)
        z[k] = a * z[k - 1] + (1 - a) * i_a[k]
    return z


def resistance(series, ocv_soc, ocv_v, hyst):
    """(R0, R1, tau) of V = OCV(SOC) + hyst - R0 I - R1 I_rc on the new cell (hyst = M h):
    least squares in R0 and R1 for each tau of a grid, the tau with the smallest residual."""
    t = series["Time [min]"].to_numpy() * 60
    i = series["Current [A]"].to_numpy()
    drop = (np.interp(true_soc(series), ocv_soc, ocv_v) + hyst
            - series["Voltage [V]"].to_numpy())
    best = None
    for tau in (30, 60, 120, 300, 600, 1200, 2400):
        A = np.column_stack([i, rc_current(t, i, tau)])
        (r0, r1), *_ = np.linalg.lstsq(A, drop, rcond=None)
        res = float(np.sum((A @ [r0, r1] - drop) ** 2))
        if r0 > 0 and r1 >= 0 and (best is None or res < best[0]):
            best = (res, float(r0), float(r1), float(tau))
    return best[1:]


def rest_socs(i_meas, v_meas, ocv_soc, ocv_v, q0, hyst=0.0):
    """Last sample of each rest and the SOC read there from the OCV curve (relaxed cell), the
    hysteresis voltage hyst taken off. A relaxed voltage beyond either end of the curve means
    the cell is at that end (the curve comes from voltages under load, which do not reach as
    far as a relaxed full or empty cell)."""
    resting = np.abs(i_meas) < 0.02 * q0
    ends = np.flatnonzero(resting[:-1] & ~resting[1:])
    curve = np.maximum.accumulate(ocv_v)
    v = v_meas[ends]
    soc = np.interp(v - np.broadcast_to(hyst, v_meas.shape)[ends], curve, ocv_soc)
    soc = np.where(v <= curve[0], ocv_soc[0], np.where(v >= curve[-1], ocv_soc[-1], soc))
    return ends, soc


def rest_capacities(t_s, i_meas, v_meas, ocv_soc, ocv_v, q0, hyst=0.0):
    """[(index, Q in Ah)] for each pair of consecutive rests more than 50 % SOC apart."""
    ends, soc = rest_socs(i_meas, v_meas, ocv_soc, ocv_v, q0, hyst)
    out = []
    for (a, sa), (b, sb) in zip(zip(ends, soc), zip(ends[1:], soc[1:])):
        ah = np.sum(0.5 * (i_meas[a:b] + i_meas[a + 1:b + 1]) * np.diff(t_s[a:b + 1])) / 3600
        if abs(sa - sb) > 0.5:
            out.append((b, abs(ah / (sa - sb))))
    return out


def ekf(t_s, i_meas, v_meas, ocv_soc, ocv_v, q0, r0, r1=0.0, tau=60.0, soc0=0.5,
        m_hyst=0.0, gamma=30.0):
    """Run the filter; returns arrays of SOC, capacity Q [Ah] and R0 [Ohm] after each sample."""
    hyst = m_hyst * hysteresis(t_s, i_meas, q0, gamma)
    found = rest_capacities(t_s, i_meas, v_meas, ocv_soc, ocv_v, q0, hyst)
    q_at = np.full(len(t_s), q0)
    for n, (k, _) in enumerate(found):
        q_at[k:] = np.median([q for _, q in found[:n + 1]])
    x = np.array([soc0, 0.0, r0])
    P = np.diag([0.3 ** 2, (r1 * q0) ** 2, r0 ** 2])
    slope = np.gradient(ocv_v, ocv_soc)
    out = np.zeros((len(t_s), 3))
    out[0] = [x[0], q0, x[2]]
    for k in range(1, len(t_s)):
        dt, i, q = t_s[k] - t_s[k - 1], i_meas[k], q_at[k]
        a = np.exp(-dt / tau)
        x[0] -= 0.5 * (i + i_meas[k - 1]) * dt / (3600 * q)   # predict
        x[1] = a * x[1] + r1 * (1 - a) * i
        F = np.diag([1.0, a, 1.0])
        P = F @ P @ F.T + np.diag([(I_NOISE * q0 * dt / 3600 / q) ** 2,
                                   (0.1 * r1 * I_NOISE * q0) ** 2, (1e-3 * r0) ** 2])
        s = np.clip(x[0], ocv_soc[0], ocv_soc[-1])           # update with the voltage
        H = np.array([np.interp(s, ocv_soc, slope), -1.0, -i])
        y = v_meas[k] - (np.interp(s, ocv_soc, ocv_v) + hyst[k] - x[2] * i - x[1])
        K = P @ H / (H @ P @ H + V_NOISE ** 2 + MODEL_ERROR ** 2)
        x = x + K * y
        x[0] = np.clip(x[0], 0.0, 1.0)                     # SOC is physically bounded
        P = (np.eye(3) - np.outer(K, H)) @ P
        out[k] = [x[0], q, x[2]]
    return out[:, 0], out[:, 1], out[:, 2]


def estimate(window, new_window, capacity_ah, new_capacity_ah, seed=0):
    """Estimate SOC and SOH on one simulated window (DataFrame with Time [min], Current [A],
    Voltage [V], Open-circuit voltage [V]); the OCV curve and the starting capacity and
    resistance come from the new cell's window. Returns (DataFrame, summary dict)."""
    ocv_soc, ocv_v, m_hyst, gamma = ocv_curve(new_window, new_capacity_ah)
    t_new = new_window["Time [min]"].to_numpy() * 60
    hyst_new = m_hyst * hysteresis(t_new, new_window["Current [A]"].to_numpy(),
                                   new_capacity_ah, gamma)
    r0, r1, tau = resistance(new_window, ocv_soc, ocv_v, hyst_new)
    rng = np.random.default_rng(seed)
    t = window["Time [min]"].to_numpy() * 60
    t = t - t[0]
    i = window["Current [A]"].to_numpy()
    v = window["Voltage [V]"].to_numpy()
    i_meas = i + rng.normal(0, I_NOISE * new_capacity_ah, len(i))
    v_meas = v + rng.normal(0, V_NOISE, len(v))
    soc, q, r = ekf(t, i_meas, v_meas, ocv_soc, ocv_v, new_capacity_ah, r0, r1, tau,
                    m_hyst=m_hyst, gamma=gamma)
    true = true_soc(window)
    df = pd.DataFrame({"Time [h]": t / 3600, "True SOC [%]": 100 * true,
                       "Estimated SOC [%]": 100 * soc,
                       "Estimated SOH [%]": 100 * q / new_capacity_ah})
    half = t >= t[-1] / 2                       # second half: after the filter has settled
    last = window["Cycle"].to_numpy() >= window["Cycle"].max() - 2
    summary = {"SOC error, second half (RMS) [%-points]":
               float(np.sqrt(np.mean((100 * (soc - true)[half]) ** 2))),
               "SOC error, last 3 cycles (RMS) [%-points]":
               float(np.sqrt(np.mean((100 * (soc - true)[last]) ** 2))),
               "Estimated SOH [%]": float(100 * q[-1] / new_capacity_ah),
               "True SOH [%]": float(100 * capacity_ah / new_capacity_ah),
               "Estimated resistance / new": float(r[-1] / r0)}
    return df, summary
