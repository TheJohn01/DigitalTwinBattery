"""Report: a techno-economic assessment following the framework of ISO/TS 14076:2025.

build_tea_report() fills the phases of ISO/TS 14076 (clause 6) with the results of one
dashboard run, after an abstract:
  1. Goal and scope definition      (6.2)
  2. Technical analysis             (6.3)
  3. Economic analysis              (6.4; life-cycle costing as in IEC 60300-3-3 and
                                     ISO 15686-5)
  4. Life cycle assessment          (6.5; summary of the screening LCA)
  5. Sensitivity analysis           (6.6)
  6. Interpretation (TEA with LCA)  (6.7)
  7. Documentation                  (7)
Only the published contents of these standards were available; the report follows their
structure but conformity has not been checked, and the study has not been reviewed.
"""
from datetime import date

import numpy as np

from . import __version__
from .chemistry import CHEMISTRIES
from .economics import (GRID_FEE_EXEMPT_UNTIL, INFLATION, LAZARD_WACC, START_YEAR,
                        TAX_LOSS_CAP, calculate_tea, sensitivity,
                        tea_documentation)
from .report_doc import Report

STATEMENT = ("A techno-economic assessment following the framework of ISO/TS 14076:2025, "
             "not critically reviewed")

REFERENCES = [
    "ISO/TS 14076:2025. Environmental management - Environmental techno-economic assessment - "
    "Principles, requirements and guidance.",
    "IEC 60300-3-3:2017. Dependability management - Part 3-3: Application guide - Life cycle "
    "costing.",
    "ISO 15686-5:2017. Buildings and constructed assets - Service life planning - Part 5: "
    "Life-cycle costing.",
    "IEC 62933-2-1. Electrical energy storage (EES) systems - Part 2-1: Unit parameters and "
    "testing methods - General specification.",
    "Cole W., Ramasamy V., Olmez Turan M. (2025). Cost Projections for Utility-Scale Battery "
    "Storage: 2025 Update. NREL/TP-6A40-93281.",
    "Benchmark Mineral Intelligence (2025). Lithium Ion Battery Cell Price Assessment, June 2025.",
    "Keiner D. et al. (2026). Sodium-ion battery cost projections and their impact on the global "
    "energy system transition until 2050. Journal of Energy Storage 146, 119861.",
    "BloombergNEF (2025). Battery price survey, December 2025.",
    "Lazard (2021). Lazard's Levelized Cost of Storage Analysis, version 7.0.",
    "Steffen B. (2020). Estimating the cost of capital for renewable energy projects. Energy "
    "Economics 88, 104783.",
    "Viswanathan V. et al. (2018). Snohomish PUD MESA-1: An assessment of battery technical "
    "performance. PNNL-27237.",
    "Schimpe M. et al. (2018). Energy efficiency evaluation of a stationary lithium-ion battery "
    "container storage system. Applied Energy 210, 211-229.",
    "Dong Q. et al. (2023). Cost, energy, and carbon footprint benefits of second-life electric "
    "vehicle battery use. iScience 26, 107195.",
    "OMIE. Day-ahead market, hourly marginal prices of the Portuguese zone.",
    "ERSE (2025). Regulamento Tarifário do setor elétrico (Regulamento n.º 1218/2025), art. 56; "
    "Diretiva n.º 10/2025; Orientação n.º 1/2026.",
    "EY (2025). Tax Alert: Proposta de Lei do Orçamento do Estado para 2026.",
    "PwC Worldwide Tax Summaries. Portugal: Corporate - Deductions (reviewed 24 July 2026).",
    "Ordem dos Contabilistas Certificados (2023). Amortização e depreciação, parecer PT27497.",
]


def _n(x, d=0):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    return f"{x:,.{d}f}"


def _eur(x, d=0):
    if x is None or not np.isfinite(x):
        return "n/a"
    return f"{'-' if x < 0 else ''}€{abs(x):,.{d}f}"


LABELS = {"capex_eur_kwh": "System cost, CAPEX (€/kWh)", "capacity_kwh": "Pack size (kWh)",
          "electricity_price_eur_kwh": "Mean buying price (€/kWh, 2025)",
          "spread_eur_kwh": "Mean spread, selling - buying (€/kWh, 2025)",
          "round_trip_eff": "Round-trip efficiency", "dod": "Depth of discharge",
          "cycles_per_year": "Cycles per year", "years": "Project lifetime (years)",
          "wacc_nominal": "Discount rate, nominal", "om_eur_kwh_yr": "O&M (€/kWh per year)",
          "warranty_pct_capex": "Warranty (share of CAPEX per year)",
          "grid_fee_eur_kwh_and_eur_kw_day_from_2030":
              "Grid fees from 2030 (€/kWh, €/kW per day)",
          "income_tax_rate": "Corporate income tax (IRC)",
          "tax_depreciation_rate": "Tax depreciation rate (per year)",
          "tax_loss_cap": "Tax losses: share of taxable income they can offset",
          "retire_below": "Retirement threshold (capacity)"}


def build_tea_report(chemistry, run, tea_inputs, prices, fee_case, lca_ind=None, fmt="pdf"):
    """Return the TEA report as PDF bytes (fmt="pdf") or Word bytes (fmt="docx").

    run: settings and simulated values of the dashboard run (as for the LCA report).
    tea_inputs: the inputs of calculate_tea (including soh_curve).
    prices: dict with source, first, last, days, days_used, profitable_days, margin
            (None if fixed prices were used).
    lca_ind: LCA indicators of the same run (lca_report.lca_results(...)["ind"]), or None."""
    c = CHEMISTRIES[chemistry]
    i = tea_inputs
    tea = calculate_tea(**i)
    table = tea["Table"]
    sens = sensitivity(i)
    q = np.asarray(i["soh_curve"], dtype=float)
    retire = i.get("retire_below", 0.70)
    below = np.flatnonzero(~(q >= retire))
    cycles_to_eol = int(below[0]) if len(below) else None
    rte, dod, cpy = i["round_trip_eff"], i.get("dod", 1.0), i["cycles_per_year"]
    buy, sell = i["electricity_price"], i["electricity_price"] + i["spread"]
    margin = sell - buy / rte                       # € per kWh delivered (2025 prices)
    capex_kwh = i["capex_eur_kwh"]
    breakeven = capex_kwh / (margin * dod) if margin > 0 else None
    retired = tea["Retired in year"]
    npv, irr, lcos = tea["NPV [€]"], tea["IRR [%]"], tea["LCOS [€/kWh]"]
    pack = i["capacity_kwh"]
    energy = table["Energy delivered [kWh]"].sum()
    tax_total, fees_total = table["Income tax [€]"].sum(), table["Grid fees [€]"].sum()
    end_year = START_YEAR + int(i.get("years", 15)) - 1

    doc = Report(f"TEA - {chemistry}", STATEMENT)
    doc.h1(f"Techno-economic assessment of a battery for energy arbitrage: {c['label']}")
    doc.p(f"<b>{STATEMENT}.</b>", "box")
    doc.p(f"Generated {date.today().isoformat()} by Battery Digital Twin v{__version__} from "
          "one simulation run. This is a model report (mock-up) for a student project: every "
          "number comes from the simulation, from the cited literature or from an assumption "
          "marked as such (section 7).", "small")

    # Abstract ------------------------------------------------------------------------
    doc.h1("Abstract")
    verdict = ("positive" if npv > 0 else "negative")
    doc.p(
        f"A {pack:g} kWh {chemistry} battery buys electricity on the Portuguese day-ahead "
        f"market in the cheapest hours of each day and sells it in the dearest hours, "
        f"{cpy:,.0f} cycles a year, from {START_YEAR}. Its capacity fade comes from a physics "
        "model combined with empirical ageing models fitted to published cell tests; it is "
        f"retired when its capacity falls below {100 * retire:.0f} %, which happens in year "
        f"{retired if retired else 'n/a (not within the project)'}. With a sourced system "
        f"cost of {_eur(capex_kwh)}/kWh ({_eur(tea['CAPEX [€]'])}), the net present value at "
        f"a {100 * i.get('wacc', 0.074):.1f} % discount rate is <b>{_eur(npv)}</b> "
        f"({verdict}); the levelised cost of storage is {_eur(lcos, 3)} per kWh delivered "
        "and the internal rate of return "
        f"{'%.1f %%' % irr if np.isfinite(irr) else 'is not defined'}.")
    doc.p(
        "<b>Context: why the NPV of battery arbitrage is often negative.</b> (1) The margin "
        f"per cycle is small compared with the investment. In this run the daily cycle buys "
        f"at a mean of {_eur(1000 * buy)}/MWh and sells at {_eur(1000 * sell)}/MWh; after "
        f"the round-trip losses ({100 * rte:.0f} % efficiency) it earns {_eur(margin, 3)} per "
        f"kWh delivered. Recovering the system cost alone, without discounting, operation or "
        f"tax, would take about {_n(breakeven)} full cycles. (2) The battery does not last "
        f"that long: it reaches {100 * retire:.0f} % capacity after "
        f"{_n(cycles_to_eol) if cycles_to_eol else 'more than the modelled'} cycles, and the "
        "energy it can sell shrinks as it fades. (3) The investment is paid at the start and "
        "the income arrives over years, so discounting lowers the value of the income. "
        "(4) Losses in the cell, inverter and auxiliary systems (PNNL measured 83 % at the grid "
        "against 91 % without auxiliaries) mean that more energy is bought than sold. "
        "(5) Arbitrage is only one of several revenue streams: in Lazard's 2021 California "
        "case study, a standalone battery with a 23.7 % project IRR earned only $747 of its "
        "$2,771/kW revenue from energy arbitrage, the rest from resource adequacy (capacity), "
        "frequency regulation and reserves. Commercial projects therefore stack services; "
        "this assessment values arbitrage alone, so it is a lower bound for a real project.")
    doc.p(
        "Cell, inverter and installation costs fall quickly (BloombergNEF: stationary packs at "
        "$70/kWh in 2025), so results depend strongly on the year of the cost data. "
        "Every input, its source and the remaining assumptions are listed in section 7.",
        "small")

    # 1 Goal and scope ----------------------------------------------------------------
    doc.h1("1. Goal and scope definition (ISO/TS 14076, 6.2)")
    doc.h2("1.1 Goal")
    doc.p(
        "<b>Intended application:</b> estimate the profitability and cost of stored energy of "
        f"the simulated battery in day-ahead arbitrage, and show which inputs drive them. "
        "<b>Intended audience:</b> the project team and supervisors (internal). The study is "
        "not intended for investment decisions or public comparisons.")
    doc.h2("1.2 Basis of production, functional unit and reference flow")
    doc.p(
        f"<b>Basis of production (ISO/TS 14076, 4.3):</b> one battery system of {pack:g} kWh "
        f"usable energy, charging at {run['c_charge']:g}C and discharging at "
        f"{run['c_discharge']:g}C, {cpy:,.0f} cycles a year. <b>Functional unit:</b> 1 kWh of "
        "energy delivered over the service life, the same as in the screening LCA. "
        f"<b>Reference flow:</b> {_n(energy)} kWh delivered over the project "
        f"({START_YEAR}-{end_year}) by one system.")
    doc.h2("1.3 System boundary and time horizon")
    doc.table([
        ["Element", "Included?", "How"],
        ["Battery system (cells, power electronics, enclosure, installation)", "Yes",
         "System cost, NREL 2025 + Benchmark cell prices"],
        ["Electricity bought and sold", "Yes", "OMIE day-ahead prices, Portugal"],
        ["Operation and maintenance, warranty", "Yes", "Lazard LCOS 7.0"],
        ["Grid access tariffs and system charges", "Yes",
         f"ERSE: exempt until {GRID_FEE_EXEMPT_UNTIL}; afterwards: {fee_case}"],
        ["Corporate income tax", "Yes", "IRC rates of the 2026 State Budget, PwC deductions"],
        ["Capacity fade, retirement", "Yes", "Physics and ageing models (section 2)"],
        ["Ancillary services, capacity payments, intraday trading", "No", "Not modelled"],
        ["Disposal or recycling cost or value", "No", "No source"],
        ["Financing structure (debt and equity separately)", "No",
         "One discount rate for the whole project"],
    ], [6.5, 2.2, 7.8])
    doc.p(
        f"Time horizon: {int(i.get('years', 15))} years ({START_YEAR}-{end_year}). Currency: "
        f"nominal euro; 2025 prices rise by {100 * INFLATION:.0f} % a year (ECB inflation "
        "target, assumption) and are discounted at a nominal rate (ISO 15686-5).", "small")

    # 2 Technical analysis -------------------------------------------------------------
    doc.h1("2. Technical analysis (ISO/TS 14076, 6.3)")
    doc.table([
        ["Quantity", "Value", "Source"],
        ["Chemistry", c["label"], "Setting"],
        ["Physics model", run["model"], "PyBaMM (Sulzer et al. 2021)"],
        ["Cell capacity / energy",
         f"{_n(run['cell_capacity_ah'], 2)} Ah / {_n(run['cell_energy_wh'], 2)} Wh",
         "Simulated"],
        ["Ambient / cycling temperature, cooling",
         f"{run['ambient_c']:g} / {run['cycling_c']:g} °C, {run['cooling']}", "Setting"],
        ["Mean cell temperature while cycling", f"{_n(run['mean_cell_temp'], 1)} °C",
         "Simulated"],
        ["Cycles to 80 % capacity", _n(run["cycles_to_80"]), "Empirical ageing model"],
        [f"Cycles to {100 * retire:.0f} % (retirement)",
         _n(cycles_to_eol) if cycles_to_eol else "beyond the data", "Empirical ageing model"],
        ["Depth of discharge", f"{100 * dod:.0f} %", "Simulated cycle"],
        ["Round-trip efficiency (whole system)", f"{100 * rte:.1f} %",
         "Simulated cell efficiency x 83/91 (PNNL-27237); IEC 62933-2-1 definition"],
    ], [5.5, 4.5, 6.5])
    if prices:
        doc.p(
            f"<b>Dispatch.</b> For each day of the OMIE price file ({prices['source']}, "
            f"{prices['first']} to {prices['last']}, {prices['days']} days), the battery finds "
            "its best single cycle with perfect foresight of that day: it charges in the "
            "cheapest hours before some hour and discharges in the dearest hours after it. It "
            f"uses the {prices['days_used']} best days; {prices['profitable_days']} days are "
            f"profitable. Mean buying price {_eur(1000 * buy)}/MWh, selling price "
            f"{_eur(1000 * sell)}/MWh, margin {_eur(margin, 3)} per kWh delivered.")
    else:
        doc.p("<b>Dispatch.</b> No hourly price file was available: a fixed buying price of "
              f"{_eur(buy, 3)}/kWh and selling price of {_eur(sell, 3)}/kWh were used "
              "(assumptions).")

    # 3 Economic analysis --------------------------------------------------------------
    doc.h1("3. Economic analysis (ISO/TS 14076, 6.4)")
    doc.h2("3.1 Method")
    doc.p(
        "Life-cycle costing with a cost breakdown into acquisition (CAPEX, year 0), operation "
        "(charging energy, grid fees), maintenance (O&amp;M and warranty) and income tax "
        "(IEC 60300-3-3). Yearly cash flow = revenue - charging cost - O&amp;M - grid fees - "
        "tax; net present value = sum over the years of cash flow / (1 + r)^year. Tax "
        "= rate x (EBITDA - depreciation - losses carried forward, at most "
        f"{100 * TAX_LOSS_CAP:.0f} % of the year's taxable income). LCOS (before tax) = "
        "discounted life-cycle costs / discounted kWh delivered. The battery is retired at its "
        f"first cycle below {100 * retire:.0f} % capacity; afterwards it earns and costs "
        "nothing, and its remaining book value is written off.")
    doc.h2("3.2 Inputs")
    doc_params = tea_documentation(i, chemistry, prices["source"] if prices else None)
    rows = [["Parameter", "Value", "Source or status"]]
    for name, (value, source) in doc_params["parameters"].items():
        if isinstance(value, float):
            value = f"{value:.4g}"
        rows.append([LABELS.get(name, name.replace("_", " ")), value, source])
    doc.table(rows, [5, 3.5, 8])
    doc.h2("3.3 Cash flows by year (nominal €)")
    show = table[(table["Energy delivered [kWh]"] > 0) | (table["Year"] <= 1)]
    rows = [["Year", "Energy out (kWh)", "Revenue", "Charging", "O&amp;M", "Grid fees",
             "Tax", "Cash flow"]]
    rows.append(["0 (CAPEX)", "", "", "", "", "", "", _eur(-tea["CAPEX [€]"])])
    for _, r in show.iterrows():
        rows.append([f"{int(r['Year'])} ({int(r['Calendar year'])})",
                     _n(r["Energy delivered [kWh]"]), _eur(r["Revenue [€]"]),
                     _eur(r["Charging cost [€]"]), _eur(r["O&M and warranty [€]"]),
                     _eur(r["Grid fees [€]"]), _eur(r["Income tax [€]"]),
                     _eur(r["Cash flow [€]"])])
    rows.append(["Total", _n(energy), _eur(table["Revenue [€]"].sum()),
                 _eur(table["Charging cost [€]"].sum()),
                 _eur(table["O&M and warranty [€]"].sum()), _eur(fees_total),
                 _eur(tax_total), _eur(tea["Cash flow [€]"].sum())])
    doc.table(rows, [2.4, 2.2, 1.9, 1.9, 1.8, 1.8, 1.6, 2.4])
    if retired:
        doc.p(f"Years after {START_YEAR + retired - 1} are zero: the battery is retired in year "
              f"{retired}.", "small")
    doc.h2("3.4 Results")
    doc.table([
        ["Indicator", "Value"],
        ["Investment (CAPEX)", _eur(tea["CAPEX [€]"])],
        ["Net present value (after tax)", _eur(npv)],
        ["Internal rate of return", f"{irr:.1f} %" if np.isfinite(irr) else "not defined"],
        ["Discounted payback", f"{tea['Discounted payback [years]']:.0f} years"
         if np.isfinite(tea["Discounted payback [years]"]) else "not within the project"],
        ["Levelised cost of storage (before tax)", f"{_eur(lcos, 3)}/kWh"],
        ["Retired in year", str(retired) if retired else "not within the project"],
        ["Income tax paid / grid fees paid", f"{_eur(tax_total)} / {_eur(fees_total)}"],
        ["Break-even cycles for CAPEX alone (undiscounted)", _n(breakeven)],
    ], [9, 7.5])

    # 4 LCA ----------------------------------------------------------------------------
    doc.h1("4. Life cycle assessment (ISO/TS 14076, 6.5)")
    if lca_ind:
        doc.p(
            "The environmental part is the screening LCA of the same run (separate report, "
            "ISO 14040/14044, not critically reviewed), with the same functional unit: carbon "
            f"footprint {_n(lca_ind['Carbon footprint, regulation scope [g CO2eq/kWh delivered]'], 1)} "
            "g CO2eq/kWh (regulation scope) and "
            f"{_n(lca_ind['Carbon footprint incl. use-phase losses [g CO2eq/kWh delivered]'], 1)} "
            "g CO2eq/kWh including the battery's losses; water consumption "
            f"{_n(lca_ind['Water consumption [L/kWh delivered]'], 2)} L/kWh; freshwater "
            f"ecotoxicity {_n(lca_ind['Freshwater ecotoxicity [g 1,4-DCB eq/kWh delivered]'], 2)} "
            "g 1,4-DCB eq/kWh.")
    else:
        doc.p("Not included in this report (see the screening LCA report).")

    # 5 Sensitivity --------------------------------------------------------------------
    doc.h1("5. Sensitivity analysis (ISO/TS 14076, 6.6)")
    rows = [["Input changed by ±20 % (one at a time)", "NPV change at -20 %", "at +20 %"]]
    for _, r in sens.iterrows():
        rows.append([r["Parameter"], _eur(r["ΔNPV at -20% [€]"]), _eur(r["ΔNPV at +20% [€]"])])
    doc.table(rows, [8, 4.25, 4.25])
    doc.p("Scenarios (one change at a time from the base case):", "small")
    scen = [("Base case", {}),
            ("Retired at 50 % (end of the ageing data)", {"retire_below": 0.5}),
            (f"Discount rate {100 * LAZARD_WACC:.1f} % (Lazard financing)", {"wacc": LAZARD_WACC}),
            ("No income tax", {"income_tax": False}),
            ("System cost -30 %", {"capex_eur_kwh": 0.7 * capex_kwh})]
    rows = [["Scenario", "NPV", "LCOS (€/kWh)"]]
    for name, change in scen:
        r = calculate_tea(**dict(i, **change))
        rows.append([name, _eur(r["NPV [€]"]), _eur(r["LCOS [€/kWh]"], 3)])
    doc.table(rows, [9, 3.75, 3.75])

    # 6 Interpretation -----------------------------------------------------------------
    doc.h1("6. Interpretation: TEA combined with LCA (ISO/TS 14076, 6.7)")
    combined = [["Indicator per kWh delivered", "Value"],
                ["Levelised cost of storage", f"{_eur(lcos, 3)}/kWh"]]
    if lca_ind:
        combined.append(["Carbon footprint (regulation scope)",
                         f"{_n(lca_ind['Carbon footprint, regulation scope [g CO2eq/kWh delivered]'], 1)} g CO2eq/kWh"])
    doc.table(combined, [9, 7.5])
    top = sens.assign(span=(sens["ΔNPV at +20% [€]"] - sens["ΔNPV at -20% [€]"]).abs()) \
        .sort_values("span", ascending=False)["Parameter"].head(3).tolist()
    doc.p(
        f"<b>Significant issues.</b> The inputs that move the NPV most are: {', '.join(top)}. "
        "Both cost and carbon per kWh delivered fall when the battery lasts longer, so the "
        "operating conditions that slow ageing (cooling, moderate charge rates) improve both. "
        "<b>Limitations.</b> One year of prices is repeated every year with perfect daily "
        "foresight (an upper bound for arbitrage); costs are US and global values converted to "
        "euro; the discount rate is for onshore wind; the grid-fee rule after "
        f"{GRID_FEE_EXEMPT_UNTIL} is not known; ancillary services are not valued. "
        "<b>Conclusion.</b> "
        + ("Day-ahead arbitrage alone does not pay back this battery; stacking other services, "
           "a lower system cost or a longer cycle life would be needed." if npv < 0 else
           "Under these inputs the battery pays back its investment; the sensitivity table "
           "shows how robust that is."))

    # 7 Documentation ------------------------------------------------------------------
    doc.h1("7. Documentation (ISO/TS 14076, 7)")
    doc.p(f"<b>{STATEMENT}.</b> Method: {doc_params['method']} Functional unit: "
          f"{doc_params['functional_unit']}.")
    doc.p("<b>Assumptions (not sourced):</b> " + "; ".join(doc_params["assumptions"]) + ".")
    doc.p("The yearly cash flows (CSV) and all inputs with their sources (JSON) can be "
          f"downloaded from the dashboard. Program: Battery Digital Twin v{__version__}.",
          "small")
    doc.h2("References")
    for ref in REFERENCES:
        doc.p(f"- {ref}", "small")
    return doc.docx() if fmt == "docx" else doc.pdf()
