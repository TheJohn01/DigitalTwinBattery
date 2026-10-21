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
