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
     "Used for": "LFP cell parameters (A123 26650)",
     "Link": "https://doi.org/10.1149/2.053304jes"},
    {"Area": "Physics model",
     "Reference": "Kim G.-H. et al. (2011). Multi-domain modeling of lithium-ion batteries "
                  "encompassing multi-physics in varied length scales. J. Electrochem. Soc. "
                  "158, A955.",
     "Used for": "NCA cell parameters (pouch cell)",
     "Link": "https://doi.org/10.1149/1.3597614"},
    {"Area": "Physics model",
     "Reference": "Chayambuka K. et al. (2022). Physics-based modeling of sodium-ion batteries "
                  "part II. Model and validation. Electrochimica Acta.",
     "Used for": "Sodium-ion cell parameters (hard carbon / NVPF)",
     "Link": ""},
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
                  "Transfer, Table 1.1 (typical convection coefficients).",
     "Used for": "Ranges behind the three cooling options; the averages used are modelling "
                 "assumptions within those ranges",
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
     "Used for": "LFP fast-charging factor (124 A123 cells, 3.6-8C charging)",
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
     "Reference": "Carter et al. (2025). Energies 18, 661.",
     "Used for": "Sodium-ion capacity loss per cycle (0.1 %, NVPF cell)",
     "Link": ""},
    {"Area": "Ageing: sodium-ion",
     "Reference": "Klick et al. (2025). Batteries & Supercaps.",
     "Used for": "No temperature dependence for sodium-ion (similar fade at 25 and 40 °C)",
     "Link": ""},
    # --- Economics and environment ------------------------------------------------------
    {"Area": "Economics and environment",
     "Reference": "Indicative assumptions, not sourced data (see chemistry.py).",
     "Used for": "Cost per kWh, CO2, water and ecotoxicity factors",
     "Link": ""},
]
