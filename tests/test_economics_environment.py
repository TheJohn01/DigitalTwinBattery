import numpy as np

from battery_twin.chemistry import CHEMISTRIES
from battery_twin.economics import calculate_tea, second_life
from battery_twin.environment import calculate_lca

NEW_FOREVER = np.ones(20000)                    # a battery that never ages


def linear_fade(per_cycle):
    """Capacity curve losing per_cycle each cycle, cut at 50 % like the dashboard."""
    q = 1 - per_cycle * np.arange(1, 20001)
    return np.where(q >= 0.5, q, np.nan)


def test_npv_falls_when_capex_rises():
    assert (calculate_tea(NEW_FOREVER, capex_eur_kwh=200)["NPV [€]"]
            < calculate_tea(NEW_FOREVER, capex_eur_kwh=100)["NPV [€]"])


def test_battery_without_ageing_is_never_retired():
    assert calculate_tea(NEW_FOREVER)["Retired in year"] is None


def test_worn_out_battery_has_no_costs_after_retirement():
    # 0.1 %/cycle at 365 cycles/year: 50 % is reached in year 2 (cycle 501). Afterwards the
    # cash flow must be zero, not "operating costs of a dead battery".
    r = calculate_tea(linear_fade(0.001), years=15)
    assert r["Retired in year"] == 2
    r_short = calculate_tea(linear_fade(0.001), years=3)
    assert abs(r["NPV [€]"] - r_short["NPV [€]"]) < 1e-6


def test_slower_fade_gives_higher_npv():
    assert (calculate_tea(linear_fade(0.0001))["NPV [€]"]
            > calculate_tea(linear_fade(0.001))["NPV [€]"])


def test_second_life_starts_at_the_right_capacity():
    sl = second_life({"soh_curve": linear_fade(0.0001)}, 1000, 20.0, 8)
    assert abs(sl["SOH at start [%]"] - 90.0) < 1e-9


def test_lca_levelised_carbon_positive():
    for chem in CHEMISTRIES:
        _, ind = calculate_lca(chem, 60)
        assert ind["Levelised carbon [kg CO2eq/MWh delivered]"] > 0


def test_npv_is_always_a_number():
    # Even a curve that ends immediately (all NaN) must give a finite NPV.
    for curve in [linear_fade(0.001), linear_fade(0.01), np.full(20000, np.nan)]:
        assert np.isfinite(calculate_tea(curve)["NPV [€]"])


def test_total_energy_follows_cfb_rules():
    import numpy as np
    from battery_twin.environment import total_energy_kwh
    q = np.linspace(1.0, 0.5, 1001)               # loses 0.05 % per cycle
    energy, n = total_energy_kwh(10, q, eol_soh=0.7)
    assert n == 601                                # cycle 602 is the first below 70 %
    assert abs(energy - 10 * q[:601].sum()) < 1e-9
    # service-life cap: 1 year at 365 cycles/year
    assert total_energy_kwh(10, q, 0.7, service_years=1, cycles_per_year=365)[1] == 365


def test_lca_uses_degen_data_and_reports_water_and_ecotox():
    from battery_twin.environment import calculate_lca
    phases, ind = calculate_lca("LFP", 10, throughput_kwh=10000)
    prod = phases.iloc[0]
    assert abs(prod["Emissions [kg CO2eq]"] - 10 * 58.5) < 1e-6
    assert abs(prod["Water consumption [m3]"] - 10 * 0.91) < 1e-6
    assert abs(prod["Freshwater ecotoxicity [kg 1,4-DCB eq]"] - 10 * 16.0) < 1e-6
    assert ind["Water consumption [L/kWh delivered]"] > 0


def test_lca_report_pdf():
    import numpy as np
    from battery_twin.lca_report import STATEMENT, build_lca_report
    run = dict(c_charge=0.3, c_discharge=1.0, ambient_c=20, cycling_c=20,
               cooling="Forced air / passive", h=25, mean_cell_temp=22, cell_capacity_ah=4.6,
               cell_energy_wh=16.9, cycles_per_year=365, model="SPMe", n_cycles=1000,
               cycles_to_80=374)
    args = dict(eol_soh=0.7, service_years=15, cycles_per_year=365, round_trip_eff=0.9,
                grid_g_co2_per_kwh=210, lifetime_km=200000, kwh_per_km=0.16)
    for chem in ["NMC", "LFP", "NCA", "Na-ion"]:
        pdf = build_lca_report(chem, 60, np.linspace(1, 0.5, 5000), "stationary", run, args)
        assert pdf.startswith(b"%PDF") and len(pdf) > 5000
    assert "not critically reviewed" in STATEMENT
