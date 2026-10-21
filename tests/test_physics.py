"""Physics model (PyBaMM) sanity checks."""
import json

from battery_twin.chemistry import CHEMISTRIES, build_model, run_battery_test, run_simulation
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


def test_nca_is_the_commercial_cell():
    # Samsung INR21700-50E: 4.9 Ah nominal, about 4.7 Ah measured at 1C and 25 °C (Schmitt et
    # al. 2023); the old lab pouch cell gave 0.47 Ah and 98.4 % efficiency.
    r = run_simulation("NCA", "SPMe", c_charge=0.3, c_discharge=1.0, n_cycles=2, h_cooling=10)
    assert 4.5 < r["meta"]["cell_capacity_ah"] < 4.9
    assert 85 < r["efficiency"]["Energy efficiency [%]"].iloc[-1] < 95


def test_lfp_is_the_commercial_cell():
    # BYD Blade: 135 Ah at C/10 (Gorsch et al. 2025); the electrode balance sets the
    # thermodynamic capacity to 135 Ah. The old A123 26650 gave about 2 Ah.
    r = run_simulation("LFP", "SPMe", c_charge=0.3, c_discharge=1.0, n_cycles=2, h_cooling=25)
    assert abs(r["cycles"]["Capacity [Ah]"].iloc[0] - 135.0) < 1.0
    assert 115 < r["meta"]["cell_capacity_ah"] < 135          # 1C discharge
    # the Blade's measured 1C resistance (about 1 mOhm, Gorsch Fig. 8C) and the LFP
    # hysteresis make it about 91.5 % efficient on this cycle
    assert 89 < r["efficiency"]["Energy efficiency [%]"].iloc[-1] < 94


def test_lfp_pulse_resistance_in_measured_range():
    # BYD 4680 LFP (Liu et al. 2025): 10 s 1C pulses, 6-17 Ohm cm2 between 80 and 20 % SOC
    import pybamm
    from battery_twin import lfp_blade_params as blade
    pv = pybamm.ParameterValues(blade.get_parameter_values("BYD4680"))
    donor = pybamm.ParameterValues("Chen2020")
    have = set(pv.keys())
    pv.update({k: donor[k] for k in donor.keys() if k not in have}, check_already_exists=False)
    model = pybamm.lithium_ion.SPMe({"thermal": "lumped", **blade.MODEL_OPTIONS})
    steps = ("Discharge at C/2 for 60 minutes", "Rest for 1 hour", "Discharge at 1C for 10 seconds")
    sol = pybamm.Simulation(model, parameter_values=pv,
                            experiment=pybamm.Experiment([steps])).solve(initial_soc=1.0)
    rest, pulse = sol.cycles[0].steps[1], sol.cycles[0].steps[2]
    r = (rest["Voltage [V]"].entries[-1] - pulse["Voltage [V]"].entries[-1]) / 15.41
    asr = r * blade.electrode_fractions("BYD4680")[0] * 1e4
    assert 6 < asr < 17


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


def test_a_run_that_stops_early_is_an_error(monkeypatch):
    # PyBaMM returns the cycles it solved when the solver fails mid-run (NCA at 4C, 5 °C ran
    # out of memory after 3 of 10). Simulate that with one cycle fewer than asked.
    import pytest
    from battery_twin import chemistry
    full = chemistry.build_experiment
    monkeypatch.setattr(chemistry, "build_experiment",
                        lambda chem, cc, cd, n: full(chem, cc, cd, n - 1))
    with pytest.raises(RuntimeError, match="stopped after 1 of 2 cycles"):
        chemistry.run_simulation("NMC", "SPMe", n_cycles=2)


def test_a_discharge_the_model_cannot_follow_is_an_error():
    # The NCA set reaches 2.5 V after about 0.15 Ah at 3C (the cell delivers most of its
    # 4.9 Ah). Without this error the pack would be sized on 0.15 Ah cells.
    import pytest
    with pytest.raises(RuntimeError, match="lower voltage limit"):
        run_simulation("NCA", "SPMe", c_charge=0.3, c_discharge=3.0, n_cycles=2)


def test_nmc_discharges_at_3c_like_the_real_cell():
    # Catenaro & Onori (2021): the LG M50 delivers 4.45 Ah at 3C in a 25 °C chamber. Before
    # the electrolyte factor (fit_electrolyte.py) the model stopped after 0.25 Ah.
    r = run_simulation("NMC", "SPMe", c_charge=0.3, c_discharge=3.0, n_cycles=2, ambient_c=25.0)
    assert abs(r["meta"]["cell_capacity_ah"] - 4.45) < 0.2


def test_nmc_core_is_warmer_than_its_can_and_detailed_model_plates():
    import pybamm
    model, pv, _ = build_model("NMC", "DFN", 0.0, 25.0)
    sol = pybamm.Simulation(model, parameter_values=pv, experiment=pybamm.Experiment(
        ["Charge at 1C until 4.2 V"])).solve(initial_soc=0)
    core = sol["Volume-averaged cell temperature [K]"].entries[-1]
    can = sol["Surface temperature [K]"].entries[-1]
    assert core > can > 273.15
    assert sol["Loss of capacity to negative lithium plating [A.h]"].entries[-1] > 0
