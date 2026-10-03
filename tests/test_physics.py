"""Physics model (PyBaMM) sanity checks."""
import json
from pathlib import Path

from battery_twin.chemistry import CHEMISTRIES, run_simulation

DATA = Path(__file__).resolve().parents[1] / "src" / "battery_twin" / "data"


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


def test_calibration_matches_table():
    cal = json.load(open(DATA / "calibration.json"))
    nmc = CHEMISTRIES["NMC"]["updates"]
    assert abs(nmc["SEI solvent diffusivity [m2.s-1]"] / cal["sei_solvent_diffusivity_m2_s"] - 1) < 0.01
    assert abs(nmc["SEI growth activation energy [J.mol-1]"] - cal["sei_activation_energy_J_mol"]) < 100
