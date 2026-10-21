"""SOC and SOH estimation on the simulated cycles."""
from battery_twin.chemistry import run_battery_test
from battery_twin.estimator import estimate


def test_estimator_tracks_soc_and_finds_the_aged_capacity():
    r = run_battery_test("NMC", n_cycles=1000, aged_windows=True)
    win, summ = r["windows"]["series"], r["windows"]["summary"].set_index("Window")
    first = win[win["Window"].str.startswith("First")]
    q_new = summ.loc["First", "Discharge capacity [Ah]"]
    for name in ("First", "Middle"):
        _, res = estimate(win[win["Window"].str.startswith(name)], first,
                          summ.loc[name, "Discharge capacity [Ah]"], q_new)
        # starts 50 points off and with the new cell's capacity; settles within a few points
        assert res["SOC error, last 3 cycles (RMS) [%-points]"] < 3
        assert abs(res["Estimated SOH [%]"] - res["True SOH [%]"]) < 3


def test_estimator_on_a_real_car():
    # TUM Tesla Model 3 (LFP), 2025 charge after 80,100 km: the filter starts at a wrong 50 %
    # and assumes the 2021 capacity (9 % too high), yet ends within a few points.
    import runpy
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_estimator_tesla.py"
    res = runpy.run_path(str(script))["evaluate"]()[2025]
    assert res["SOC error RMS [%-points]"] < 4
    assert abs(res["SOC error at full [%-points]"]) < 1
    assert res["counting with the 2021 capacity, error at full [%-points]"] < -8
    assert abs(res["capacity from voltage to full [Ah]"] / res["capacity [Ah]"] - 1) < 0.03


def test_hysteresis_is_found_in_the_open_circuit_voltage():
    # LFP-like window: OCV = 3.2 V + 0.2 V x SOC + 30 mV x h, three 1C discharges and 0.5C
    # charges; the fit must recover the 30 mV and the switching rate.
    import numpy as np
    import pandas as pd
    from battery_twin.estimator import hysteresis, ocv_curve
    q = 10.0
    i = np.tile(np.r_[np.full(60, 10.0), np.full(120, -5.0)], 3)
    t = 60.0 * np.arange(len(i))
    cycle = np.repeat([1, 2, 3], 180)
    soc = np.concatenate([1 - np.r_[np.arange(1, 61) / 60, 1 - np.arange(1, 121) / 120]] * 3)
    ocv = 3.2 + 0.2 * soc + 0.03 * hysteresis(t, i, q, 30)
    window = pd.DataFrame({"Time [min]": t / 60, "Current [A]": i, "Cycle": cycle,
                           "Open-circuit voltage [V]": ocv})
    _, _, m, gamma = ocv_curve(window, q)
    assert abs(m - 0.03) < 0.003 and gamma == 30


def test_hysteresis_term_helps_on_partial_lfp_cycles():
    # Simulated BYD Blade on partial cycles with rests at 40-70 % SOC (validate_hysteresis.py):
    # the filter with the fitted hysteresis must be far closer to the truth than without.
    import runpy
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_hysteresis.py"
    m, out = runpy.run_path(str(script))["main"]()
    assert 0.025 < m < 0.037                          # the model's 31.4 mV
    assert out["with hysteresis"][0] < 0.5 * out["without"][0]


def test_estimator_on_a_home_storage_system():
    # Figgener et al. 2024, system 10 (NMC), April-December 2022: from a wrong 50 % the filter
    # follows each day within a few points, and the rest-to-rest capacity agrees with the
    # capacity counted from empty to full.
    import runpy
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_estimator_storage.py"
    res, monthly = runpy.run_path(str(script))["evaluate"]()
    assert res["test days"] > 50
    assert res["SOC error after the first full charge, RMS, median of days [%-points]"] < 4
    assert abs(res["rest-to-rest capacity, median [Ah]"]
               / res["counted capacity, median of test days [Ah]"] - 1) < 0.05
