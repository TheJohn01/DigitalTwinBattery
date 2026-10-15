"""Cooling options: h values, pre-conditioning and their effect on the cell temperature."""
from battery_twin.chemistry import (COOLING_OPTIONS, PRECONDITION_C, cooling_conditions,
                                    run_battery_test)


def test_options_and_preconditioning():
    assert set(COOLING_OPTIONS) == {"Forced air / passive", "Liquid cold plate", "Immersion cooling"}
    assert cooling_conditions("Forced air / passive", 5) == (25.0, 5.0)
    assert cooling_conditions("Liquid cold plate", 5) == (100.0, PRECONDITION_C)
    assert cooling_conditions("Immersion cooling", 40) == (300.0, PRECONDITION_C)
    assert all(o["warning"] for o in COOLING_OPTIONS.values())


def test_preconditioning_keeps_cold_nmc_alive_longer():
    # At 5 °C ambient and 1.5C charging, an air-cooled NMC cell charges cold and plates
    # lithium; a pre-conditioned (liquid-cooled) pack charges at 25 °C.
    runs = {}
    for name in ("Forced air / passive", "Liquid cold plate"):
        h, cycling_c = cooling_conditions(name, 5)
        runs[name] = run_battery_test("NMC", c_charge=1.5, ambient_c=5, h_cooling=h,
                                      cycling_c=cycling_c)["meta"]
    assert runs["Liquid cold plate"]["mean_cell_temperature_c"] > 20
    assert runs["Liquid cold plate"]["cycles_to_80pct"] > runs["Forced air / passive"]["cycles_to_80pct"]
