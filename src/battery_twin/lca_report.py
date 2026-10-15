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
from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from . import __version__
from .chemistry import CHEMISTRIES
from .environment import (CFB_MIN_EOL_SOH, PACK_GWP_CROSSCHECK, calculate_lca,
                          production_factors, total_energy_kwh)

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
                grid_g_co2_per_kwh=210.0, lifetime_km=200000, kwh_per_km=0.16,
                config="HE", eol_credit=True):
    """LCA of one case. use_case: "stationary" (energy from the simulated ageing curve) or
    "ev" (energy = km x kWh/km, as in the CFB-EV rules)."""
    if use_case == "stationary":
        energy, cycles = total_energy_kwh(pack_kwh, soh_curve, eol_soh, 1.0,
                                          service_years, cycles_per_year)
    else:
        energy, cycles = lifetime_km * kwh_per_km, None
    phases, ind = calculate_lca(chemistry, pack_kwh, vehicle=use_case == "ev",
                                round_trip_eff=round_trip_eff,
                                grid_g_co2_per_kwh=grid_g_co2_per_kwh,
                                throughput_kwh=energy, config=config, eol_credit=eol_credit)
    return {"phases": phases, "ind": ind, "energy_kwh": energy, "cycles": cycles}


def sensitivity(chemistry, pack_kwh, soh_curve, base_args):
    """Change one input at a time and report the carbon footprint per kWh delivered."""
    key = "Carbon footprint, regulation scope [g CO2eq/kWh delivered]"
    key_use = "Carbon footprint incl. use-phase losses [g CO2eq/kWh delivered]"
    base = lca_results(chemistry, pack_kwh, soh_curve, **base_args)["ind"]
    variants = [("Base case", {})]
    variants.append(("Production data: high-power cell configuration (Degen et al.)",
                     {"config": "HP"}))
    variants.append(("No end-of-life recycling credit", {"eol_credit": False}))
    variants.append(("Grid carbon intensity -50 %",
                     {"grid_g_co2_per_kwh": base_args["grid_g_co2_per_kwh"] * 0.5}))
    variants.append(("Grid carbon intensity +50 %",
                     {"grid_g_co2_per_kwh": base_args["grid_g_co2_per_kwh"] * 1.5}))
    variants.append(("Round-trip efficiency -5 %-points",
                     {"round_trip_eff": base_args["round_trip_eff"] - 0.05}))
    if base_args["use_case"] == "stationary":
        variants.append(("End of service life at 80 % instead of "
                         f"{100 * base_args['eol_soh']:.0f} %", {"eol_soh": 0.80}))
        variants.append(("Service life cap halved",
                         {"service_years": base_args["service_years"] / 2}))
    rows = []
    for name, change in variants:
        r = lca_results(chemistry, pack_kwh, soh_curve, **dict(base_args, **change))["ind"]
        rows.append([name, r[key], 100 * (r[key] / base[key] - 1), r[key_use]])
    return rows


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------
_styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_styles["Heading1"], fontSize=15, spaceBefore=12, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("Body", parent=_styles["BodyText"], fontSize=9.5, leading=13)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8, leading=10)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8, leading=10)
BOX = ParagraphStyle("Box", parent=BODY, backColor=colors.HexColor("#FFF4D6"),
                     borderColor=colors.HexColor("#C99A00"), borderWidth=0.6, borderPadding=6,
                     spaceBefore=6, spaceAfter=10)


def _p(text, style=BODY):
    return Paragraph(text, style)


def _table(rows, widths, header=True):
    data = [[_p(str(c), CELL) for c in row] for row in rows]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if header else 0)
    style = [("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF6")))
    t.setStyle(TableStyle(style))
    return t


def _n(x, d=1):
    if x is None or x != x:
        return "not assessed"
    return f"{x:,.{d}f}"


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def build_lca_report(chemistry, pack_kwh, soh_curve, use_case, run, lca_args):
    """Return the report as PDF bytes.

    run: settings and simulated values of the dashboard run (keys used below).
    lca_args: eol_soh, service_years, cycles_per_year, round_trip_eff, grid_g_co2_per_kwh,
              lifetime_km, kwh_per_km."""
    c = CHEMISTRIES[chemistry]
    args = dict(lca_args, use_case=use_case)
    res = lca_results(chemistry, pack_kwh, soh_curve, **args)
    ph, ind = res["phases"], res["ind"]
    f = production_factors(chemistry, "HE")
    sens = sensitivity(chemistry, pack_kwh, soh_curve, args)
    cfb = ind["Carbon footprint, regulation scope [g CO2eq/kWh delivered]"]
    cfb_use = ind["Carbon footprint incl. use-phase losses [g CO2eq/kWh delivered]"]
    stationary = use_case == "stationary"

    story = []
    story += [_p(f"Screening life cycle assessment of a battery pack: {c['label']}", H1),
              _p(f"<b>{STATEMENT}.</b>", BOX),
              _p(f"Generated {date.today().isoformat()} by Battery Digital Twin "
                 f"v{__version__} from one simulation run. This is a model report (mock-up) "
                 "for a student project: every number comes from the simulation, from the "
                 "cited literature or from an assumption marked as such.", SMALL)]

    # 1 ------------------------------------------------------------------------------
    story.append(_p("1. Goal and scope definition (ISO 14044, 4.2)", H1))
    story.append(_p("1.1 Goal", H2))
    story.append(_p(
        "<b>Intended application:</b> screen the life-cycle climate, water and freshwater "
        "ecotoxicity impacts of a "
        f"{pack_kwh:g} kWh {chemistry} battery operated as simulated, and show which life-cycle "
        "stages and assumptions dominate. <b>Reasons:</b> support design and operating "
        "decisions within the Battery Digital Twin project. <b>Intended audience:</b> the "
        "project team and supervisors (internal). <b>Comparative assertion:</b> this study is "
        "NOT intended to support comparative assertions disclosed to the public. Any public "
        "comparison between chemistries would require a critical review by a panel of "
        "interested parties (ISO 14044, 6.3), which has not been done."))
    story.append(_p("1.2 Function, functional unit and reference flow", H2))
    if stationary:
        func = (f"Stationary energy storage (daily energy arbitrage), cycled as in the "
                f"simulation: {run['c_charge']:g}C charge, {run['c_discharge']:g}C "
                f"discharge, {run['cycles_per_year']:,.0f} cycles per year.")
    else:
        func = (f"Traction battery of an electric vehicle: {lca_args['lifetime_km']:,.0f} km "
                f"at {lca_args['kwh_per_km']:g} kWh/km.")
    story.append(_p(
        f"<b>Function:</b> {func} <b>Functional unit:</b> 1 kWh of energy delivered by the "
        "battery over its service life (Regulation (EU) 2023/1542, Annex II; JRC CFB-IND "
        f"rules, 3.2.1). <b>Total energy over the service life:</b> {_n(res['energy_kwh'], 0)} "
        f"kWh. <b>Reference flow:</b> {_n(ind['Reference flow [kg battery/kWh delivered]'], 4)} "
        "kg of battery per kWh delivered (pack mass "
        f"{_n(ind['Pack mass [kg]'], 0)} kg, from a cell-level specific energy of "
        f"{c['wh_per_kg']:g} Wh/kg - an assumption)."))
    story.append(_p("1.3 System boundary", H2))
    story.append(_table([
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
    ], [5.5, 2.6, 8.4]))
    story.append(_p("1.4 Cut-off criteria", H2))
    story.append(_p(
        "Processes for which no data were available were excluded: module and pack "
        "components (housing, electronics, cooling), which take about 29 % of the energy "
        "needed to produce an NMC111 pack (Dai et al. 2019, in Emilsson & Dahllof 2019, "
        "Table 4), and transport, installation and maintenance. No mass or energy threshold "
        "could be applied, because the cell data come pre-aggregated. This is a known "
        "limitation of a screening study (section 4)."))
    story.append(_p("1.5 Allocation and end of life", H2))
    story.append(_p(
        "No multi-output processes are modelled inside the system; allocation within the "
        "background data follows ecoinvent 3.10 as used by Degen et al. Recycling is modelled "
        f"with an avoided-burden credit of {c['eol_credit_kg_per_kg']:g} kg CO2eq per kg of "
        "battery (an assumption). The regulation requires the Circular Footprint Formula "
        "(CFB-IND rules); it was not applied. The credit is therefore shown separately and "
        "tested in the sensitivity check."))
    story.append(_p("1.6 Impact categories and assessment methods", H2))
    story.append(_table([
        ["Impact category", "Indicator (unit)", "Method"],
        ["Climate change", "GWP100 (kg CO2eq)", "ReCiPe 2016 v1.03 (H), as in Degen et al. 2024"],
        ["Water use", "Water consumption potential, WCP (m3)", "ReCiPe 2016 (H)"],
        ["Freshwater ecotoxicity", "FETP (kg 1,4-DCB eq)", "ReCiPe 2016 (H)"],
    ], [4, 5, 7.5]))
    story.append(_p(
        "The EU Environmental Footprint method EF 3.1 (AWARE for water scarcity, USEtox for "
        "ecotoxicity) is required for the regulation's carbon footprint and is recommended "
        "for European studies, but no peer-reviewed EF 3.1 results covering all four "
        "chemistries were available, so ReCiPe 2016 was used throughout for consistency.",
        SMALL))
    story.append(_p("1.7 Data quality requirements", H2))
    story.append(_table([
        ["Aspect", "Requirement", "Achieved"],
        ["Time-related coverage", "Data from 2019 or later", "Yes: 2023-2025 sources"],
        ["Geographical coverage", "Production: global supply chain; use: grid of the user",
         "Partly: production location of Degen et al. not stated; grid intensity is a user input"],
        ["Technology coverage", "Same chemistry as the simulated cell",
         "NMC811, NCA, LFP: yes. Sodium-ion: layered-oxide data for an NVPF physics model"],
        ["Precision", "Uncertainty ranges known", "Degen et al. give 67 % confidence intervals "
         "(figures only); values read from figures"],
        ["Completeness", "All stages in 1.3", "Pack components missing (cut off)"],
        ["Representativeness", "Commercial-scale production", "Modelled factory data"],
        ["Consistency", "One database and method for production", "Yes: ecoinvent 3.10 + ReCiPe"],
        ["Reproducibility", "All inputs reported", "Yes: section 2 and 5"],
        ["Sources", "Peer-reviewed or official", "Yes, except the assumptions marked in 2.1"],
    ], [3.5, 5.5, 7.5]))
    story.append(_p("1.8 Assumptions and limitations", H2))
    story.append(_p(
        "Cell-level production data stand in for the pack; pack mass from an assumed specific "
        "energy; the ageing curve comes from empirical models fitted to published cell tests "
        "(see the dashboard's Sources tab); the grid carbon intensity and recycling credit are "
        "assumptions; water and ecotoxicity are assessed for production only."))
    story.append(_p("1.9 Critical review", H2))
    story.append(_p("<b>None.</b> No critical review (ISO 14044, 6) has been carried out."))

    # 2 ------------------------------------------------------------------------------
    story.append(_p("2. Life cycle inventory (ISO 14044, 4.3)", H1))
    story.append(_p("2.1 Data collected", H2))
    inv = [["Item", "Value", "Unit", "Type", "Source"],
           ["Chemistry (physics model)", c["label"], "-", "Setting", "Dashboard"],
           ["Pack size (initial usable energy)", _n(pack_kwh, 1), "kWh", "Setting", "Dashboard"],
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
           ["Round-trip energy efficiency", _n(100 * lca_args["round_trip_eff"], 1), "%",
            "Simulated", "PyBaMM physics model (mean of simulated cycles)"],
           ["Cycles per year", _n(lca_args["cycles_per_year"], 0), "1/year", "Setting",
            "Dashboard"]]
    if stationary:
        inv += [["End of service life (capacity threshold)", _n(100 * lca_args["eol_soh"], 0),
                 "% of initial", "Setting", "CFB-IND: at least 70 %"],
                ["Service life cap", _n(lca_args["service_years"], 0), "years", "Setting",
                 "CFB-IND: at most 1000 cycles/year"],
                ["Cycles counted", _n(res["cycles"], 0), "cycles", "Simulated",
                 "Empirical ageing model"]]
    else:
        inv += [["Vehicle lifetime", _n(lca_args["lifetime_km"], 0), "km", "Assumption",
                 "Dashboard"],
                ["Consumption", _n(lca_args["kwh_per_km"], 3), "kWh/km", "Assumption",
                 "Dashboard"]]
    inv += [["Total energy delivered", _n(res["energy_kwh"], 0), "kWh", "Calculated",
             "CFB-IND 3.2.1"],
            ["Battery losses", _n(ind["Battery losses [kWh]"], 0), "kWh", "Calculated",
             "Energy delivered x (1/efficiency - 1)"],
            ["Grid carbon intensity", _n(lca_args["grid_g_co2_per_kwh"], 0), "g CO2eq/kWh",
             "Assumption", "Dashboard input"],
            ["Production GWP", _n(f["gwp"], 1), "kg CO2eq/kWh cell", "Literature",
             f"Degen et al. 2024, Fig. 6 ({f['cell']}, high-energy)"],
            ["Production water consumption", _n(f["water"], 2), "m3/kWh cell", "Literature",
             "Degen et al. 2024, Fig. 7"],
            ["Production freshwater ecotoxicity", _n(f["ecotox"], 1), "kg 1,4-DCB eq/kWh cell",
             "Literature", "Degen et al. 2024, Fig. 7"],
            ["Specific energy (for pack mass)", _n(c["wh_per_kg"], 0), "Wh/kg", "Assumption",
             "chemistry.py"],
            ["Recycling credit", _n(c["eol_credit_kg_per_kg"], 1), "kg CO2eq/kg", "Assumption",
             "chemistry.py"]]
    story.append(_table(inv, [4.4, 2.8, 2.5, 1.9, 4.9]))
    story.append(_p("2.2 Calculation procedures", H2))
    story.append(_p(
        "Total energy (stationary): E<sub>total</sub> = initial usable energy x sum over "
        "cycles of the remaining capacity fraction, until the capacity first falls below the "
        "end-of-service-life threshold or the service-life cap is reached (CFB-IND 3.2.1, "
        "full cycles multiplied by the mean state of health). Production impacts = pack "
        "energy x impact per kWh of cell. Use-phase losses = E<sub>total</sub> x (1/round-trip "
        "efficiency - 1). All results are divided by E<sub>total</sub> for the functional "
        "unit."))
    story.append(_p("2.3 Validation of data", H2))
    eff = 100 * lca_args["round_trip_eff"]
    story.append(_p(
        f"Energy balance: the simulated cycles return {eff:.1f} % of the charged energy; the "
        "remainder is counted as losses. The production GWP per kWh of the three lithium-ion "
        "chemistries lies within the range of independent studies (Llamas-Orozco et al. 2023: "
        "about 55-82 kg CO2eq/kWh at pack level; Emilsson & Dahllof 2019: 61-106 kg CO2eq/kWh). "
        "The ageing model behind the cycle count was checked against published cell tests "
        "(dashboard Sources tab)."))

    # 3 ------------------------------------------------------------------------------
    story.append(_p("3. Life cycle impact assessment (ISO 14044, 4.4)", H1))
    story.append(_p(
        "Mandatory elements: the impact categories, indicators and characterization models "
        "are listed in 1.6. Classification and characterization were carried out in the "
        "source study (ecoinvent 3.10, ReCiPe 2016 H). Optional elements (normalization, "
        "grouping, weighting) were NOT applied; no single score is given."))
    story.append(_p("3.1 Results per life-cycle stage (whole battery)", H2))
    rows = [["Stage", "Climate change (kg CO2eq)", "Water consumption (m3)",
             "Freshwater ecotoxicity (kg 1,4-DCB eq)"]]
    for _, r in ph.iterrows():
        rows.append([r["Phase"], _n(r["Emissions [kg CO2eq]"], 0),
                     _n(r["Water consumption [m3]"], 1),
                     _n(r["Freshwater ecotoxicity [kg 1,4-DCB eq]"], 1)])
    story.append(_table(rows, [6, 3.5, 3.2, 3.8]))
    story.append(_p("3.2 Results per functional unit (1 kWh delivered)", H2))
    story.append(_table([
        ["Indicator", "Value", "Unit"],
        ["Carbon footprint, regulation scope (production + end of life)", _n(cfb, 1),
         "g CO2eq/kWh"],
        ["Carbon footprint including use-phase losses", _n(cfb_use, 1), "g CO2eq/kWh"],
        ["Water consumption (production)",
         _n(ind["Water consumption [L/kWh delivered]"], 2), "L/kWh"],
        ["Freshwater ecotoxicity (production)",
         _n(ind["Freshwater ecotoxicity [g 1,4-DCB eq/kWh delivered]"], 2),
         "g 1,4-DCB eq/kWh"],
    ], [9, 3, 4.5]))

    # 4 ------------------------------------------------------------------------------
    story.append(_p("4. Interpretation (ISO 14044, 4.5)", H1))
    gwp = ph["Emissions [kg CO2eq]"].iloc[:3]
    gross = gwp.clip(lower=0).sum()
    shares = ", ".join(f"{name.split(' (')[0].lower()} {100 * v / gross:.0f} %"
                       for name, v in zip(ph["Phase"].iloc[:3], gwp) if v > 0)
    story.append(_p("4.1 Significant issues", H2))
    story.append(_p(
        f"Climate change (gross, before the recycling credit): {shares}. The carbon "
        f"footprint per kWh delivered depends as much on the service life ({_n(res['energy_kwh'], 0)} "
        "kWh delivered) as on production: halving the life doubles it. Water consumption and "
        "freshwater ecotoxicity come entirely from production in this screening."))
    story.append(_p("4.2 Completeness check", H2))
    story.append(_table([
        ["Element", "Status"],
        ["Cell production (all stages to the factory gate)", "Complete (source data)"],
        ["Pack components", "Missing - underestimates production impacts"],
        ["Use phase", "Losses only; included separately"],
        ["End of life", "Simplified credit (assumption); Circular Footprint Formula not applied"],
        ["Water and ecotoxicity beyond production", "Not assessed"],
    ], [8, 8.5]))
    story.append(_p("4.3 Sensitivity check (one change at a time)", H2))
    srows = [["Variant", "Carbon footprint, regulation scope (g CO2eq/kWh)", "Change",
              "Incl. use-phase losses (g CO2eq/kWh)"]]
    for name, v, d, vu in sens:
        srows.append([name, _n(v, 1), f"{d:+.0f} %", _n(vu, 1)])
    story.append(_table(srows, [7, 3.6, 2, 3.9]))
    if chemistry in PACK_GWP_CROSSCHECK:
        story.append(_p(
            f"Cross-check: Llamas-Orozco et al. (2023) give {PACK_GWP_CROSSCHECK[chemistry]:g} "
            f"kg CO2eq/kWh at pack level (global average) against {f['gwp']:g} kg CO2eq/kWh at "
            "cell level used here.", SMALL))
    story.append(_p("4.4 Consistency check", H2))
    story.append(_p(
        "Production data for all chemistries come from one study, database and method, so "
        "they are consistent with each other. Inconsistencies: cell-level data are used for a "
        "pack; the sodium-ion data describe a layered-oxide cell while the physics model uses "
        "NVPF; the ReCiPe climate-change model differs slightly from the EF 3.1 model "
        "required by the regulation."))
    story.append(_p("4.5 Conclusions, limitations and recommendations", H2))
    story.append(_p(
        f"For this run the battery's carbon footprint is about {_n(cfb, 0)} g CO2eq per kWh "
        f"delivered (regulation scope) and {_n(cfb_use, 0)} g CO2eq/kWh including its own "
        "losses. Because the result is a screening with cut-offs and assumptions, it should "
        "not be used for public comparisons or regulatory declarations. Recommended next "
        "steps: add pack components (bill of materials), model end of life with the Circular "
        "Footprint Formula, use EF 3.1 (AWARE, USEtox) with ecoinvent or the EF datasets, use "
        "the actual grid mix, and commission a critical review before any public "
        "comparison."))

    # 5 ------------------------------------------------------------------------------
    story.append(_p("5. Reporting (ISO 14044, 5)", H1))
    story.append(_p(
        f"<b>{STATEMENT}.</b> This document is the study report. It was generated "
        "automatically; the inputs in section 2.1 and the settings below allow the results "
        "to be reproduced with the same program version."))
    story.append(_table([
        ["Setting", "Value"],
        ["Program", f"Battery Digital Twin v{__version__}"],
        ["Physics model", run["model"]],
        ["Simulated cycles shown", _n(run["n_cycles"], 0)],
        ["Cycles to 80 % capacity (simulation)", _n(run["cycles_to_80"], 0)],
        ["Use case", "Stationary storage" if stationary else "Electric vehicle"],
    ], [8, 8.5]))
    story.append(_p("References", H2))
    for ref in REFERENCES:
        story.append(_p(f"- {ref}", SMALL))

    buf = BytesIO()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(2 * cm, 1.2 * cm, f"{STATEMENT}  |  page {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                      topMargin=1.8 * cm, bottomMargin=1.8 * cm,
                      title=f"Screening LCA - {chemistry}",
                      author="Battery Digital Twin").build(story, onFirstPage=footer,
                                                         onLaterPages=footer)
    return buf.getvalue()
