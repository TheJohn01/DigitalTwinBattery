"""PDF report: a screening LCA following ISO 14040/14044, not critically reviewed.

build_lca_report() fills the five elements of ISO 14040/14044 with the results of one
dashboard run:
  1. Goal and scope definition      (ISO 14044 4.2)
  2. Life cycle inventory (LCI)      (ISO 14044 4.3)
  3. Life cycle impact assessment    (ISO 14044 4.4)
  4. Interpretation                  (ISO 14044 4.5)
  5. Reporting                       (ISO 14044 5)
The sixth element, critical review (ISO 14044 6), has NOT been carried out.
"""
from . import __version__
from .chemistry import CHEMISTRIES
from .constants import CFB_MIN_EOL_SOH
from .environment import (CFB_KEY, CFB_USE_KEY, ECOTOX_KEY, GRID_G_CO2_PER_KWH, KWH_PER_KM,
                          LIFETIME_KM, PACK_GWP_CROSSCHECK, WATER_KEY, calculate_lca,
                          production_factors, total_energy_kwh)
from matplotlib.figure import Figure

from .report_doc import BLUE, GREY, Report, capacity_figure, fmt_number

STATEMENT = "A screening LCA following ISO 14040/14044, not critically reviewed"

REFERENCES = [
    "ISO 14040:2006 + A1:2020. Environmental management - Life cycle assessment - Principles "
    "and framework.",
    "ISO 14044:2006 + A1:2017 + A2:2020. Environmental management - Life cycle assessment - "
    "Requirements and guidelines.",
    "Regulation (EU) 2023/1542 of 12 July 2023 concerning batteries and waste batteries, "
    "Article 7 and Annex II (carbon footprint).",
    "Andreasi Bassi S., Ardente F., Candelaresi D., Eynard U., Ferronato N., Peters J. (2025). "
    "Rules for the calculation of the Carbon Footprint of industrial Batteries without external "
    "storage (CFB-IND). JRC, EUR 40286. doi:10.2760/6346639.",
    "JRC (2023). Harmonised rules for the calculation of the Carbon Footprint of Electric "
    "Vehicle Batteries (CFB-EV).",
    "Degen F., Mitterfellner M., Kampker A. (2024). Comparative life cycle assessment of "
    "lithium-ion, sodium-ion, and solid-state battery cells for electric vehicles. Journal of "
    "Industrial Ecology. doi:10.1111/jiec.13594.",
    "Llamas-Orozco J. A. et al. (2023). Estimating the environmental impacts of global "
    "lithium-ion battery supply chain: a temporal, geographical, and technological perspective. "
    "PNAS Nexus 2(11), pgad361. doi:10.1093/pnasnexus/pgad361.",
    "Emilsson E., Dahllof L. (2019). Lithium-ion vehicle battery production - status 2019. "
    "IVL Swedish Environmental Research Institute, report C 444.",
    "Eltohamy H. et al. (2024). Review of current practices of life cycle assessment in "
    "electric mobility: a first step towards method harmonization. Sustainable Production and "
    "Consumption 52, 299-313. doi:10.1016/j.spc.2024.10.026.",
    "Huijbregts M. A. J. et al. (2017). ReCiPe2016: a harmonised life cycle impact assessment "
    "method at midpoint and endpoint level. Int. J. Life Cycle Assessment 22, 138-147.",
]


# ---------------------------------------------------------------------------
# Calculations
# ---------------------------------------------------------------------------
def lca_results(chemistry, pack_kwh, soh_curve, use_case, eol_soh=CFB_MIN_EOL_SOH,
                service_years=15, cycles_per_year=365, round_trip_eff=0.90,
                grid_g_co2_per_kwh=GRID_G_CO2_PER_KWH, lifetime_km=LIFETIME_KM,
                kwh_per_km=KWH_PER_KM, dod=1.0,
                config="HE", eol_credit=True, earlier_kwh=0.0):
    """LCA of one case. use_case: "stationary" (energy from the simulated ageing curve, each
    cycle at depth dod) or "ev" (energy = km x kWh/km, as in the CFB-EV rules).
    earlier_kwh: energy a used battery delivered before this study (inf: cut-off, no
    production burden); making and recycling it are shared by energy delivered."""
    if use_case == "stationary":
        energy, cycles = total_energy_kwh(pack_kwh, soh_curve, eol_soh, dod,
                                          service_years, cycles_per_year)
    else:
        energy, cycles = lifetime_km * kwh_per_km, None
    phases, ind = calculate_lca(chemistry, pack_kwh, vehicle=use_case == "ev",
                                round_trip_eff=round_trip_eff,
                                grid_g_co2_per_kwh=grid_g_co2_per_kwh,
                                throughput_kwh=energy, config=config, eol_credit=eol_credit,
                                production_share=energy / (energy + earlier_kwh)
                                if earlier_kwh else 1.0)
    return {"phases": phases, "ind": ind, "energy_kwh": energy, "cycles": cycles}


def sensitivity(chemistry, pack_kwh, soh_curve, base_args, rte_system=None):
    """Change one input at a time and report the carbon footprint per kWh delivered.
    rte_system: the TEA's whole-system efficiency, shown as one more case if given."""
    base = lca_results(chemistry, pack_kwh, soh_curve, **base_args)["ind"]
    rows = [["Base case", base[CFB_KEY], 0.0, base[CFB_USE_KEY]]]
    variants = []
    variants.append(("Production data: high-power cell configuration (Degen et al.)",
                     {"config": "HP"}))
    variants.append(("No end-of-life recycling credit", {"eol_credit": False}))
    variants.append(("Grid carbon intensity -50 %",
                     {"grid_g_co2_per_kwh": base_args["grid_g_co2_per_kwh"] * 0.5}))
    variants.append(("Grid carbon intensity +50 %",
                     {"grid_g_co2_per_kwh": base_args["grid_g_co2_per_kwh"] * 1.5}))
    variants.append(("Round-trip efficiency -5 %-points",
                     {"round_trip_eff": base_args["round_trip_eff"] - 0.05}))
    if rte_system is not None:
        variants.append((f"Round-trip efficiency of the whole system ({100 * rte_system:.1f} %, "
                         "the TEA value)", {"round_trip_eff": rte_system}))
    if base_args.get("earlier_kwh"):
        variants.append(("Used battery, cut-off: no share of making and recycling it",
                         {"earlier_kwh": float("inf")}))
    if base_args["use_case"] == "stationary":
        eol = base_args["eol_soh"]
        if abs(eol - CFB_MIN_EOL_SOH) > 1e-9:
            variants.append((f"End of service life at the CFB-IND minimum, "
                             f"{100 * CFB_MIN_EOL_SOH:.0f} % (instead of {100 * eol:.0f} %)",
                             {"eol_soh": CFB_MIN_EOL_SOH}))
        if abs(eol - 0.80) > 1e-9:
            variants.append((f"End of service life at 80 % instead of {100 * eol:.0f} %",
                             {"eol_soh": 0.80}))
        variants.append(("Service life cap halved",
                         {"service_years": base_args["service_years"] / 2}))
    for name, change in variants:
        r = lca_results(chemistry, pack_kwh, soh_curve, **dict(base_args, **change))["ind"]
        rows.append([name, r[CFB_KEY], 100 * (r[CFB_KEY] / base[CFB_KEY] - 1), r[CFB_USE_KEY]])
    return rows


def _n(x, d=1):
    return fmt_number(x, d, missing="not assessed")


def efficiency_text(rte, rte_cell=None, rte_system=None):
    """Which round-trip efficiency the LCA uses, and why (for the report)."""
    source = "an input of the study"
    if rte_cell is not None:
        default = round(min(max(rte_cell, 0.70), 0.98), 2)
        source = ("the mean energy efficiency of the simulated cycles (PyBaMM)"
                  if abs(rte - default) <= 0.005 else
                  f"set by hand (the simulated value is {100 * rte_cell:.1f} %)")
    text = (f"<b>Round-trip efficiency used: the battery itself (its cells), {100 * rte:.1f} %</b>, "
            f"{source}. The use-phase burden in this study is the battery's own losses: the "
            "energy lost inside the cells while they are charged and discharged (reported "
            "separately and excluded from the regulation-scope footprint, CFB-IND 4.2). Losses "
            "in the power conversion system (inverter, transformer) and in the auxiliary loads "
            "(cooling, battery management) happen in equipment outside the system boundary, "
            "which is cut off with the other pack and system components (1.3 and 1.4); counting "
            "its losses without its production would mix two boundaries. ")
    if rte_system is not None:
        return text + (f"The TEA of the same run uses the whole-system efficiency "
                       f"({100 * rte_system:.1f} %), because its costs and revenues occur at the "
                       "grid connection; section 4.3 shows this study's result with that value.")
    return text + ("A techno-economic assessment, whose costs and revenues occur at the grid "
                   "connection, would use the whole-system efficiency instead.")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def build_lca_report(chemistry, pack_kwh, soh_curve, use_case, run, lca_args, fmt="pdf",
                     second=None):
    """Return the report as PDF bytes (fmt="pdf") or Word bytes (fmt="docx").

    run: settings and simulated values of the dashboard run (keys used below).
    lca_args: eol_soh, service_years, cycles_per_year, round_trip_eff, grid_g_co2_per_kwh,
              lifetime_km, kwh_per_km.
    second: the dashboard's second-life results (dict with "carbon", see app.py), or None."""
    c = CHEMISTRIES[chemistry]
    args = dict(lca_args, use_case=use_case)
    res = lca_results(chemistry, pack_kwh, soh_curve, **args)
    ph, ind = res["phases"], res["ind"]
    f = production_factors(chemistry, "HE")
    sens = sensitivity(chemistry, pack_kwh, soh_curve, args, run.get("rte_system"))
    cfb, cfb_use = ind[CFB_KEY], ind[CFB_USE_KEY]
    stationary = use_case == "stationary"
    eol = lca_args["eol_soh"]
    eol_basis = run.get("eol_basis", "Setting")
    below_cfb = stationary and eol < CFB_MIN_EOL_SOH - 1e-9
    cfb_note = (f" The end of service life ({100 * eol:.0f} %) is below the "
                f"{100 * CFB_MIN_EOL_SOH:.0f} % minimum of the CFB-IND rules, so the "
                "regulation-scope carbon footprint is not a conforming declaration; "
                f"section 4.3 gives the value at {100 * CFB_MIN_EOL_SOH:.0f} %." if below_cfb else "")
    eol_sentence = ""
    if stationary:
        eol_sentence = f" <b>End of service life:</b> {100 * eol:.0f} % of the initial capacity."
        if "eol_basis" in run:
            eol_sentence += (f" Basis: {eol_basis}; the techno-economic assessment of the run "
                             "uses the same end of life.")
        eol_sentence += cfb_note

    doc = Report(f"Screening LCA - {chemistry}", STATEMENT)
    doc.h1(f"Screening life cycle assessment of a battery pack: {c['label']}")
    doc.intro()

    # 1 ------------------------------------------------------------------------------
    doc.h1("1. Goal and scope definition (ISO 14044, 4.2)")
    doc.h2("1.1 Goal")
    doc.p(
        "<b>Intended application:</b> screen the life-cycle climate, water and freshwater "
        "ecotoxicity impacts of a "
        f"{pack_kwh:g} kWh {chemistry} battery operated as simulated, and show which life-cycle "
        "stages and assumptions dominate. <b>Reasons:</b> support design and operating "
        "decisions within the Battery Digital Twin project. <b>Intended audience:</b> the "
        "project team and supervisors (internal). <b>Comparative assertion:</b> this study is "
        "NOT intended to support comparative assertions disclosed to the public. Any public "
        "comparison between chemistries would require a critical review by a panel of "
        "interested parties (ISO 14044, 6.3), which has not been done.")
    doc.h2("1.2 Function, functional unit and reference flow")
    if stationary:
        func = (f"Stationary energy storage (daily energy arbitrage), cycled as in the "
                f"simulation: {run['c_charge']:g}C charge, {run['c_discharge']:g}C "
                f"discharge, {run['cycles_per_year']:,.0f} cycles per year.")
    else:
        func = (f"Traction battery of an electric vehicle: {lca_args['lifetime_km']:,.0f} km "
                f"at {lca_args['kwh_per_km']:g} kWh/km.")
    doc.p(
        f"<b>Function:</b> {func} <b>Functional unit:</b> 1 kWh of energy delivered by the "
        "battery over its service life (Regulation (EU) 2023/1542, Annex II; JRC CFB-IND "
        f"rules, 3.2.1). <b>Total energy over the service life:</b> {_n(res['energy_kwh'], 0)} "
        f"kWh. <b>Reference flow:</b> {_n(ind['Reference flow [kg battery/kWh delivered]'], 4)} "
        "kg of battery per kWh delivered (pack mass "
        f"{_n(ind['Pack mass [kg]'], 0)} kg, from a cell-level specific energy of "
        f"{c['wh_per_kg']:g} Wh/kg - an assumption).{eol_sentence}")
    doc.h2("1.3 System boundary")
    doc.table([
        ["Life-cycle stage", "Included?", "How"],
        ["Raw material acquisition and pre-processing", "Yes",
         f"Cradle-to-gate cell data, Degen et al. 2024 ({f['cell']} cell)"],
        ["Cell production", "Yes", "Degen et al. 2024 (factory energy included)"],
        ["Pack assembly: housing, battery management system, thermal system", "No",
         "Data gap; cut off (see 1.4)"],
        ["Distribution and installation", "No", "Cut off"],
        ["Use phase: battery losses", "Yes, reported separately",
         "Energy lost = energy delivered x (1/round-trip efficiency - 1) x grid intensity. "
         "Excluded from the regulation's carbon footprint (CFB-IND 4.2)"],
        ["Use phase: electricity stored and delivered", "No",
         "Belongs to the application, not to the battery"],
        ["End of life: collection and recycling", "Yes, reported separately",
         "Avoided-burden credit per kg (assumption)"],
    ], [5.5, 2.6, 8.4])
    doc.h2("1.4 Cut-off criteria")
    doc.p(
        "Processes for which no data were available were excluded: module and pack "
        "components (housing, electronics, cooling), which take about 29 % of the energy "
        "needed to produce an NMC111 pack (Dai et al. 2019, in Emilsson & Dahllof 2019, "
        "Table 4), and transport, installation and maintenance. No mass or energy threshold "
        "could be applied, because the cell data come pre-aggregated. This is a known "
        "limitation of a screening study (section 4).")
    doc.h2("1.5 Allocation and end of life")
    doc.p(
        "No multi-output processes are modelled inside the system; allocation within the "
        "background data follows ecoinvent 3.10 as used by Degen et al. Recycling is modelled "
        f"with an avoided-burden credit of {c['eol_credit_kg_per_kg']:g} kg CO2eq per kg of "
        "battery (an assumption). The regulation requires the Circular Footprint Formula "
        "(CFB-IND rules); it was not applied. The credit is therefore shown separately and "
        "tested in the sensitivity check.")
    doc.h2("1.6 Impact categories and assessment methods")
    doc.table([
        ["Impact category", "Indicator (unit)", "Method"],
        ["Climate change", "GWP100 (kg CO2eq)", "ReCiPe 2016 v1.03 (H), as in Degen et al. 2024"],
        ["Water use", "Water consumption potential, WCP (m3)", "ReCiPe 2016 (H)"],
        ["Freshwater ecotoxicity", "FETP (kg 1,4-DCB eq)", "ReCiPe 2016 (H)"],
    ], [4, 5, 7.5])
    doc.p(
        "The EU Environmental Footprint method EF 3.1 (AWARE for water scarcity, USEtox for "
        "ecotoxicity) is required for the regulation's carbon footprint and is recommended "
        "for European studies, but no peer-reviewed EF 3.1 results covering all four "
        "chemistries were available, so ReCiPe 2016 was used throughout for consistency.", "small")
    doc.h2("1.7 Data quality requirements")
    doc.table([
        ["Aspect", "Requirement", "Achieved"],
        ["Time-related coverage", "Data from 2019 or later", "Yes: 2023-2025 sources"],
        ["Geographical coverage", "Production: global supply chain; use: grid of the user",
         "Partly: production location of Degen et al. not stated; grid intensity is a user input"],
        ["Technology coverage", "Same chemistry as the simulated cell",
         "NMC811, NCA, LFP: yes. Sodium-ion: yes (layered oxide; exact composition may differ)"],
        ["Precision", "Uncertainty ranges known", "Degen et al. give 67 % confidence intervals "
         "(figures only); values read from figures"],
        ["Completeness", "All stages in 1.3", "Pack components missing (cut off)"],
        ["Representativeness", "Commercial-scale production", "Modelled factory data"],
        ["Consistency", "One database and method for production", "Yes: ecoinvent 3.10 + ReCiPe"],
        ["Reproducibility", "All inputs reported", "Yes: section 2 and 5"],
        ["Sources", "Peer-reviewed or official", "Yes, except the assumptions marked in 2.1"],
    ], [3.5, 5.5, 7.5])
    doc.h2("1.8 Assumptions and limitations")
    doc.p(
        "Cell-level production data stand in for the pack; pack mass from an assumed specific "
        "energy; the ageing curve comes from empirical models fitted to published cell tests "
        "(see the dashboard's Sources tab); the grid carbon intensity and recycling credit are "
        "assumptions; water and ecotoxicity are assessed for production only.")
    doc.h2("1.9 Critical review")
    doc.p("<b>None.</b> No critical review (ISO 14044, 6) has been carried out.")

    # 2 ------------------------------------------------------------------------------
    doc.h1("2. Life cycle inventory (ISO 14044, 4.3)")
    doc.h2("2.1 Data collected")
    inv = [["Item", "Value", "Unit", "Type", "Source"],
           ["Chemistry (physics model)", c["label"], "-", "Setting", "Dashboard"],
           ["Pack size (initial usable energy)", _n(pack_kwh, 1), "kWh", "Setting", "Dashboard"],
           ["Battery at the start", "new" if run.get("start_soh", 1.0) >= 1 else
            f"used, {100 * run['start_soh']:.0f} % capacity; this study carries "
            f"{100 * res['energy_kwh'] / (res['energy_kwh'] + lca_args.get('earlier_kwh', 0.0)):.0f} % of "
            "making and recycling it (its share of all the energy the battery delivers; the "
            "earlier owner assumed to drive like this one)", "-", "Setting", "Dashboard"],
           ["Cell capacity / energy (simulated)",
            f"{_n(run['cell_capacity_ah'], 2)} Ah / {_n(run['cell_energy_wh'], 2)} Wh", "-",
            "Simulated", "PyBaMM physics model"],
           ["Charge / discharge rate", f"{run['c_charge']:g}C / {run['c_discharge']:g}C", "-",
            "Setting", "Dashboard"],
           ["Ambient / cycling temperature",
            f"{run['ambient_c']:g} / {run['cycling_c']:g}", "°C", "Setting", "Dashboard"],
           ["Cooling", f"{run['cooling']} (h = {run['h']:g} W/m²K)", "-", "Setting",
            "Dashboard (assumed average h)"],
           ["Mean cell temperature while cycling", _n(run["mean_cell_temp"], 1), "°C",
            "Simulated", "PyBaMM physics model"],
           ["Round-trip energy efficiency (battery, cells)",
            _n(100 * lca_args["round_trip_eff"], 1), "%", "Simulated",
            "PyBaMM physics model (mean of simulated cycles); why this type: 2.3"],
           ["Cycles per year", _n(lca_args["cycles_per_year"], 0), "1/year", "Setting",
            "Dashboard"]]
    if stationary:
        inv += [["End of service life (capacity threshold)", _n(100 * eol, 0),
                 "% of initial", "Setting" if eol_basis == "Setting" else "Calculated",
                 f"{eol_basis}; CFB-IND: at least {100 * CFB_MIN_EOL_SOH:.0f} %"],
                ["Service life cap", _n(lca_args["service_years"], 0), "years", "Setting",
                 "CFB-IND: at most 1000 cycles/year"],
                ["Cycles counted", _n(res["cycles"], 0), "cycles", "Simulated",
                 "Empirical ageing model"]]
    else:
        inv += [["Vehicle lifetime", _n(lca_args["lifetime_km"], 0), "km", "Setting",
                 "Distance per day x 365 x years in the car"],
                ["Consumption", _n(lca_args["kwh_per_km"], 3), "kWh/km", "Setting",
                 "Dashboard sidebar"]]
    inv += [["Total energy delivered", _n(res["energy_kwh"], 0), "kWh", "Calculated",
             "CFB-IND 3.2.1"],
            ["Battery losses", _n(ind["Battery losses [kWh]"], 0), "kWh", "Calculated",
             "Energy delivered x (1/efficiency - 1)"],
            ["Grid carbon intensity", _n(lca_args["grid_g_co2_per_kwh"], 1), "g CO2eq/kWh",
             "Literature" if lca_args["grid_g_co2_per_kwh"] == GRID_G_CO2_PER_KWH else "Setting",
             "Electricity Maps, Portugal 2025 mean (default; dashboard input)"],
            ["Production GWP", _n(f["gwp"], 1), "kg CO2eq/kWh cell", "Literature",
             f"Degen et al. 2024, Fig. 6 ({f['cell']}, high-energy)"],
            ["Production water consumption", _n(f["water"], 2), "m3/kWh cell", "Literature",
             "Degen et al. 2024, Fig. 7"],
            ["Production freshwater ecotoxicity", _n(f["ecotox"], 1), "kg 1,4-DCB eq/kWh cell",
             "Literature", "Degen et al. 2024, Fig. 7"],
            ["Specific energy (for pack mass)", _n(c["wh_per_kg"], 0), "Wh/kg", "Literature",
             "Cell datasheet or teardown (chemistry.py)"],
            ["Recycling credit", _n(c["eol_credit_kg_per_kg"], 1), "kg CO2eq/kg", "Assumption",
             "chemistry.py"]]
    doc.table(inv, [4.4, 2.8, 2.5, 1.9, 4.9])
    doc.h2("2.2 Calculation procedures")
    doc.p(
        "Total energy (stationary): E<sub>total</sub> = initial usable energy x sum over "
        "cycles of the remaining capacity fraction, until the capacity first falls below the "
        "end-of-service-life threshold or the service-life cap is reached (CFB-IND 3.2.1, "
        "full cycles multiplied by the mean state of health). Production impacts = pack "
        "energy x impact per kWh of cell. Use-phase losses = E<sub>total</sub> x (1/round-trip "
        "efficiency - 1). All results are divided by E<sub>total</sub> for the functional "
        "unit.")
    if stationary:
        doc.figure(capacity_figure(soh_curve, lca_args["cycles_per_year"],
                                   lca_args["service_years"], eol,
                                   f"end of service life ({100 * eol:.0f} %)"),
                   "Capacity of the battery over its service life, from its empirical ageing "
                   f"model ({100 * lca_args.get('dod', 1.0):.0f} % depth)"
                   + (f", starting from the used battery's {100 * run['start_soh']:.0f} %"
                      if run.get("start_soh", 1.0) < 1 else "")
                   + ". The energy counted (the functional units) is delivered until the first "
                   "cycle below the dashed line or the service-life cap.")
    doc.h2("2.3 Round-trip efficiency: which one and why")
    doc.p(efficiency_text(lca_args["round_trip_eff"], run.get("rte_cell"), run.get("rte_system")))
    doc.h2("2.4 Validation of data")
    eff = 100 * lca_args["round_trip_eff"]
    doc.p(
        f"Energy balance: the simulated cycles return {eff:.1f} % of the charged energy; the "
        "remainder is counted as losses. The production GWP per kWh of the three lithium-ion "
        "chemistries lies within the range of independent studies (Llamas-Orozco et al. 2023: "
        "about 55-82 kg CO2eq/kWh at pack level; Emilsson & Dahllof 2019: 61-106 kg CO2eq/kWh). "
        "The ageing model behind the cycle count was checked against published cell tests "
        "(dashboard Sources tab).")

    # 3 ------------------------------------------------------------------------------
    doc.h1("3. Life cycle impact assessment (ISO 14044, 4.4)")
    doc.p(
        "Mandatory elements: the impact categories, indicators and characterization models "
        "are listed in 1.6. Classification and characterization were carried out in the "
        "source study (ecoinvent 3.10, ReCiPe 2016 H). Optional elements (normalization, "
        "grouping, weighting) were NOT applied; no single score is given.")
    doc.h2("3.1 Results per life-cycle stage (whole battery)")
    rows = [["Stage", "Climate change (kg CO2eq)", "Water consumption (m3)",
             "Freshwater ecotoxicity (kg 1,4-DCB eq)"]]
    for _, r in ph.iterrows():
        rows.append([r["Phase"], _n(r["Emissions [kg CO2eq]"], 0),
                     _n(r["Water consumption [m3]"], 1),
                     _n(r["Freshwater ecotoxicity [kg 1,4-DCB eq]"], 1)])
    doc.table(rows, [6, 3.5, 3.2, 3.8])
    fig = Figure(figsize=(7, 2.6))
    ax = fig.subplots()
    stages = ph.iloc[:3]
    ax.bar(["Production", "Use (losses)", "End of life (credit)"],
           stages["Emissions [kg CO2eq]"], color=[BLUE, "#f2a541", "#43c25a"])
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set(ylabel="kg CO2eq")
    ax.grid(axis="y", alpha=0.3)
    doc.figure(fig, "Climate change by life-cycle stage for the whole battery: making the cells, "
               "the battery's own losses while it works, and the recycling credit (an "
               "assumption, below zero).")
    doc.h2("3.2 Results per functional unit (1 kWh delivered)")
    doc.table([
        ["Indicator", "Value", "Unit"],
        ["Carbon footprint, regulation scope (production + end of life)", _n(cfb, 1),
         "g CO2eq/kWh"],
        ["Carbon footprint including use-phase losses", _n(cfb_use, 1), "g CO2eq/kWh"],
        ["Water consumption (production)",
         _n(ind[WATER_KEY], 2), "L/kWh"],
        ["Freshwater ecotoxicity (production)",
         _n(ind[ECOTOX_KEY], 2),
         "g 1,4-DCB eq/kWh"],
    ], [9, 3, 4.5])

    # 4 ------------------------------------------------------------------------------
    doc.h1("4. Interpretation (ISO 14044, 4.5)")
    gwp = ph["Emissions [kg CO2eq]"].iloc[:3]
    gross = gwp.clip(lower=0).sum()
    shares = ", ".join(f"{name.split(' (')[0].lower()} {100 * v / gross:.0f} %"
                       for name, v in zip(ph["Phase"].iloc[:3], gwp) if v > 0)
    doc.h2("4.1 Significant issues")
    doc.p(
        f"Climate change (gross, before the recycling credit): {shares}. The carbon "
        f"footprint per kWh delivered depends as much on the service life ({_n(res['energy_kwh'], 0)} "
        "kWh delivered) as on production: halving the life doubles it. Water consumption and "
        "freshwater ecotoxicity come entirely from production in this screening.")
    doc.h2("4.2 Completeness check")
    doc.table([
        ["Element", "Status"],
        ["Cell production (all stages to the factory gate)", "Complete (source data)"],
        ["Pack components", "Missing - underestimates production impacts"],
        ["Use phase", "Losses only; included separately"],
        ["End of life", "Simplified credit (assumption); Circular Footprint Formula not applied"],
        ["Water and ecotoxicity beyond production", "Not assessed"],
    ], [8, 8.5])
    doc.h2("4.3 Sensitivity check (one change at a time)")
    srows = [["Variant", "Carbon footprint, regulation scope (g CO2eq/kWh)", "Change",
              "Incl. use-phase losses (g CO2eq/kWh)"]]
    for name, v, d, vu in sens:
        srows.append([name, _n(v, 1), f"{d:+.0f} %", _n(vu, 1)])
    doc.table(srows, [7, 3.6, 2, 3.9])
    if chemistry in PACK_GWP_CROSSCHECK:
        doc.p(
            f"Cross-check: Llamas-Orozco et al. (2023) give {PACK_GWP_CROSSCHECK[chemistry]:g} "
            f"kg CO2eq/kWh at pack level (global average) against {f['gwp']:g} kg CO2eq/kWh at "
            "cell level used here.", "small")
    doc.h2("4.4 Consistency check")
    doc.p(
        "Production data for all chemistries come from one study, database and method, so "
        "they are consistent with each other. Inconsistencies: cell-level data are used for a "
        "pack; the sodium-ion data describe a layered-oxide cell like the physics model "
        "(Na-Ni-Fe-Mn oxide), but its exact composition may differ; the ReCiPe climate-change model differs slightly from the EF 3.1 model "
        "required by the regulation.")
    doc.h2("4.5 Conclusions, limitations and recommendations")
    doc.p(
        f"For this run the battery's carbon footprint is about {_n(cfb, 0)} g CO2eq per kWh "
        f"delivered (regulation scope) and {_n(cfb_use, 0)} g CO2eq/kWh including its own "
        f"losses.{cfb_note} Because the result is a screening with cut-offs and assumptions, "
        "it should "
        "not be used for public comparisons or regulatory declarations. Recommended next "
        "steps: add pack components (bill of materials), model end of life with the Circular "
        "Footprint Formula, use EF 3.1 (AWARE, USEtox) with ecoinvent or the EF datasets, use "
        "the actual grid mix, and commission a critical review before any public "
        "comparison.")

    # 5 ------------------------------------------------------------------------------
    if second and "carbon" in second:
        doc.h2("4.6 Second life after the car")
        doc.p(f"After {second['ev_years']} years in a car the battery keeps "
              f"{100 * second['capacity_left']:.1f} % of its capacity and is reused for "
              f"stationary storage for {second['years']} years (Economics tab). Carbon footprint, "
              "regulation scope, per kWh delivered. Sharing the production between both lives "
              "divides it over all the energy the battery delivers; the cut-off view leaves it "
              "with the car, so the second life carries only the repurposing test electricity "
              "(NREL B2U calculator; transport, labour and the new inverter and enclosure are "
              "not included). The alternative is a new LFP storage system over the same years.")
        doc.table([["Case", "g CO2eq/kWh delivered"]]
                  + [[k, _n(v, 1)] for k, v in second["carbon"].items()], [11, 5.5])

    doc.h1("5. Reporting (ISO 14044, 5)")
    doc.p(
        f"<b>{STATEMENT}.</b> This document is the study report. It was generated "
        "automatically; the inputs in section 2.1 and the settings below allow the results "
        "to be reproduced with the same program version.")
    doc.table([
        ["Setting", "Value"],
        ["Program", f"Battery Digital Twin v{__version__}"],
        ["Physics model", run["model"]],
        ["Battery test cycles (physics, full depth)", _n(run["n_cycles"], 0)],
        ["Storage depth of discharge", f"{100 * run.get('storage_dod', 1.0):.0f} %"],
        ["Cycles to 80 % capacity (storage cycle)", _n(run["cycles_to_80"], 0)],
        ["Use case", "Stationary storage" if stationary else "Electric vehicle"],
    ], [8, 8.5])
    doc.h2("References")
    for ref in REFERENCES:
        doc.p(f"- {ref}", "small")

    return doc.docx() if fmt == "docx" else doc.pdf()
