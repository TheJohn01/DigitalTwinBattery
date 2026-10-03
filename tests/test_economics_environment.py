from battery_twin.chemistry import CHEMISTRIES
from battery_twin.economics import calculate_tea
from battery_twin.environment import calculate_lca


def test_npv_falls_when_capex_rises():
    assert calculate_tea(capex_eur_kwh=200)["NPV [€]"] < calculate_tea(capex_eur_kwh=100)["NPV [€]"]


def test_lca_levelised_carbon_positive():
    for chem in CHEMISTRIES:
        _, ind = calculate_lca(chem, 60)
        assert ind["Levelised carbon [kg CO2eq/MWh delivered]"] > 0
