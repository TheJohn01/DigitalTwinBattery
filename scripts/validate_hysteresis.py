"""Does the hysteresis term help the SOC filter? A simulated LFP (BYD Blade) cell on partial
cycles, where LFP's charge and discharge voltage curves differ most for the same SOC.

As in the dashboard (estimator.estimate), the filter learns the open-circuit voltage curve,
the hysteresis (M, gamma) and the resistance from the new cell's normal 10-cycle window
(0.3C charge, 1C discharge, 25 °C). It then follows a different, partial-cycle profile,
repeated three times from full: 1C discharge to 40 %, 0.5C charge to 70 %, 1C discharge to
40 %, 0.5C charge to full, each followed by a 1-hour rest. It starts from a wrong 50 % and
sees the current and voltage with sensor noise; it is run with the fitted M and with M = 0.
Truth: the charge counted from full, over the new cell's 1C capacity.

Run:  python scripts/validate_hysteresis.py      (about 2 minutes)
"""
import numpy as np
import pybamm

from battery_twin.chemistry import CALIBRATED_H_COOLING, build_model, run_simulation
from battery_twin.estimator import (I_NOISE, V_NOISE, coulomb_soc, ekf, hysteresis, ocv_curve,
                                    resistance)

LOOP = ["Discharge at 1C for 36 minutes", "Rest for 1 hour",
        "Charge at 0.5C for 36 minutes", "Rest for 1 hour",
        "Discharge at 1C for 18 minutes", "Rest for 1 hour",
        "Charge at 0.5C for 72 minutes or until 3.65 V", "Rest for 1 hour"]


def partial_cycles(h):
    model, pv, _ = build_model("LFP", "SPMe", 25.0, h)
    sim = pybamm.Simulation(model, parameter_values=pv, experiment=pybamm.Experiment(LOOP * 3,
                                                                                    period="1 minute"))
    sol = sim.solve(initial_soc=1.0)
    return sol["Time [s]"].entries, sol["Current [A]"].entries, sol["Voltage [V]"].entries


def main(seed=0):
    new = run_simulation("LFP", "SPMe", 0.3, 1.0, 10, 25.0, CALIBRATED_H_COOLING)
    window, q_new = new["series"], float(new["efficiency"]["Discharge [Ah]"].mean())
    ocv_soc, ocv_v, m, gamma = ocv_curve(window, q_new)
    t_new = window["Time [min]"].to_numpy() * 60
    hyst_new = m * hysteresis(t_new, window["Current [A]"].to_numpy(), q_new, gamma)
    t, i, v = partial_cycles(CALIBRATED_H_COOLING)
    truth = coulomb_soc(t, i, q_new)
    rng = np.random.default_rng(seed)
    i_meas = i + rng.normal(0, I_NOISE * q_new, len(i))
    v_meas = v + rng.normal(0, V_NOISE, len(v))
    settled = t > 6 * 3600                          # after the first loop
    resting = np.abs(i) < 1e-3 * q_new
    out = {}
    for label, m_used, hyst in (("with hysteresis", m, hyst_new), ("without", 0.0, 0 * hyst_new)):
        r0, r1, tau = resistance(window, ocv_soc, ocv_v, hyst)
        soc, _, _ = ekf(t, i_meas, v_meas, ocv_soc, ocv_v, q_new, r0, r1, tau,
                        m_hyst=m_used, gamma=gamma)
        err = 100 * (soc - truth)
        out[label] = (float(np.sqrt(np.mean(err[settled] ** 2))),
                      float(np.abs(err[settled]).max()),
                      float(np.sqrt(np.mean(err[settled & resting] ** 2))))
    print(f"Fitted on the new cell: M = {1000 * m:.1f} mV, gamma = {gamma:g}")
    print("SOC error after the first loop [%-points]: RMS, largest, RMS during rests")
    for label, (rms, worst, rest) in out.items():
        print(f"  {label:16} {rms:5.2f} {worst:6.2f} {rest:6.2f}")
    return m, out


if __name__ == "__main__":
    main()
