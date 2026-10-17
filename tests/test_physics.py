"""Physics model (PyBaMM) sanity checks."""
import json

from battery_twin.chemistry import CHEMISTRIES, run_battery_test, run_simulation
from battery_twin.constants import DATA_DIR


def test_soh_decreases_with_cycles():
    soh = run_simulation("NMC", "SPMe", n_cycles=5)["cycles"]["SOH [%]"].to_numpy()
    assert all(soh[1:] <= soh[:-1])


def test_hotter_means_more_sei():
    cold = run_simulation("NMC", "SPMe", n_cycles=3, ambient_c=15)["cycles"]
    hot = run_simulation("NMC", "SPMe", n_cycles=3, ambient_c=45)["cycles"]
    assert hot["SEI capacity loss [Ah]"].iloc[-1] > cold["SEI capacity loss [Ah]"].iloc[-1]


def test_coulombic_efficiency_not_above_100():
    eff = run_simulation("LFP", "SPMe", n_cycles=3)["efficiency"]
    assert (eff["Coulombic efficiency [%]"] <= 100.5).all()


def test_sodium_runs():
    assert run_simulation("Na-ion", n_cycles=2)["meta"]["cell_capacity_ah"] > 0


def test_nmc_capacity_matches_measured():
    # Kirkaldy et al. 2024: mean C/10 capacity 4.857 Ah
    r = run_simulation("NMC", "SPMe", n_cycles=1)
    assert abs(r["cycles"]["Capacity [Ah]"].iloc[0] - 4.857) < 0.05


def test_nmc_uses_calibration_file():
    # The NMC values must come straight from data/calibration.json, with no hand copying.
    with open(DATA_DIR / "calibration.json") as f:
        cal = json.load(f)
    nmc = CHEMISTRIES["NMC"]["updates"]
    assert nmc["SEI solvent diffusivity [m2.s-1]"] == cal["sei_solvent_diffusivity_m2_s"]
    assert nmc["SEI growth activation energy [J.mol-1]"] == cal["sei_activation_energy_J_mol"]
    assert (nmc["Initial concentration in negative electrode [mol.m-3]"]
            == cal["initial_concentration_negative_mol_m3"])


def test_first_middle_last_windows():
    r = run_battery_test("NMC", n_cycles=1000, aged_windows=True)
    summary = r["windows"]["summary"].set_index("Window")
    assert list(summary.index) == ["First", "Middle", "Last"]
    assert summary.loc["Middle", "Cycles"] == "496–505"
    assert summary.loc["Last", "Cycles"] == "991–1000"
    # the aged cells hold less charge and run warmer (higher resistance)
    cap = summary["Discharge capacity [Ah]"]
    assert cap["First"] > cap["Middle"] > cap["Last"]
    assert summary.loc["Last", "Max temperature [°C]"] > summary.loc["First", "Max temperature [°C]"]
