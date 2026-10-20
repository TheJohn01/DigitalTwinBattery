"""Every published source the program uses, shown in the dashboard's "Sources" tab.

Each entry: area, reference, what the program uses it for, and a link (empty if none).
"""

SOURCES = [
    # --- Physics model ------------------------------------------------------------------
    {"Area": "Physics model",
     "Reference": "Sulzer V. et al. (2021). Python Battery Mathematical Modelling (PyBaMM). "
                  "Journal of Open Research Software 9(1), 14.",
     "Used for": "Electrochemical and thermal simulation (SPMe and DFN models)",
     "Link": "https://doi.org/10.5334/jors.309"},
    {"Area": "Physics model",
     "Reference": "Chen C.-H. et al. (2020). Development of experimental techniques for "
                  "parameterization of multi-scale lithium-ion battery models. J. Electrochem. "
                  "Soc. 167, 080534.",
     "Used for": "NMC cell parameters (LG M50)",
     "Link": "https://doi.org/10.1149/1945-7111/ab9050"},
    {"Area": "Physics model",
     "Reference": "Prada E. et al. (2013). A simplified electrochemical and thermal aging model "
                  "of LiFePO4-graphite Li-ion batteries. J. Electrochem. Soc. 160, A616.",
     "Used for": "LFP / graphite electrochemistry of the LFP cell (LFP diffusion and kinetics, "
                 "conductivities); four values refitted, see lfp_blade_params.py",
     "Link": "https://doi.org/10.1149/2.053304jes"},
    {"Area": "Physics model",
     "Reference": "Gorsch J. et al. (2025). Contrasting a BYD Blade prismatic cell and Tesla "
                  "4680 cylindrical cell with a teardown analysis of design and performance. "
                  "Cell Rep. Phys. Sci. 6, 102453 (CC BY 4.0).",
     "Used for": "LFP cell: commercial BYD Blade BEV cell (135 Ah) - geometry, coatings, "
                 "graphite mass, capacity, energy, mass and volume",
     "Link": "https://doi.org/10.1016/j.xcrp.2025.102453"},
    {"Area": "Physics model",
     "Reference": "Liu A. et al. (2025). Design and performance of the BYD LFP/graphite 4680 "
                  "cylindrical cell. J. Electrochem. Soc. 172, 110536 (CC BY 4.0).",
     "Used for": "LFP cell: charge-transfer resistance and rate test of BYD's 4680 LFP cell "
                 "(fitted); its pulse resistances check the model",
     "Link": "https://doi.org/10.1149/1945-7111/ae1e33"},
    {"Area": "Physics model",
     "Reference": "Gray R., Vagg C. (2026). 280 Ah prismatic LFP cell: characterisation and "
                  "aging data. Zenodo (CC BY 4.0).",
     "Used for": "LFP cell: OCV level, hysteresis and entropy coefficient (fitted); "
                 "temperature dependence and C/10 curve check the model; 700 cycles at 1C "
                 "check the LFP ageing model",
     "Link": "https://doi.org/10.5281/zenodo.20813753"},
    {"Area": "Physics model",
     "Reference": "Mohtat P. et al. (2020). Differential expansion and voltage model for Li-ion "
                  "batteries at practical charging rates. J. Electrochem. Soc. 167, 110561.",
     "Used for": "Graphite open-circuit potential of the LFP cell (as shipped with PyBaMM)",
     "Link": "https://doi.org/10.1149/1945-7111/aba5d1"},
    {"Area": "Physics model",
     "Reference": "Schmitt C., Gerle M., Kopljar D., Friedrich K. A. (2023). Full "
                  "parameterization study of a high-energy and a high-power Li-ion cell for "
                  "physicochemical models. J. Electrochem. Soc. 170, 070509 (CC BY 4.0).",
     "Used for": "NCA cell parameters: commercial Samsung INR21700-50E (NCA / graphite-SiOx), "
                 "incl. temperature dependence; measured discharges used to check the model",
     "Link": "https://doi.org/10.1149/1945-7111/ace1a7"},
    {"Area": "Physics model",
     "Reference": "Landesfeind J., Gasteiger H. A. (2019). Temperature and concentration "
                  "dependence of the ionic transport properties of lithium-ion battery "
                  "electrolytes. J. Electrochem. Soc. 166, A3079.",
     "Used for": "NCA and LFP electrolyte transport (LiPF6 in EC:EMC 3:7, as shipped with "
                 "PyBaMM; the NCA cell's EC:DMC data are in the same paper)",
     "Link": "https://doi.org/10.1149/2.0571912jes"},
    {"Area": "Physics model",
     "Reference": "Schneider N., Stapf N., Mehlich C., Biswas A., Birke K. P., Fill A. (2025). "
                  "Towards accurate sodium-ion cell modelling: parametrization and validation "
                  "of a commercial sodium-ion cell incorporating temperature-dependent kinetics. "
                  "J. Electrochem. Soc. 172, 090525 (CC BY 4.0).",
     "Used for": "Sodium-ion cell parameters: commercial Mushang NA18650-1250 (layered oxide / "
                 "hard carbon), incl. temperature dependence and thermal properties; measured "
                 "discharges and temperatures used to check the model",
     "Link": "https://doi.org/10.1149/1945-7111/adfd16"},
    {"Area": "Physics model",
     "Reference": "Rehm M. et al. (2025). Comparing the electrical performance of commercial "
                  "sodium-ion and lithium-iron-phosphate batteries. J. Power Sources 633, "
                  "236290 (CC BY 4.0).",
     "Used for": "Check of the sodium-ion round-trip efficiency (same cell, 10-45 °C)",
     "Link": "https://doi.org/10.1016/j.jpowsour.2025.236290"},
    {"Area": "Physics model",
     "Reference": "O'Kane S. E. J. et al. (2022). Lithium-ion battery degradation: how to "
                  "model it. Phys. Chem. Chem. Phys. 24, 7909.",
     "Used for": "SEI growth activation energy for LFP and NCA (38 kJ/mol)",
     "Link": "https://doi.org/10.1039/D2CP00417H"},
    {"Area": "Physics calibration",
     "Reference": "Kirkaldy N. et al. (2024). Lithium-ion battery degradation: comprehensive "
                  "cycle ageing data and analysis for commercial 21700 cells. J. Power Sources "
                  "603, 234185. Dataset: Zenodo 10637534 (CC-BY-4.0).",
     "Used for": "NMC capacity, SEI growth and self-heating calibration; held-out check of "
                 "the NMC ageing model",
     "Link": "https://doi.org/10.1016/j.jpowsour.2024.234185"},
    # --- Cooling ------------------------------------------------------------------------
    {"Area": "Cooling",
     "Reference": "Incropera F. P., DeWitt D. P. et al. Fundamentals of Heat and Mass "
                  "Transfer, Table 1.1 (typical convection coefficients) and Table A.4 (air).",
     "Used for": "Ranges behind the three cooling options; the averages used are modelling "
                 "assumptions within those ranges. Air properties for the pack row",
     "Link": ""},
    # --- Ageing models ------------------------------------------------------------------
    {"Area": "Ageing (all lithium)",
     "Reference": "NREL BLAST-Lite, battery lifetime models (Gasper P. et al.), BSD-3-Clause.",
     "Used for": "Calendar ageing of NMC, LFP and NCA; LFP cycling model",
     "Link": "https://github.com/NREL/BLAST-Lite"},
    {"Area": "Ageing: NMC",
     "Reference": "Truong Bui et al. (2021), IEEE: LG M50 ageing data used by BLAST-Lite.",
     "Used for": "NMC calendar ageing (through BLAST-Lite)",
     "Link": ""},
    {"Area": "Ageing: NMC",
     "Reference": "Luh M., Blank T. (2024). Comprehensive battery aging dataset: capacity and "
                  "impedance fade measurements of a lithium-ion NMC/C-SiO cell. Scientific "
                  "Data 11, 1004. Dataset: doi 10.35097/1947 (CC BY 4.0).",
     "Used for": "NMC cycling fit: effect of charge rate (1/3-5/3C) and temperature "
                 "(0-40 °C), i.e. lithium plating",
     "Link": "https://doi.org/10.1038/s41597-024-03831-x"},
    {"Area": "Ageing: NMC, NCA, LFP",
     "Reference": "Preger Y. et al. (2020). Degradation of commercial lithium-ion cells as a "
                  "function of chemistry and cycling conditions. J. Electrochem. Soc. 167, "
                  "120532.",
     "Used for": "NCA cycling fit (same Panasonic cell); NMC depth of discharge and level; "
                 "LFP (A123) level for the fast-charge fit",
     "Link": "https://doi.org/10.1149/1945-7111/abae37"},
    {"Area": "Ageing: NMC",
     "Reference": "Wittman R. M. et al. (2023). Characterization of cycle-aged commercial NMC "
                  "and NCA lithium-ion cells: I. Temperature-dependent degradation. "
                  "J. Electrochem. Soc. 170, 120538.",
     "Used for": "NMC cycling fit (cycles to 80 % at 15, 25 and 35 °C)",
     "Link": "https://doi.org/10.1149/1945-7111/ad1450"},
    {"Area": "Ageing: NMC, LFP",
     "Reference": "Ohneseit S. et al. (2025). Aging behavior beyond SOH 80: an experimental "
                  "aging study on commercial lithium-ion batteries with different cathode "
                  "materials. Batteries & Supercaps.",
     "Used for": "NMC cycling fit; LFP cycling level (21700 cells, 20 °C)",
     "Link": "https://doi.org/10.1002/batt.202400713"},
    {"Area": "Ageing: LFP",
     "Reference": "Severson K. A. et al. (2019). Data-driven prediction of battery cycle life "
                  "before capacity degradation. Nature Energy 4, 383. Supplementary Table 9.",
     "Used for": "LFP fast-charging factor (124 A123 cells, 3.6-8C charging); with the "
                 "cycle-by-cycle capacities: check of the shape of the LFP curve and of the "
                 "measurement update",
     "Link": "https://doi.org/10.1038/s41560-019-0356-8"},
    {"Area": "Ageing: LFP",
     "Reference": "Naumann M. et al. (2018, 2020), J. Energy Storage and J. Power Sources; "
                  "model identification: Gasper P. et al. (2022), J. Electrochem. Soc.",
     "Used for": "LFP ageing model (Sony-Murata 18650, through BLAST-Lite)",
     "Link": "https://doi.org/10.1149/1945-7111/ac86a8"},
    {"Area": "Ageing: NCA",
     "Reference": "Keil P. et al. (2016). Calendar aging of lithium-ion batteries. "
                  "J. Electrochem. Soc. 163, A1872.",
     "Used for": "NCA calendar ageing (through BLAST-Lite)",
     "Link": "https://doi.org/10.1149/2.0411609jes"},
    {"Area": "Ageing: sodium-ion",
     "Reference": "Liu S., Li K., Yu J., Liu K. (2026). Characterisation and performance "
                  "evaluation of early-generation commercial sodium-ion batteries. Applied "
                  "Energy 412, 127687.",
     "Used for": "Sodium-ion capacity loss per cycle: 0.05 % default (layered-oxide NFM 18650 "
                 "cells, full cycles, Fig. 23); about 0.008 % for their Cu-Fe-Mn oxide cell",
     "Link": "https://doi.org/10.1016/j.apenergy.2026.127687"},
    {"Area": "Ageing: sodium-ion",
     "Reference": "Carter et al. (2025). Energies 18, 661.",
     "Used for": "Best commercial sodium-ion cells: under 0.01 % loss per cycle",
     "Link": ""},
    {"Area": "Ageing: sodium-ion",
     "Reference": "Rehm M., Bahrke J., Natterer J., Milutinovic L., Roehrer F., Jossen A. "
                  "(2026). Aging of commercial sodium-ion batteries with layered oxides: how to "
                  "measure and analyze it? EES Batteries (CC BY 3.0).",
     "Used for": "Same cell as the physics model, 20-80 % cycling at 1C: 3-9 % loss in over "
                 "3,400 cycles (context for the default)",
     "Link": "https://doi.org/10.1039/D5EB00221D"},
    {"Area": "Ageing: sodium-ion",
     "Reference": "Klick et al. (2025). Batteries & Supercaps.",
     "Used for": "No temperature dependence for sodium-ion (similar fade at 25 and 40 °C)",
     "Link": ""},
    # --- Environment (screening LCA) ----------------------------------------------------
    {"Area": "Environment (LCA)",
     "Reference": "Degen F., Mitterfellner M., Kampker A. (2024). Comparative life cycle "
                  "assessment of lithium-ion, sodium-ion, and solid-state battery cells for "
                  "electric vehicles. Journal of Industrial Ecology. Ecoinvent 3.10, ReCiPe 2016.",
     "Used for": "Production climate change, water consumption and freshwater ecotoxicity per "
                 "kWh of cell, for NCA, NMC811, LFP and sodium-ion (read from Fig. 6 and 7)",
     "Link": "https://doi.org/10.1111/jiec.13594"},
    {"Area": "Environment (LCA)",
     "Reference": "Andreasi Bassi S. et al. (2025). Rules for the calculation of the Carbon "
                  "Footprint of industrial Batteries without external storage (CFB-IND). JRC, "
                  "EUR 40286.",
     "Used for": "Functional unit (1 kWh delivered), total energy over the service life, "
                 "end of service life at 70 % or more, use phase excluded",
     "Link": "https://doi.org/10.2760/6346639"},
    {"Area": "Environment (LCA)",
     "Reference": "Regulation (EU) 2023/1542 concerning batteries and waste batteries, "
                  "Article 7 and Annex II.",
     "Used for": "Carbon footprint scope and functional unit",
     "Link": "https://eur-lex.europa.eu/eli/reg/2023/1542/oj"},
    {"Area": "Environment (LCA)",
     "Reference": "JRC (2023). Harmonised rules for the calculation of the Carbon Footprint of "
                  "Electric Vehicle Batteries (CFB-EV).",
     "Used for": "Functional unit for the electric-vehicle case",
     "Link": "https://eplca.jrc.ec.europa.eu/GRB-CBF_CarbonFootprintRules-EV.pdf"},
    {"Area": "Environment (LCA)",
     "Reference": "Llamas-Orozco J. A. et al. (2023). Estimating the environmental impacts of "
                  "global lithium-ion battery supply chain. PNAS Nexus 2(11), pgad361.",
     "Used for": "Cross-check of production climate change at pack level (LCA report)",
     "Link": "https://doi.org/10.1093/pnasnexus/pgad361"},
    {"Area": "Environment (LCA)",
     "Reference": "Emilsson E., Dahllöf L. (2019). Lithium-ion vehicle battery production - "
                  "status 2019. IVL Swedish Environmental Research Institute, report C 444.",
     "Used for": "Cross-check of production climate change; share of pack components "
                 "(LCA report, cut-off criteria)",
     "Link": ""},
    {"Area": "Environment (LCA)",
     "Reference": "ISO 14040:2006 and ISO 14044:2006 (with amendments). Environmental "
                  "management - Life cycle assessment.",
     "Used for": "Structure of the screening LCA report (not critically reviewed)",
     "Link": ""},
    # --- Economics (TEA) --------------------------------------------------------------
    {"Area": "Economics (TEA)",
     "Reference": "OMIE, Iberian day-ahead electricity market: hourly marginal prices of the "
                  "Portuguese zone, downloaded with the OMIEData package "
                  "(scripts/download_omie_prices.py).",
     "Used for": "Buying and selling prices of the daily arbitrage cycle",
     "Link": "https://www.omie.es"},
    {"Area": "Economics (TEA)",
     "Reference": "Cole W., Ramasamy V., Olmez Turan M. (2025). Cost Projections for "
                  "Utility-Scale Battery Storage: 2025 Update. NREL/TP-6A40-93281.",
     "Used for": "System cost of a 4-hour battery ($321/kWh, 2025 mid), 15-year lifetime, "
                 "85 % round-trip efficiency",
     "Link": "https://docs.nrel.gov/docs/fy25osti/93281.pdf"},
    {"Area": "Economics (TEA)",
     "Reference": "NREL Annual Technology Baseline (ATB), Utility-Scale Battery Storage.",
     "Used for": "Cross-check of the system cost and fixed O&M projections",
     "Link": "https://atb.nlr.gov/electricity/2025/utility-scale_battery_storage"},
    {"Area": "Economics (TEA)",
     "Reference": "ISO/TS 14076:2025. Environmental management - Environmental techno-economic "
                  "assessment - Principles, requirements and guidance.",
     "Used for": "Framework of the TEA: goal and scope with the LCA's functional unit, "
                 "technical and economic analysis, sensitivity, combined interpretation, "
                 "documentation of all parameters (structure from the published contents)",
     "Link": "https://www.iso.org/standard/61119.html"},
    {"Area": "Economics (TEA)",
     "Reference": "IEC 60300-3-3:2017. Dependability management - Part 3-3: Application guide "
                  "- Life cycle costing. ISO 15686-5:2017. Buildings and constructed assets - "
                  "Service life planning - Part 5: Life-cycle costing.",
     "Used for": "Life-cycle cost breakdown (acquisition, operation, maintenance, taxes), "
                 "nominal cash flows discounted at a nominal rate, net present value",
     "Link": "https://webstore.iec.ch/en/publication/31206"},
    {"Area": "Economics (TEA)",
     "Reference": "IEC 62933-2-1. Electrical energy storage (EES) systems - Part 2-1: Unit "
                  "parameters and testing methods - General specification.",
     "Used for": "Round-trip efficiency defined for the whole system at the grid connection",
     "Link": ""},
    {"Area": "Economics (TEA)",
     "Reference": "Benchmark Mineral Intelligence (2025). Lithium Ion Battery Cell Price "
                  "Assessment, June 2025.",
     "Used for": "Cell price difference between chemistries: weighted averages LFP $50.2, "
                 "NCM $66.0, NCA $71.7/kWh",
     "Link": ""},
    {"Area": "Economics (TEA)",
     "Reference": "Keiner D. et al. (2026). Sodium-ion battery cost projections and their "
                  "impact on the global energy system transition until 2050. J. Energy "
                  "Storage 146, 119861.",
     "Used for": "Sodium-ion cell cost equal to LFP (about 93 €/kWh in 2023)",
     "Link": "https://doi.org/10.1016/j.est.2025.119861"},
    {"Area": "Economics (TEA)",
     "Reference": "Viswanathan V. et al. (2018). Snohomish PUD MESA-1: An assessment of "
                  "battery technical performance. PNNL-27237.",
     "Used for": "Whole-system efficiency: 83 % with, 91 % without auxiliary loads at 1C "
                 "(factor 83/91 on the simulated cell efficiency)",
     "Link": "https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-27237.pdf"},
    {"Area": "Economics (TEA)",
     "Reference": "Schimpe M. et al. (2018). Energy efficiency evaluation of a stationary "
                  "lithium-ion battery container storage system. Applied Energy 210, 211-229.",
     "Used for": "Context: power electronics and auxiliaries dominate the losses at low "
                 "utilisation (70-80 % conversion efficiency in that system)",
     "Link": "https://doi.org/10.1016/j.apenergy.2017.10.129"},
    {"Area": "Economics (TEA)",
     "Reference": "ERSE (2025). Regulamento Tarifário do setor elétrico (Regulamento "
                  "n.º 1218/2025), article 56; ERSE Diretiva n.º 10/2025 (tariffs for 2026); "
                  "ERSE Orientação n.º 1/2026 (system charges for storage).",
     "Used for": "Grid fees: storage exempt from network access tariffs until the end of "
                 "2029 and from system regulation charges below 10 MVA; 2026 MT and BTE "
                 "access tariffs for the after-2029 options",
     "Link": "https://www.erse.pt"},
    {"Area": "Economics (TEA)",
     "Reference": "EY (2025). Tax Alert: Proposta de Lei do Orçamento do Estado para 2026.",
     "Used for": "Corporate income tax (IRC): 19 % in 2026, 18 % in 2027, 17 % from 2028",
     "Link": ""},
    {"Area": "Economics (TEA)",
     "Reference": "PwC Worldwide Tax Summaries. Portugal: Corporate - Deductions (reviewed "
                  "24 July 2026).",
     "Used for": "Tax depreciation: maximum straight-line rate for electronic equipment, 20 % "
                 "a year; tax losses deductible up to 65 % of a year's taxable income",
     "Link": "https://taxsummaries.pwc.com/portugal/corporate/deductions"},
    {"Area": "Economics (TEA)",
     "Reference": "Ordem dos Contabilistas Certificados (2023). Amortização e depreciação, "
                  "parecer técnico PT27497.",
     "Used for": "Minimum depreciation rate = half the maximum (Decreto Regulamentar 25/2009)",
     "Link": ""},
    {"Area": "Economics (TEA)",
     "Reference": "BloombergNEF (2025). Lithium-ion battery pack prices fall to $108 per "
                  "kilowatt-hour. Battery price survey, December 2025.",
     "Used for": "Stationary pack price ($70/kWh), used to separate the balance of system "
                 "for second life",
     "Link": "https://about.bnef.com/insights/clean-transport/lithium-ion-battery-pack-prices-"
             "fall-to-108-per-kilowatt-hour-despite-rising-metal-prices-bloombergnef/"},
    {"Area": "Economics (TEA)",
     "Reference": "Lazard (2021). Lazard's Levelized Cost of Storage Analysis, version 7.0.",
     "Used for": "Operation and maintenance ($1.53/kWh per year, +2.5 %/year), warranty "
                 "(0.9 % of capital cost per year from year 3); financing used as the high "
                 "discount rate",
     "Link": "https://www.lazard.com"},
    {"Area": "Economics (TEA)",
     "Reference": "Steffen B. (2020). Estimating the cost of capital for renewable energy "
                  "projects. Energy Economics 88, 104783.",
     "Used for": "Discount rate: after-tax WACC for Portugal, 7.4 % (Table 2)",
     "Link": "https://doi.org/10.1016/j.eneco.2020.104783"},
    {"Area": "Economics (TEA)",
     "Reference": "Dong Q. et al. (2023). Cost, energy, and carbon footprint benefits of "
                  "second-life electric vehicle battery use. iScience 26, 107195.",
     "Used for": "Price of a repurposed EV battery ($44-180/kWh; default $72/kWh)",
     "Link": "https://doi.org/10.1016/j.isci.2023.107195"},
    {"Area": "Economics (TEA)",
     "Reference": "European Central Bank euro reference rates, 2025 annual average "
                  "(1.1300 USD per EUR), as published by the Bank of Finland.",
     "Used for": "Converting dollar costs to euro",
     "Link": "https://www.suomenpankki.fi/en/statistics/interest-rates-and-exchange-rates/"
             "exchange-rates/average-annual-exchange-rates-for-the-year-2025/"},
    # --- Digital-twin methods and related open-source projects --------------------------
    {"Area": "Digital-twin methods",
     "Reference": "Thelen A. et al. (2023). A comprehensive review of digital twin - part 2: "
                  "roles of uncertainty quantification and optimization, a battery digital "
                  "twin, and perspectives. Structural and Multidisciplinary Optimization 66, 1. "
                  "Code and data: github.com/acthelen/battery_digital_twin (MIT licence).",
     "Used for": "Cycle-by-cycle capacities of the Severson cells (their copy of the data); "
                 "the idea of choosing when to retire a battery from its predicted curve; the "
                 "measurement update is a simplified version of their particle filter",
     "Link": "https://doi.org/10.1007/s00158-022-03410-x"},
    {"Area": "Digital-twin methods",
     "Reference": "Marin J. (2026). otwin-hybrid: a hybrid digital twin for Li-ion battery "
                  "state of health. Software, Apache-2.0 licence.",
     "Used for": "How the measurement update is tested: forecasting from early cycles only, "
                 "persistence and linear-drift baselines, skill score, end-of-life error; "
                 "log-space fit of the power law",
     "Link": "https://github.com/otwin-core/otwin-hybrid"},
    {"Area": "Digital-twin methods",
     "Reference": "Wang J. et al. (2011). Cycle-life model for graphite-LiFePO4 cells. Journal "
                  "of Power Sources 196(8), 3942-3948.",
     "Used for": "Power-law capacity fade, used as a data-only comparison for the update",
     "Link": "https://doi.org/10.1016/j.jpowsour.2010.11.134"},
    {"Area": "Pack thermal",
     "Reference": "ThermoWeave contributors (2026). ThermoWeave: adaptive spatial "
                  "electrothermal digital twin for battery cooling design. Software, MIT "
                  "licence (docs/model.md, eq. 4).",
     "Used for": "Coolant energy balance along a channel (temperature spread between cells)",
     "Link": "https://github.com/mohammadrezwankhan/thermoweave-battery-digital-twin"},
    # --- Assumptions -------------------------------------------------------------------
    {"Area": "Assumptions (not sourced)",
     "Reference": "Indicative values in chemistry.py, economics.py and the dashboard inputs.",
     "Used for": "Recycling credit, specific energy (pack mass), grid carbon intensity; in "
                 "the TEA: 2 % inflation (ECB target), batteries classed as electronic "
                 "equipment for tax, write-off at retirement, no municipal or state IRC "
                 "surcharges, no disposal cost, start in 2026; pack row: water-glycol 50/50 properties "
                 "(typical data-sheet values) and coolant flow",
     "Link": ""},
]
