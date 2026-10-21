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
