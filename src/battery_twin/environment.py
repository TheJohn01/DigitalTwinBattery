"""Screening life cycle assessment (LCA) of a battery pack.

A screening LCA following ISO 14040/14044, NOT critically reviewed. lca_report.py turns
the results into a report with the five ISO elements (goal and scope, inventory, impact
assessment, interpretation, reporting).

Data:
- Production (cradle-to-gate, per kWh of CELL capacity): Degen, Mitterfellner & Kampker
  (2024), J. Industrial Ecology, doi 10.1111/jiec.13594. Ecoinvent 3.10 with ReCiPe 2016
  (H): global warming (GWP100), water consumption (WCP) and freshwater ecotoxicity
  (FETP). Values read from their Fig. 6 and 7 (data/lca_degen2024.csv). Pack parts
  (housing, battery management system, cooling) are not included.
- Functional unit and total energy: JRC rules for the carbon footprint of industrial
  batteries (CFB-IND, Andreasi Bassi et al. 2025) under Regulation (EU) 2023/1542:
  1 kWh of energy delivered over the service life; end of service life at >= 70 % of the
  initial capacity; at most 1000 equivalent full cycles per year of service life.
- Use phase (battery losses only) and end-of-life credit are reported separately: the
  regulation's carbon footprint excludes the use phase, and the recycling credit is an
  assumption (eol_credit_kg_per_kg in chemistry.py), not sourced data.
"""
import numpy as np
import pandas as pd

from .ageing import cycles_to
from .chemistry import CHEMISTRIES
from .constants import CFB_MAX_CYCLES_PER_YEAR, CFB_MIN_EOL_SOH, DATA_DIR

FACTORS = pd.read_csv(DATA_DIR / "lca_degen2024.csv")

# Pack-level GWP (cradle-to-gate, global average 2020) from Llamas-Orozco et al. (2023),
# PNAS Nexus 2, pgad361: used only as a cross-check in the interpretation.
PACK_GWP_CROSSCHECK = {"NMC": 77.4, "NCA": 82.3, "LFP": 55.0}

# Defaults (assumptions; the dashboard lets the user change them)
GRID_G_CO2_PER_KWH = 210.0      # grid carbon intensity [g CO2eq/kWh]
LIFETIME_KM, KWH_PER_KM = 200000, 0.16   # electric vehicle use

# Indicator names used by the dashboard and both reports
CFB_KEY = "Carbon footprint, regulation scope [g CO2eq/kWh delivered]"
CFB_USE_KEY = "Carbon footprint incl. use-phase losses [g CO2eq/kWh delivered]"
WATER_KEY = "Water consumption [L/kWh delivered]"
ECOTOX_KEY = "Freshwater ecotoxicity [g 1,4-DCB eq/kWh delivered]"


def production_factors(chemistry, config="HE"):
    """GWP [kg CO2eq], water [m3] and freshwater ecotoxicity [kg 1,4-DCB eq] per kWh of
    cell capacity, from Degen et al. 2024. config: "HE" (high energy) or "HP" (high power)."""
    row = FACTORS[(FACTORS.chemistry == chemistry) & (FACTORS.config == config)].iloc[0]
    return {"gwp": float(row.gwp_kg_co2e_per_kwh), "water": float(row.wcp_m3_per_kwh),
            "ecotox": float(row.fetp_kg_dcb_per_kwh), "cell": row.degen_cell}


def total_energy_kwh(capacity_kwh, soh_curve, eol_soh=CFB_MIN_EOL_SOH, dod=1.0,
                     service_years=None, cycles_per_year=None):
    """Energy delivered over the service life [kWh] and the cycles counted.

    Each cycle delivers capacity x its remaining capacity fraction x depth of discharge,
    until the capacity first falls below eol_soh (the CFB-IND rules require >= 70 %).
    If service_years is given, the service life is also limited to service_years x
    min(cycles_per_year, 1000) cycles."""
    q = np.asarray(soh_curve, dtype=float)
    n = int(min(cycles_to(q, eol_soh) - 1, len(q)))   # the cycles before the first below
    if service_years:
        n = min(n, int(service_years * min(cycles_per_year or CFB_MAX_CYCLES_PER_YEAR,
                                           CFB_MAX_CYCLES_PER_YEAR)))
    return float(capacity_kwh * dod * np.sum(q[:n])), n


def lifetime_throughput_kwh(capacity_kwh, vehicle, lifetime_km=LIFETIME_KM,
                            kwh_per_km=KWH_PER_KM, lifetime_cycles=3000, dod=0.80):
    """Energy delivered by the battery over its life [kWh] when no ageing curve is given."""
    if vehicle:
        return lifetime_km * kwh_per_km
    return capacity_kwh * dod * lifetime_cycles


def calculate_lca(chemistry, capacity_kwh, vehicle=True, lifetime_km=LIFETIME_KM,
                  kwh_per_km=KWH_PER_KM, lifetime_cycles=3000, dod=0.80,
                  round_trip_eff=0.90, grid_g_co2_per_kwh=GRID_G_CO2_PER_KWH,
                  throughput_kwh=None, config="HE", eol_credit=True):
    """Phase results and indicators per functional unit (1 kWh delivered).

    throughput_kwh: energy delivered over the service life (e.g. from total_energy_kwh with
    the simulated ageing curve); if None it is estimated with lifetime_throughput_kwh."""
    c = CHEMISTRIES[chemistry]
    f = production_factors(chemistry, config)
    mass_kg = capacity_kwh * 1000.0 / c["wh_per_kg"]
    if throughput_kwh is None:
        throughput_kwh = lifetime_throughput_kwh(capacity_kwh, vehicle, lifetime_km,
                                                 kwh_per_km, lifetime_cycles, dod)

    production = {"gwp": capacity_kwh * f["gwp"], "water": capacity_kwh * f["water"],
                  "ecotox": capacity_kwh * f["ecotox"]}
    losses_kwh = throughput_kwh * (1.0 / round_trip_eff - 1.0)
    use_gwp = losses_kwh * grid_g_co2_per_kwh / 1000.0
    eol_gwp = -mass_kg * c["eol_credit_kg_per_kg"] if eol_credit else 0.0
    total_gwp = production["gwp"] + use_gwp + eol_gwp

    phases = pd.DataFrame({
        "Phase": ["Production (cells, cradle-to-gate)", "Use (battery losses)",
                  "End of life (recycling credit, assumption)", "TOTAL"],
        "Emissions [kg CO2eq]": [production["gwp"], use_gwp, eol_gwp, total_gwp],
        "Water consumption [m3]": [production["water"], np.nan, np.nan, production["water"]],
        "Freshwater ecotoxicity [kg 1,4-DCB eq]": [production["ecotox"], np.nan, np.nan,
                                                   production["ecotox"]],
    })
    fu = throughput_kwh                                   # number of functional units
    # Totals per phase are in `phases`; per kWh delivered here (g/kWh = kg/MWh).
    indicators = {
        "Pack mass [kg]": mass_kg,
        "Reference flow [kg battery/kWh delivered]": mass_kg / fu,
        "Battery losses [kWh]": losses_kwh,
        CFB_KEY: 1000.0 * (production["gwp"] + eol_gwp) / fu,
        CFB_USE_KEY: 1000.0 * total_gwp / fu,
        WATER_KEY: 1000.0 * production["water"] / fu,
        ECOTOX_KEY: 1000.0 * production["ecotox"] / fu,
    }
    return phases, indicators

