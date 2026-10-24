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
                 "electrode sizes, component masses, capacity, energy, volume, and its 1C "
                 "pulse resistance (Fig. 8C, fitted)",
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
    {"Area": "Second life",
     "Reference": "Regulation (EU) 2024/1257 (Euro 7): minimum battery durability of electric "
                  "cars, 80 % up to 5 years or 100,000 km and 72 % up to 8 years or 160,000 km.",
     "Used for": "Check of the car first life before second life",
     "Link": "https://eur-lex.europa.eu/eli/reg/2024/1257/oj"},
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
     "Used for": "SEI growth activation energy for LFP and NCA (38 kJ/mol); lithium plating "
                 "parameters of the detailed NMC model (PyBaMM set OKane2022, LG M50)",
     "Link": "https://doi.org/10.1039/D2CP00417H"},
    {"Area": "Physics calibration",
     "Reference": "Catenaro E., Onori S. (2021). Experimental data of lithium-ion batteries "
                  "under galvanostatic discharge tests at different rates and temperatures of "
                  "operation. Data in Brief 35, 106894 (CC BY 4.0).",
     "Used for": "NMC electrolyte diffusivity factor (LG M50 capacities at 2C and 3C); check "
                 "of the NMC self-heating, capacity and round-trip efficiency at 1-5C",
     "Link": "https://doi.org/10.1016/j.dib.2021.106894"},
    {"Area": "Physics model",
     "Reference": "Drake S. J. et al. (2014). Measurement of anisotropic thermophysical "
                  "properties of cylindrical Li-ion cells. J. Power Sources 252, 298-304.",
     "Used for": "Radial thermal conductivity (0.20 W/mK) for the core-to-can resistance of "
                 "the 21700 cells",
     "Link": "https://doi.org/10.1016/j.jpowsour.2013.11.107"},
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
     "Reference": "Attia P. M. et al. (2022). Review - \"Knees\" in lithium-ion battery aging "
                  "trajectories. J. Electrochem. Soc. 169, 060517.",
     "Used for": "Lithium plating as the most common knee mechanism: the LFP knee is tied "
                 "to fast-charge wear",
     "Link": "https://doi.org/10.1149/1945-7111/ac6d13"},
    {"Area": "Ageing: LFP",
     "Reference": "Severson K. A. et al. (2019). Data-driven prediction of battery cycle life "
                  "before capacity degradation. Nature Energy 4, 383. Supplementary Table 9.",
     "Used for": "LFP fast-charging factor (124 A123 cells, 3.6-8C charging); with the "
                 "cycle-by-cycle capacities: the LFP knee (fitted to the curve shapes) and "
                 "the check of the measurement update",
     "Link": "https://doi.org/10.1038/s41560-019-0356-8"},
    {"Area": "Pack row",
     "Reference": "Baumhöfer T., Brühl M., Rothgang S., Sauer D. U. (2014). Production caused "
                  "variation in capacity aging trend and correlation to initial cell "
                  "performance. J. Power Sources 247, 332-338.",
     "Used for": "Cell-to-cell variation (Pack expander): 48 cells of one lot aged identically "
                 "reached 84 % after 850-1,200 cycles, 7.7 % standard deviation in life",
     "Link": "https://doi.org/10.1016/j.jpowsour.2013.08.108"},
    {"Area": "Ageing: LFP",
     "Reference": "Wheeler W., Venet P., Bultel Y., Sari A. (2025). An ageing study of twenty "
                  "18650 lithium-ion Graphite/LFP cells in first and second life use. "
                  "Scientific Data 12, 392. Data: Recherche Data Gouv, doi 10.57745/OLBXKT.",
     "Used for": "Check of the LFP fade below 80 % (second life): 20 A123 cells aged at 50 °C "
                 "to 31-64 % faded steadily at 70 % depth and bent at full depth or with 2C "
                 "both ways; the model's level at 50 °C (2.3-2.7 times too long a life)",
     "Link": "https://doi.org/10.1038/s41597-025-04712-7"},
    {"Area": "Ageing: LFP",
     "Reference": "Yagci M. C., Richter O., Behmann R., Bessler W. G. (2025). Degradation modes of "
                  "large-format stationary-storage LFP-based lithium-ion cells during calendaric "
                  "and cyclic aging. J. Energy Storage 124, 116774. Data: Zenodo 22939281 "
                  "(CC BY 4.0).",
     "Used for": "LFP heat term LfpAdjusted.K_HOT: 200 Ah cells cycled at 36.5 and 52 °C (50 °C "
                 "cells 2.2 %-points RMS); stored cells at 35/50 °C check the calendar term",
     "Link": "https://doi.org/10.1016/j.est.2025.116774"},
    {"Area": "Ageing: LFP",
     "Reference": "Lam V. et al. (2024). A decade of insights: delving into calendar aging trends "
                  "and implications. Joule. Data: osf.io/ju325 (no licence stated).",
     "Used for": "Check of the LFP calendar term: K2 Energy LFP cells stored 7.5 years at 24 °C "
                 "(model within the cells) and 4 years at 45 °C (model too optimistic)",
     "Link": "https://osf.io/ju325"},
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
     "Used for": "Comparison: other makers' layered-oxide NFM 18650 cells lost 0.05 % per full "
                 "cycle (Fig. 23; the default before the TUM data); about 0.008 % for their "
                 "Cu-Fe-Mn oxide cell",
     "Link": "https://doi.org/10.1016/j.apenergy.2026.127687"},
    {"Area": "Ageing: sodium-ion",
     "Reference": "Carter et al. (2025). Energies 18, 661.",
     "Used for": "Best commercial sodium-ion cells: under 0.01 % loss per cycle",
     "Link": ""},
    {"Area": "Ageing: sodium-ion",
     "Reference": "Rehm M., Bahrke J., Natterer J., Milutinovic L., Roehrer F., Jossen A. "
                  "(2026). Aging of commercial sodium-ion batteries with layered oxides: how to "
                  "measure and analyze it? EES Batteries (CC BY 3.0).",
     "Used for": "Same cell as the physics model, 20-80 % cycling at 1C (data: mediaTUM, "
                 "doi 10.14459/2025mp1837893): sodium-ion fade at partial depth, "
                 "SodiumIon.PARTIAL_FACTOR (after taking out the calendar loss)",
     "Link": "https://doi.org/10.1039/D5EB00221D"},
    {"Area": "Ageing: sodium-ion",
     "Reference": "Bahrke J., Rehm M., Natterer J., Wendlandt C., Jossen A. (2026). Aging data "
                  "for commercial sodium-ion batteries, including check-ups and degradation "
                  "mode analysis. mediaTUM, doi 10.14459/2026mp1840745 (CC BY 4.0).",
     "Used for": "Same cell as the physics model (scripts/fit_sodium.py): calendar loss by state "
                 "of charge (24 cells stored at 10-90 %, 25 and 45 °C, 1.5 years); cycling loss "
                 "per full cycle (four cells, 0-100 % at 1C; SodiumIon.FADE_PER_EFC); check of "
                 "the 20 % windows (no cycling wear beyond the calendar loss)",
     "Link": "https://doi.org/10.14459/2026mp1840745"},
    {"Area": "Ageing: sodium-ion",
     "Reference": "Klick et al. (2025). Batteries & Supercaps.",
     "Used for": "No temperature dependence for sodium-ion (similar fade at 25 and 40 °C; TUM's "
                 "cells stored at 45 °C aged no faster than at 25 °C)",
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
     "Used for": "System cost of a 4-hour battery ($321/kWh, 2025 mid; Table 2 mid projection "
                 "for systems bought later, e.g. $257/kWh in 2033 for the second life), 15-year "
                 "lifetime, 85 % round-trip efficiency",
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
     "Used for": "Range of repurposed EV battery prices ($44-180/kWh)",
     "Link": "https://doi.org/10.1016/j.isci.2023.107195"},
    {"Area": "Ageing",
     "Reference": "Plett G. L. (2004). Extended Kalman filtering for battery management "
                  "systems of LiPB-based HEV battery packs, Parts 1-3. J. Power Sources 134, "
                  "252-292.",
     "Used for": "SOC estimation in the Physics tab (extended Kalman filter, estimator.py)",
     "Link": "https://doi.org/10.1016/j.jpowsour.2004.02.031"},
    {"Area": "Ageing",
     "Reference": "Huang R., Zhao J., Chen J., Xu Y., Li X., Lin W., Ji M., Chen Z., Yu X. "
                  "(2026). Experimental study on the impact of aging trajectories on "
                  "high-nickel ternary NCA lithium-ion cells. Electronics 15(12), 2563.",
     "Used for": "Charge-rate term of the Samsung 50E (0.5 and 1C charge at 23 and 40 °C, "
                 "Fig. 5b read into data/huang2026); no discharge-rate factor for the 50E",
     "Link": "https://doi.org/10.3390/electronics15122563"},
    {"Area": "Ageing",
     "Reference": "Zhu J. et al. (2022). Data-driven capacity estimation of commercial "
                  "lithium-ion batteries from voltage relaxation. Nature Communications 13, "
                  "2261. Data: Zenodo 6405084 (CC BY 4.0).",
     "Used for": "NMC heat term: NCM cells at 45 °C reached 80 % after 0.61 times the cycles "
                 "at 35 °C (sets K_HOT). Check: NCM/NCA cells discharged at 1, 2 and 4C (0.5C "
                 "charge, 25 °C) reached 80 % after the same 470-510 cycles (no discharge-rate "
                 "effect)",
     "Link": "https://doi.org/10.1038/s41467-022-29837-w"},
    {"Area": "Ageing",
     "Reference": "Stroebl F. et al. (2024). A multi-stage lithium-ion battery aging dataset "
                  "using various experimental design methodologies. Scientific Data. Data: "
                  "mediaTUM 1745519 (CC BY 4.0).",
     "Used for": "Check of the NMC ageing model on 42 LG MJ1 cells (10-30 °C, 10-100 % depth, "
                 "0.33-1C charge); warning for fast, deep charging of silicon energy cells",
     "Link": "https://doi.org/10.1038/s41597-024-03859-z"},
    {"Area": "Ageing",
     "Reference": "Kollmeyer P. (2020). LG 18650HG2 Li-ion Battery Data. Mendeley Data, "
                  "version 2. McMaster University.",
     "Used for": "Check of the SOC filter on UDDS, HWFET, LA92 and US06 drive cycles at "
                 "-20 to 40 °C (data/kollmeyer2020)",
     "Link": "https://doi.org/10.17632/b5mj79w5w9.2"},
    {"Area": "Ageing",
     "Reference": "Figgener J. et al. (2024). Multi-year field measurements of home storage "
                  "systems and their use in capacity estimation. Nature Energy 9, 1438-1447.",
     "Used for": "Check of the storage ageing model: 21 home storage systems lost about 2 "
                 "percentage points of capacity a year (NMC 1.9-3.2, LFP 2.0-2.2); system "
                 "10's 2022 data (Zenodo 12091223, CC BY 4.0) test the SOC filter and the "
                 "rest-to-rest capacity method",
     "Link": "https://doi.org/10.1038/s41560-024-01620-9"},
    {"Area": "Ageing: NCA",
     "Reference": "Urquia A. et al. (2025). Aging of Samsung INR21700-50E Li-ion cells. "
                  "e-cienciaDatos (UNED), REBELION project (CC BY 4.0).",
     "Used for": "Level of the NCA cycling term: two 50E cells cycled 0-100 % for 530 full "
                 "cycles; cells with other charge strategies as checks",
     "Link": "https://doi.org/10.21950/GT4LKX"},
    {"Area": "Physics validation",
     "Reference": "Qaadan S. et al. (2025). Data on battery health and performance: analysing "
                  "Samsung INR21700-50E cells with advanced feature engineering. Data in "
                  "Brief 59, 111346; data: Univ. Wuppertal, Zenodo 10891871.",
     "Used for": "NCA physics check: C/5 capacity and self-heating at 0.2-0.75C of two 50E "
                 "cells",
     "Link": "https://doi.org/10.1016/j.dib.2025.111346"},
    {"Area": "Ageing",
     "Reference": "Bilfinger P. et al. (2025). Why we need a standardized state of health "
                  "measurement procedure for electric vehicle battery packs - a proposal for "
                  "energy- and capacity-based metrics. npj Clean Energy 1, 10. Data: mediaTUM "
                  "(CC BY 4.0).",
     "Used for": "Check of the LFP car first life: TUM Tesla Model 3 (LFP), 163.6 -> 149.0 Ah "
                 "in about four years (data/bilfinger2025)",
     "Link": "https://doi.org/10.1038/s44406-025-00010-8"},
    {"Area": "Ageing",
     "Reference": "Rücker F., Figgener J., Schoeneberger I., Sauer D. U. (2024). Battery "
                  "electric vehicles in commercial fleets: Use profiles, battery aging, and "
                  "open-access data. J. Energy Storage 86, 111030. Data: RWTH Aachen, "
                  "doi:10.18154/RWTH-2024-01907 (CC BY 4.0).",
     "Used for": "Field factors of the NMC car first life: capacity tests of six Smart e.d. "
                 "cars (data/rucker2024); two Peugeot iOn as a check",
     "Link": "https://doi.org/10.1016/j.est.2024.111030"},
    {"Area": "Economics (TEA)",
     "Reference": "NREL (2020). Battery Second-Use Repurposing Cost Calculator, June 2020 "
                  "version.",
     "Used for": "Repurposing cost ($24.38 per nameplate kWh) and price paid for the used "
                 "battery ($19.62 per nameplate kWh at 70 % left), at the calculator's defaults",
     "Link": "https://www.nrel.gov/transportation/b2u-calculator.html"},
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
    {"Area": "Environment (LCA)",
     "Reference": "Electricity Maps (2026). Grid in review 2025: Portugal.",
     "Used for": "Grid carbon intensity, 117.2 g CO2eq/kWh (2025 mean, flow-traced, life-cycle "
                 "factors)",
     "Link": "https://www.electricitymaps.com/grid-in-review-2025/portugal"},
    {"Area": "Physics",
     "Reference": "LG Chem (2018). Product specification INR21700 M50T 18.2Wh "
                  "(LRB-PS-CY18.2Wh-M50T).",
     "Used for": "NMC specific energy for the pack mass: 18.2 Wh / 70.0 g = 260 Wh/kg",
     "Link": "https://aws.robu.in/wp-content/uploads/2021/11/DATASHEET-LGM50T.pdf"},
    {"Area": "Economics (TEA)",
     "Reference": "Banco de Portugal (2026). Boletim Económico, junho 2026: projeções para a "
                  "economia portuguesa 2026-28.",
     "Used for": "Inflation (HICP) 3.1 % in 2026, 2.4 % in 2027, 2.0 % in 2028; then the ECB's "
                 "2 % target",
     "Link": "https://www.bportugal.pt/"},
    {"Area": "Economics (TEA)",
     "Reference": "Código do IRC, art. 87.º-A (derrama estadual); AT, Ofício Circulado "
                  "20288/2026 (derrama municipal, period 2025).",
     "Used for": "No IRC surcharges: the state surcharge applies only above €1.5M of taxable "
                 "profit; Lisbon and many other municipalities exempt a turnover up to €150,000",
     "Link": "https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/CIRC_2R/pages/irc87a.aspx"},
    {"Area": "Economics (TEA)",
     "Reference": "Código do IRC, art. 38 (now 31.º-B); AT binding ruling PIV 693 "
                  "(process 2010 001335).",
     "Used for": "Write-off of the remaining book value when the battery is retired",
     "Link": "https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/circ_rep/Pages/irc38.aspx"},
    {"Area": "Economics (TEA)",
     "Reference": "Decreto Regulamentar n.º 25/2009 (depreciation and amortisation), art. 5.",
     "Used for": "No table rate for battery storage: a rate reasonable for the useful life "
                 "(art. 5(3)); used assets over their remaining life (art. 5(2)(a))",
     "Link": "https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/legislacao/outros_diplomas/Documents/Dec_Regulamentar25_2009.pdf"},
    {"Area": "Economics (TEA)",
     "Reference": "Regulation (EU) 2023/1542 on batteries and waste batteries, art. 56 and "
                  "61(1).",
     "Used for": "No disposal cost: producers take back waste industrial and EV batteries free "
                 "of charge",
     "Link": "https://eur-lex.europa.eu/eli/reg/2023/1542/oj"},
    {"Area": "Pack row",
     "Reference": "MEGlobal. Ethylene Glycol product guide, Fig. 8 (specific heats) and "
                  "Fig. 17 (specific gravities).",
     "Used for": "Water-glycol 50 wt% at 25 °C: 3,490 J/(kg K), 1,060 kg/m3",
     "Link": "https://www.meglobal.biz/"},
    {"Area": "Assumptions (not sourced)",
     "Reference": "Indicative values in chemistry.py, economics.py and the dashboard inputs.",
     "Used for": "Recycling credit (EverBatt 2019 gives none for LFP or sodium-ion, and for NMC "
                 "and NCA only after choosing a plant, a location and a process); batteries "
                 "classed as electronic equipment for tax; start in 2026; pack row: coolant "
                 "flow (the VW ID.3 pack keeps its modules within 5 K when fast charging, "
                 "Wassiliadis et al. 2022, but no flow rate is published)",
     "Link": ""},
]
