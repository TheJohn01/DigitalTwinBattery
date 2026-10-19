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


def test_sodium_is_the_commercial_cell():
    # Mushang NA18650-1250: 1.25 Ah nominal, about 1.10 Ah measured at 1C (Schneider et al.
    # 2025); round-trip efficiency 89-92 % measured at 1C (Rehm et al. 2025), the model is
    # about 2 points higher (no hysteresis). The cell heats up (thermal model).
    r = run_simulation("Na-ion", "DFN", c_charge=0.3, c_discharge=1.0, n_cycles=2, h_cooling=10)
    assert 1.05 < r["meta"]["cell_capacity_ah"] < 1.15
    assert 90 < r["efficiency"]["Energy efficiency [%]"].iloc[-1] < 97
    assert r["cycles"]["Max temperature [°C]"].iloc[-1] > 26


def test_sodium_warmer_cell_is_more_efficient():
    # Arrhenius kinetics and diffusion (Schneider et al. 2025): losses fall with temperature
    eff = [run_simulation("Na-ion", "DFN", 1.0, 1.0, n_cycles=1, ambient_c=t, h_cooling=300)
           ["efficiency"]["Energy efficiency [%]"].iloc[-1] for t in (15, 35)]
    assert eff[1] > eff[0]


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
