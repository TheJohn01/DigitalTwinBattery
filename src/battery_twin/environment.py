"""Screening life cycle assessment (cradle-to-grave CO2eq) of a battery pack.

This is a screening model with indicative factors, not an ISO 14040 study.
"""
import pandas as pd

from .chemistry import CHEMISTRIES


def lifetime_throughput_kwh(capacity_kwh, vehicle, lifetime_km=200000, kwh_per_km=0.16,
                            lifetime_cycles=3000, dod=0.80):
    """Energy delivered by the battery over its life [kWh]."""
    if vehicle:
        return lifetime_km * kwh_per_km
    return capacity_kwh * dod * lifetime_cycles


def calculate_lca(chemistry, capacity_kwh, vehicle=True, lifetime_km=200000,
                  kwh_per_km=0.16, lifetime_cycles=3000, dod=0.80,
                  round_trip_eff=0.90, grid_g_co2_per_kwh=210.0):
    c = CHEMISTRIES[chemistry]
    mass_kg = capacity_kwh * 1000.0 / c["wh_per_kg"]

    # Production factor is cradle-to-gate and already includes raw materials,
    # so materials are not counted a second time.
    production = capacity_kwh * c["co2_kg_per_kwh"]

    # Use phase: only the battery's own losses are attributed to it,
    # not the electricity that drives the vehicle.
    throughput = lifetime_throughput_kwh(capacity_kwh, vehicle, lifetime_km,
                                         kwh_per_km, lifetime_cycles, dod)
    losses_kwh = throughput * (1.0 / round_trip_eff - 1.0)
    use = losses_kwh * grid_g_co2_per_kwh / 1000.0

    end_of_life = -mass_kg * c["eol_credit_kg_per_kg"]
    total = production + use + end_of_life

    phases = pd.DataFrame({
        "Phase": ["Production (cradle-to-gate)", "Use (battery losses)",
                  "End of life (recycling credit)", "TOTAL"],
        "Emissions [kg CO2eq]": [production, use, end_of_life, total],
    })
    indicators = {
        "Pack mass [kg]": mass_kg,
        "Lifetime energy delivered [MWh]": throughput / 1000.0,
        "Footprint per kWh capacity [kg CO2eq/kWh]": total / capacity_kwh,
        "Levelised carbon [kg CO2eq/MWh delivered]": total / (throughput / 1000.0),
        "Water (screening) [L]": capacity_kwh * c["water_l_per_kwh"],
        "Ecotoxicity (screening) [relative units]": mass_kg * c["ecotox_per_kg"],
    }
    return phases, indicators
