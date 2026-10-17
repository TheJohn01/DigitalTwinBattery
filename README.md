![Tests](https://github.com/TheJohn01/DigitalTwinBattery/actions/workflows/tests.yml/badge.svg)    
   [![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://battery-twin.streamlit.app/)
# Battery Digital Twin

**A hybrid physics–empirical digital twin of a lithium-ion or sodium-ion battery cell, with a techno-economic analysis and a screening life cycle assessment**

A battery cell simulator that combines a **physics model** (PyBaMM) with **empirical ageing
models fitted to published measurements**, plus techno-economic (TEA) and life-cycle (LCA)
screening, in a Streamlit dashboard. Chemistries: NMC, LFP, NCA and sodium-ion.

---

## Abstract

Simulations used to design and operate batteries have to work at two very different time
scales. Electrochemical models resolve what happens inside a cell during one charge or
discharge (seconds to hours). Battery lifetime, and so the economics and environmental
impact of a battery, depends on what happens over thousands of cycles (years). Running a
full electrochemical model over the whole service life is computationally expensive. Its
degradation mechanisms are also hard to parameterise for a specific commercial cell.

This work presents a *hybrid* digital twin that splits the problem at that boundary. A
physics-based model (the Single Particle Model with electrolyte, SPMe, or the
Doyle–Fuller–Newman model, DFN, with a lumped thermal model, implemented in PyBaMM) simulates
the first ten cycles of a user-defined test in full. From those cycles it takes the operating
conditions that drive ageing: state-of-charge trajectory, depth of discharge, charge and
discharge rates, and cell temperature. These conditions drive empirical capacity-fade models,
one per chemistry. The models come from the NREL BLAST-Lite library and were refitted or
rescaled to 46 points read from peer-reviewed ageing studies (Preger et al. 2020; Wittman et
al. 2023; Luh & Blank 2024; Ohneseit et al. 2025) and to 81 cells from Severson et al. (2019).
They project capacity fade over up to 20,000 cycles. The NMC physics model is also calibrated
against measured LG M50T data (Kirkaldy et al. 2024): lithium-inventory loss is reproduced
within 0.40 %-points (RMSE) on the training cells, and 2.56 %-points on held-out cells at
10 °C.

The projected capacity curve feeds two downstream assessments:

1. A cycle-by-cycle techno-economic analysis of energy arbitrage on the Portuguese
   day-ahead market (hourly OMIE prices): net present value (NPV), internal rate of return
   (IRR), discounted payback, levelised cost of storage (LCOS), and second-life value. It
   follows the framework of ISO/TS 14076:2025 (environmental techno-economic assessment)
   and the life-cycle costing structure of IEC 60300-3-3 and ISO 15686-5. Costs come from
   NREL, Benchmark Mineral Intelligence and Lazard, grid fees from ERSE, income tax from the
   2026 State Budget, and the discount rate from Steffen (2020).
2. A screening life cycle assessment that follows ISO 14040/14044 (not critically reviewed).
   It uses the functional unit of the EU Battery Regulation (EU) 2023/1542 and the JRC rules
   for the carbon footprint of industrial batteries (CFB-IND). Production impacts come from
   Degen et al. (2024): climate change, water consumption and freshwater ecotoxicity under
   ReCiPe 2016.

The dashboard can export a complete ISO-structured LCA report as a PDF. At the default
settings (20 °C, 0.3C charge, 1C discharge, one cycle per day), the model predicts 373
cycles to 80 % capacity for NMC, 1,229 for LFP, 341 for NCA and 201 for sodium-ion (at the
measured worst-case fade rate). That is consistent with the roughly three-fold LFP-to-NMC
ratio measured in a single study under identical protocols (Ohneseit et al. 2025).

**Keywords:** digital twin; lithium-ion battery; PyBaMM; capacity fade; lithium plating;
empirical ageing model; techno-economic analysis; life cycle assessment; ISO 14044;
Battery Regulation (EU) 2023/1542.

---

## Table of contents

1. [Introduction](#1-introduction)
2. [Quick start](#2-quick-start)
3. [System architecture: how it works](#3-system-architecture-how-it-works)
4. [Electrochemical and thermal model (physics)](#4-electrochemical-and-thermal-model-physics)
5. [Calibration of the NMC physics model](#5-calibration-of-the-nmc-physics-model)
6. [Empirical ageing models](#6-empirical-ageing-models)
7. [Techno-economic analysis (money)](#7-techno-economic-analysis-money)
8. [Screening life cycle assessment (environment)](#8-screening-life-cycle-assessment-environment)
9. [Results at the default settings](#9-results-at-the-default-settings)
10. [Validation and known limitations](#10-validation-and-known-limitations)
11. [Software implementation, testing and reproducibility](#11-software-implementation-testing-and-reproducibility)
12. [Conclusions and future work](#12-conclusions-and-future-work)
13. [Development](#13-development)
14. [Licences and credits](#14-licences-and-credits)
15. [References](#15-references)
- [Appendix A: Nomenclature](#appendix-a-nomenclature)

---

## 1. Introduction

### 1.1 Motivation

How a battery is used, from the C-rates it charges and discharges at to the temperature it
works at, the cooling it gets and how often it cycles, sets how quickly it loses capacity.
That loss sets three things that matter outside the laboratory:

- **Service life:** how many cycles or years the battery stays above a useful capacity.
- **Economics:** how much energy, and so revenue, the battery delivers before it is retired.
- **Environmental impact per unit of service:** production impacts are fixed when the
  battery is made, so every kWh the battery delivers carries a share of them. A battery that
  lasts twice as long halves its production impact per kWh delivered. This is why the EU
  Battery Regulation (EU) 2023/1542 defines the carbon footprint per kWh of energy delivered
  over the service life, not per kWh of capacity.

A *digital twin* here means a computational model of a battery cell that responds to the
same operating inputs as the real cell and predicts its electrical, thermal and ageing
behaviour and, from those, its economic and environmental performance.

### 1.2 Problem statement

Two families of models exist, each with a weakness for this purpose:

| Approach | Strength | Weakness for lifetime studies |
|---|---|---|
| Physics-based (pseudo-two-dimensional DFN, SPMe) | Resolves voltage, current, heat and internal states from first principles | Expensive to integrate over thousands of cycles. Degradation sub-models (SEI growth, lithium plating, particle cracking) have many parameters that are rarely published for a given commercial cell |
| Empirical / semi-empirical ageing models | Fast; fitted directly to measured capacity fade of commercial cells | Need the operating conditions (SOC swing, temperature, C-rate) as input; know nothing about voltage or heat |

### 1.3 Objectives

1. Simulate a user-defined cycling test of a commercial-type cell (NMC, LFP, NCA or
   sodium-ion) with a physics model, including self-heating under a chosen cooling option.
2. Predict long-term capacity fade with empirical models that are fitted or checked against
   peer-reviewed measurements, including charge-rate and temperature effects (lithium plating).
3. Translate the capacity trajectory into economic indicators (NPV, IRR, payback, LCOS) for
   an energy-arbitrage application, including second life.
4. Translate the same trajectory into life cycle impact indicators per functional unit, and
   export a screening LCA report that follows the structure of ISO 14040/14044.
5. State the validity range of every model openly: warn the user when the inputs leave the
   measured conditions, and document where the models are known to be inaccurate.

### 1.4 Scope

- **Level:** single cell, scaled to a pack by energy (the number of cells is the pack energy
  divided by the simulated cell energy). Cell-to-cell variation, pack-level thermal gradients
  and the battery management system are not modelled.
- **Ageing mode:** capacity fade. Resistance growth is used only to approximate an aged cell
  in the Physics tab (Section 4.6).
- **Chemistries:** NMC/graphite, LFP/graphite, NCA/graphite, sodium-ion (hard carbon / NVPF).
- **Range:** capacity down to 50 % of the initial value, where the ageing data end.

### 1.5 Contributions

- A coupling scheme in which the physics model supplies the stress factors for empirical
  ageing models. The BLAST-Lite trajectories are evaluated in closed form, so 20,000 cycles
  are projected in milliseconds.
- Refitted cycling terms for NCA and NMC, and a rescaled LFP term with a fast-charge factor,
  all traceable to tabulated published data (`src/battery_twin/data/`) and reproducible
  with one script (`scripts/fit_ageing.py`).
- An NMC lithium-plating term that makes cooling and pre-conditioning matter for lifetime.
- A calibration of the NMC physics model against an open dataset, with a held-out test.
- An LCA in which the functional unit (kWh delivered) is computed from the *simulated*
  ageing curve, following the CFB-IND rules, and exported as an ISO-structured PDF report.

### 1.6 Structure of this document

Section 3 describes the architecture. Sections 4–8 describe each sub-model: theory, equations,
parameters and data. Section 9 gives the results at the default settings. Section 10
discusses validation and limitations. Section 11 describes the implementation and tests.

---

## 2. Quick start

```
git clone <this repository>
cd <repository folder>
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python -m streamlit run app.py    # dashboard
pytest -q                         # tests
```

Requirements: Python ≥ 3.10 (the CI uses 3.12), PyBaMM ≥ 25.10, NumPy ≥ 2.0, pandas,
SciPy, numpy-financial, Matplotlib and ReportLab (for the PDF report). The dashboard also
needs Streamlit and Plotly (`pip install -e .[app]`). `requirements.txt` installs everything,
including the test tools.

A hosted version runs on Streamlit Community Cloud (badge above). After changing the
dependencies in `pyproject.toml`, reboot the app there so they are reinstalled.

---

## 3. System architecture: how it works

### 3.1 Overview

Follow the arrows from top to bottom. Each box is one step, with the file that does it in italics. The dashed arrow is a step done once, not on every run.

```mermaid
flowchart TD
    USER["You pick the settings: <b>chemistry</b>, <b>charge speed</b>, <b>temperature</b> [<i>app.py</i>]"]
    SHEET[("Battery data sheet: numbers for <b>NMC</b>, <b>LFP</b>, <b>NCA</b>, <b>Na-ion</b> [<i>chemistry.py</i>]")]
    LAB["Real lab measurements, used once to tune the NMC model [<i>calibration.py</i>]"]

    PHYS["<b>1. Physics</b>. Simulate 10 charge/discharge cycles: voltage, current, heat [<i>chemistry.py</i> + <i>PyBaMM</i>]"]
    AGE["<b>2. Ageing</b>. Predict capacity loss over thousands of cycles [<i>ageing.py</i>]"]
    MONEY["<b>3. Money</b>. Is it profitable? NPV, payback, cost per kWh [<i>economics.py</i>]"]
    CO2["<b>4. Environment</b>. Carbon footprint, water, ecotoxicity, PDF report [<i>environment.py</i> + <i>lca_report.py</i>]"]
    OUT["Results on screen: charts, tables, downloads [<i>app.py</i>]"]

    USER --> PHYS
    SHEET --> PHYS
    LAB -. "done once" .-> SHEET
    PHYS --> AGE
    AGE --> MONEY
    SHEET --> CO2
    AGE --> CO2
    PHYS --> OUT
    AGE --> OUT
    MONEY --> OUT
    CO2 --> OUT

  
```

The environment step now also receives the ageing curve (arrow `AGE → CO2`), because the
functional unit of the LCA is the energy delivered over the service life (Section 8).

### 3.2 The two time scales

The key design decision is to split the simulation at the boundary between the two time
scales described in Section 1.2:

```mermaid
flowchart LR
    subgraph FAST["Seconds to hours: physics (PyBaMM)"]
        direction TB
        P1["CC-CV cycling protocol"] --> P2["SPMe or DFN + lumped thermal + SEI"]
        P2 --> P3["V(t), I(t), T(t), SOC(t), Q, E, efficiency"]
    end
    subgraph LINK["Stress factors of one representative cycle"]
        direction TB
        L1["SOC trajectory and depth of discharge"]
        L2["Charge-weighted charge C-rate and temperature while charging"]
        L3["Mean discharge C-rate"]
        L4["Cell temperature profile"]
        L5["Rest until the next cycle (cycles per year)"]
    end
    subgraph SLOW["Months to years: empirical ageing"]
        direction TB
        S1["Calendar loss = f(time, T, SOC)"]
        S2["Cycling loss = g(EFC, DoD, C-rate, T)"]
        S1 --> S3["Capacity q(n), n = 1 … 20,000"]
        S2 --> S3
    end
    FAST --> LINK --> SLOW
    SLOW --> TEA["Economics"]
    SLOW --> LCA["LCA"]
```

### 3.3 Sequence of one dashboard run

```mermaid
sequenceDiagram
    actor U as User
    participant A as app.py (Streamlit)
    participant C as chemistry.py
    participant P as PyBaMM
    participant G as ageing.py
    participant E as economics.py
    participant L as environment.py / lca_report.py
    U->>A: Settings in sidebar, press Run
    A->>C: run_battery_test(chemistry, model, C-rates, cycles, T, h, ...)
    C->>P: build_model() + Experiment (1 conditioning + 10 cycles)
    P-->>C: Solution (cycles, summary variables)
    C->>C: summarise(): capacity, temperatures, efficiency, last-cycle profile
    C->>G: add_rest() then predict_capacity() (nominal, T-5 °C, T+5 °C)
    G-->>C: q(n) for n = 1..20,000
    opt Physics tab: aged windows
        C->>P: run_aged_window(area_scale = q at middle / last window)
    end
    C-->>A: result (projection, cycles, series, meta, warnings)
    A->>E: calculate_tea(q(n), ...), sensitivity(), second_life()
    A->>L: lca_results(q(n), ...), build_lca_report() for the PDF
    A-->>U: Tabs: Summary, Physics, Economics, Environment, Compare, Download, Sources
```

### 3.4 Module dependencies

```mermaid
flowchart BT
    vendor["_vendor/blast_lite<br/>(NREL BLAST-Lite, BSD-3)"]
    ageing["ageing.py"]
    chemistry["chemistry.py"]
    calibration["calibration.py"]
    economics["economics.py"]
    environment["environment.py"]
    report["lca_report.py"]
    sources["sources.py"]
    app["app.py"]
    data[("data/: calibration.json,<br/>published_ageing.csv,<br/>severson2019_cycle_life.csv,<br/>lca_degen2024.csv, kirkaldy2024/,<br/>omie_prices_pt_year.csv")]
    vendor --> ageing --> chemistry
    data --> chemistry
    data --> environment
    data --> economics
    chemistry --> calibration
    chemistry --> environment --> report
    chemistry --> app
    ageing --> app
    economics --> app
    report --> app
    sources --> app
```

### 3.5 Dashboard

The sidebar defines the *battery test*: chemistry, number of cycles (10–10,000), charge rate
(0.3–4C), discharge rate (0.3–3C), ambient temperature (5–45 °C), cooling option, cycles per
year (12–3,650), pack size, and, under "Advanced", the detailed DFN model. For sodium-ion it
also sets the capacity loss per cycle. The results are shown in seven tabs:

| Tab | Content |
|---|---|
| Summary | Capacity left, cycles to 80 %, peak temperature, cells per pack; capacity curve with the shaded sensitivity range; validity warnings; "How accurate is this?" (NMC measured-vs-model comparison) |
| Physics | Voltage and temperature of the first, middle and last 10 cycles (Section 4.6); the 10 simulated cycles one by one; Coulombic and energy efficiency per cycle |
| Economics | NPV, IRR, payback, LCOS from hourly OMIE prices and sourced costs; tornado chart (±20 %); second life |
| Environment | Carbon footprint (regulation scope and incl. losses), water, freshwater ecotoxicity per kWh delivered; phase table; PDF report download |
| Compare chemistries | All four chemistries under the same simple cycle: capacity, cycles to 80 %, cost, NPV, LCOS, carbon footprint |
| Download | Capacity per cycle (CSV), voltage & temperature series (CSV), run settings (JSON) |
| Sources | Every published source and what it is used for (`src/battery_twin/sources.py`) |

---

## 4. Electrochemical and thermal model (physics)

### 4.1 Model selection

PyBaMM solves the battery's equations for 10 full cycles. This is accurate but slow, so it only runs a few cycles. PyBaMM simulates full charge/discharge cycles: voltage,
   current, heat and state of charge (SPMe, or DFN above 2C charge).

PyBaMM (Sulzer et al. 2021) offers both models. The choice is made in `app.py`:

| Condition | Model |
|---|---|
| Default (lithium chemistries, charge ≤ 2C) | SPMe: Single Particle Model with electrolyte |
| Charge rate > 2C, or "Detailed physics" ticked | DFN: Doyle–Fuller–Newman (pseudo-two-dimensional) |
| Sodium-ion (always) | PyBaMM `sodium_ion.BasicDFN`, isothermal, no degradation sub-model |

The SPMe treats each electrode as one representative particle and adds an electrolyte
correction. It is accurate at low to moderate C-rates and much faster than the DFN. At high
C-rates the reaction distribution across the electrode thickness becomes non-uniform, and
the full DFN is needed.

### 4.2 Governing equations (DFN)

For each electrode *k* ∈ {n, p}, lithium diffuses in spherical active particles of radius
R_k:

```math
\frac{\partial c_{s,k}}{\partial t} = \frac{1}{r^2}\frac{\partial}{\partial r}\left(r^2 D_{s,k}\frac{\partial c_{s,k}}{\partial r}\right),
\qquad
-D_{s,k}\left.\frac{\partial c_{s,k}}{\partial r}\right|_{r=R_k} = \frac{j_k}{a_k F}
```

Lithium ions move through the electrolyte (porosity ε, transference number t⁺):

```math
\varepsilon_k \frac{\partial c_e}{\partial t} = \frac{\partial}{\partial x}\left(D_e^{\text{eff}} \frac{\partial c_e}{\partial x}\right) + \frac{(1-t^+)}{F}\, j_k
```

Charge is conserved in the solid (φ_s) and the electrolyte (φ_e):

```math
\frac{\partial}{\partial x}\left(\sigma_k^{\text{eff}}\frac{\partial \phi_s}{\partial x}\right) = j_k,
\qquad
\frac{\partial}{\partial x}\left(\kappa^{\text{eff}}\frac{\partial \phi_e}{\partial x} - \frac{2\kappa^{\text{eff}} R T}{F}(1-t^+)\frac{\partial \ln c_e}{\partial x}\right) = -j_k
```

The interfacial current density follows Butler–Volmer kinetics:

```math
j_k = a_k\, j_{0,k} \sinh\!\left(\frac{F\,\eta_k}{2RT}\right),
\qquad
\eta_k = \phi_s - \phi_e - U_k(c_{s,k}^{\text{surf}}),
\qquad
j_{0,k} = k_k \sqrt{c_e\, c_{s,k}^{\text{surf}}\,(c_{s,k}^{\max} - c_{s,k}^{\text{surf}})}
```

The terminal voltage is V = φ_s(x = L) − φ_s(x = 0). The SPMe replaces the through-thickness
solid problem with one particle per electrode and keeps a first-order electrolyte correction.

### 4.3 Thermal model

All lithium models use PyBaMM's **lumped** thermal option: one cell temperature T, governed
by an energy balance of heat generation and convective cooling:

```math
\rho c_p^{\text{eff}} V_{\text{cell}} \frac{dT}{dt} = Q_{\text{gen}} - h\,A_{\text{cool}}\,(T - T_{\text{amb}})
```

Q_gen contains the irreversible (ohmic and reaction overpotential) and reversible (entropic)
heat. *h* is the **total heat transfer coefficient**, an effective value over the whole
cooling surface A_cool. It is set by the cooling option (Section 4.5). PyBaMM's sodium-ion
model is isothermal (T = T_amb).

### 4.4 Degradation inside the physics model (SEI)

The lithium models enable PyBaMM's *solvent-diffusion-limited* SEI growth model. The SEI
grows as solvent diffuses through the existing layer, at a rate inversely proportional to
its thickness. Its diffusivity is Arrhenius-dependent:

```math
j_{\text{SEI}} \propto -\frac{c_{\text{sol}}\, D_{\text{sol}}(T)}{L_{\text{SEI}}},
\qquad
D_{\text{sol}}(T) = D_{\text{sol,ref}} \exp\!\left[\frac{E_{\text{SEI}}}{R}\left(\frac{1}{T_{\text{ref}}} - \frac{1}{T}\right)\right]
```

The parameter sets for LFP (Prada 2013) and NCA (Kim 2011) give E_SEI = 0 J/mol, which would
make SEI growth independent of temperature. The program uses 38 kJ/mol from O'Kane et al.
(2022) instead. For NMC both SEI parameters are calibrated (Section 5). This physics-level
SEI loss is reported for the ten simulated cycles. The **long-term** projection uses the
empirical models of Section 6, which capture all mechanisms that the measured data contain.

### 4.5 Parameter sets, cycling protocol and cooling

**Parameter sets.** Each chemistry uses a published PyBaMM parameter set (`chemistry.py`).
Missing parameters (for example the thermal properties of Prada 2013) are filled from Chen
2020, without overwriting existing values:

| Chemistry | Parameter set | Cell | Voltage window | Modifications |
|---|---|---|---|---|
| NMC | Chen 2020 | LG M50 21700 (≈5 Ah) | 2.5–4.2 V | Lithium inventory, SEI diffusivity and activation energy calibrated (Section 5) |
| LFP | Prada 2013 | A123 26650 | 2.0–3.6 V | 26650 cell volume (3.45·10⁻⁵ m³) and cooling area (0.00637 m²); E_SEI = 38 kJ/mol |
| NCA | Kim 2011 | Small pouch (≈0.43 Ah, 1.7 Wh) | 2.7–4.2 V | E_SEI = 38 kJ/mol |
| Na-ion | Chayambuka 2022 | Hard carbon / NVPF, 3 mAh lab cell | 2.0–4.2 V | Electrode width ×1000 → 3 Ah cell with identical electrochemistry |

**Cycling protocol.** Each cycle is CC discharge to V_min, rest 5 min, CC charge to V_max,
CV hold at V_max until C/20, and rest 5 min. One extra conditioning cycle (cycle 0) is run
first and discarded, because the parameter set's initial state does not match the CC-CV
charged state. The capacity of each cycle is the thermodynamic capacity from PyBaMM's
electrode state-of-health summary (lithium), or the measured discharge capacity (sodium-ion).
Coulombic and energy efficiencies are integrated from the current and voltage.

**Cooling.** The sidebar offers three cooling options. Each sets an average effective heat transfer
coefficient h over the cell surface (a modelling assumption within the textbook ranges of
Incropera et al., Table 1.1; the dashboard shows a warning with the realistic range):

| Option | h (W/m²K) | Pre-conditioning |
|---|---|---|
| Forced air / passive | 25 | No: cells cycle at the ambient temperature |
| Liquid cold plate | 100 | Yes: cells held at 25 °C while cycling |
| Immersion cooling | 300 | Yes: cells held at 25 °C while cycling |

Between cycles the battery always rests at the ambient temperature. The calibrated value
for the Kirkaldy test chamber (13 W/m²K) is still the default of `run_battery_test`. All
published sources are listed in the dashboard's **Sources** tab (`src/battery_twin/sources.py`).

The textbook ranges are 2–25 W/m²K for free convection of air, 25–250 W/m²K for forced air
and 100–20,000 W/m²K for forced liquids. Those are coolant-side values, whereas the lumped
model needs an *effective* value over the whole cell surface. Only part of each cell touches
a cold plate, through a thermal interface material, so the effective values chosen are much
lower. The warnings shown in the dashboard give the realistic effective ranges: about
5–15 W/m²K (passive) and 25–50 W/m²K (forced air), 50–200 W/m²K (cold plate) and
100–1,000 W/m²K (immersion). With pre-conditioning, the thermal system warms or cools the
cells to 25 °C while they cycle, so in cold weather they do not charge cold. Section 6.4
shows why that matters for NMC.

### 4.6 Physics tab: first, middle and last cycles

The physics model simulates the first 10 cycles in full. To compare them with later life,
the Physics tab also simulates 10 cycles in the middle and at the end of the chosen number
of cycles, using an aged cell: the new cell with its electrode area scaled to the capacity
the ageing model predicts there. It holds less charge and, at the same current, has a higher
resistance (+25 % at 80 % capacity). This is an approximation: real ageing also shifts the
electrode balance and grows the SEI, which the scaled cell does not capture.

Formally, the electrode width is multiplied by the predicted capacity fraction q(n_start).
The C-rate current is kept at the *new* cell's value, so the current density per electrode
area rises by 1/q. That reproduces a resistance increase of 1/q − 1, which is +25 % at
q = 0.8. Ohneseit et al. (2025) measured roughly +10 to +50 % ohmic resistance growth to
80 % capacity. Windows that overlap an earlier window, or that start below 50 % capacity,
are not simulated.

```mermaid
flowchart LR
    Q["Ageing curve q(n)"] --> W1["First window<br/>cycles 1–10<br/>new cell"]
    Q --> W2["Middle window<br/>n/2-4 … n/2+5<br/>width × q(mid)"]
    Q --> W3["Last window<br/>n-9 … n<br/>width × q(n-9)"]
    W1 --> CMP["Overlay: voltage and temperature vs time in cycle;<br/>table of capacity, efficiency, max/mean temperature"]
    W2 --> CMP
    W3 --> CMP
```

---

## 5. Calibration of the NMC physics model

### 5.1 Data

The NMC model is calibrated with the open dataset of Kirkaldy et al. (2024, J. Power
Sources 603, 234185; Zenodo 10637534, CC-BY-4.0), "Expt 2,2": six LG M50T cells (two each
in 10, 25 and 40 °C chambers) cycled between 70 and 85 % state of charge (1C discharge,
0.3C charge) for about 260 days. The processed files give loss of lithium inventory (LLI),
state of health and the measured cell surface temperature. They are stored in
`src/battery_twin/data/kirkaldy2024/`.

### 5.2 Procedure

`calibration.py` (run with `python scripts/calibrate.py`) fits three quantities in sequence:

```mermaid
flowchart TD
    D[("Kirkaldy et al. 2024<br/>6 cells, 10/25/40 °C")] --> S1
    S1["1. Lithium inventory<br/>secant method on c_n,0<br/>target: C/10 capacity 4.857 Ah"] --> S2
    S2["2. SEI growth<br/>least squares on log10 D_sol and E_SEI<br/>train: 25 and 40 °C cells (LLI)<br/>test: 10 °C cells (held out)"] --> CHK
    CHK{"Storage shortcut valid?<br/>20 cycles vs storage, same time<br/>within 2 %"} --> S3
    S3["3. Cooling coefficient h<br/>bisection on h, 5–60 W/m²K<br/>target: measured self-heating, 25 °C chamber"] --> J
    J[("calibration.json<br/>read by chemistry.py")]
```

1. **Capacity.** Capacity is linear in the initial lithium concentration in the negative
   electrode, c_n,0, so three secant steps make the simulated C/10 capacity match the mean
   measured capacity of 40 cells, 4.857 Ah (Kirkaldy et al., Table 7).
2. **SEI growth.** The solvent-diffusion SEI model does not depend on current. A 70–85 %
   cycle therefore ages the model like storage at the same mean state of charge (0.775) and
   temperature, which is much faster to simulate. `check_storage_shortcut()` verifies this:
   20 real cycles and storage for the same time give LLI within 2 %. The parameters
   x = [log₁₀ D_sol, E_SEI] are fitted by bounded least squares to the measured LLI of the
   25 °C and 40 °C cells. Each cell is simulated at its measured surface temperature:

```math
\min_{x}\ \sum_{\text{cells}\in\{25,40\,^\circ\text{C}\}}\ \sum_{i} \left[\text{LLI}_{\text{model}}(x; T_{\text{cell}}, t_i) - \text{LLI}_{\text{meas}}(t_i)\right]^2
```

3. **Cooling.** The lumped model's temperature rise in the 25 °C chamber (mean over the
   second half of eight 70–85 % cycles) is matched to the measured rise by bisection on h.

### 5.3 Result

| Quantity | Default (Chen 2020) | Calibrated |
|---|---|---|
| Initial concentration in negative electrode | 29,866 mol/m³ | 28,342 mol/m³ |
| SEI solvent diffusivity | 2.5·10⁻²² m²/s | 2.19·10⁻²⁰ m²/s |
| SEI growth activation energy | 38 kJ/mol (O'Kane) | 25.4 kJ/mol |
| Total heat transfer coefficient (test chamber) | n/a | 12.96 W/m²K (13 in the program) |
| LLI RMSE, training cells (25/40 °C) | n/a | 0.40 %-points |
| LLI RMSE, held-out cells (10 °C) | n/a | 2.56 %-points |
| Storage shortcut valid | n/a | Yes |

The fit reproduces lithium loss within 0.5 %-points at 28–41 °C cell temperature. At 16 °C
the model's lithium loss is 2.6 %-points lower than measured (those cells were not used in the
fit). A likely reason is that a mechanism that grows when cold, such as lithium plating, is
missing from the solvent-diffusion SEI model. `python scripts/validate.py` repeats the
comparison for both the physics and the empirical model (Section 10).

---

## 6. Empirical ageing models

### 6.1 Concept

Formulas fitted to real lab tests take those 10 cycles and project how much capacity is left after thousands more (up to 20,000 cycles). The simulated state-of-charge swing and cell temperature drive an empirical capacity-fade model for that chemistry. Each cycle is followed by a rest so that it lasts as long as in real use (set by "Cycles per year", 365 = once a day), because batteries also age while they sit idle (calendar ageing).

All lithium models are of the semi-empirical, additive form used by BLAST-Lite (Gasper et
al.):

```math
q(n) = 1 - \underbrace{L_{\text{cal}}(t_n;\ T,\ \text{SOC})}_{\text{calendar}} - \underbrace{L_{\text{cyc}}(\text{EFC}_n;\ \text{DoD},\ C,\ T)}_{\text{cycling}},
\qquad q \in [0, 1]
```

Here q(n) is the capacity fraction after n cycles, t_n the elapsed time and EFC_n the
equivalent full cycles.

| Chemistry | Physics parameters | Ageing model and data |
|---|---|---|
| NMC | Chen 2020 (LG M50), calibrated to Kirkaldy et al. 2024 | Calendar: NREL BLAST-Lite, LG M50 (Truong Bui et al., IEEE 2021). Cycling, incl. fast/cold charging: fitted to LG HG2 data (Luh & Blank, Sci. Data 2024; Preger et al. 2020; Wittman et al. 2023) and Ohneseit et al. 2025 |
| LFP | Prada 2013 (A123 26650) | NREL BLAST-Lite, Sony-Murata 3 Ah (Naumann et al. 2018, 2020; Gasper et al., JES 2022); cycling term rescaled to Ohneseit et al. 2025; fast-charge factor from Severson et al., Nat. Energy 2019 |
| NCA | Kim 2011 (pouch) | Panasonic NCR18650B: calendar from NREL BLAST-Lite (Keil et al., JES 2016); cycling refitted to Preger et al., JES 2020 |
| Na-ion | Chayambuka 2022 (hard carbon / NVPF) | 0.1 % per cycle (adjustable), commercial NVPF cell (Carter et al., Energies 18, 661, 2025) |

### 6.2 From the physics model to the stress factors

The last fully simulated cycle (time t, SOC, cell temperature T) is the *representative
cycle* that is assumed to repeat. `ageing.py` extracts the following from it:

| Stress factor | Definition |
|---|---|
| Equivalent full cycles per cycle | EFC₁ = ½ Σ\|ΔSOC\| |
| Depth of discharge | DoD = max SOC − min SOC |
| Mean discharge C-rate | c_dis = Σ(−ΔSOC) / Σ Δt over discharging intervals [1/h] |
| Charge-weighted charge C-rate | c_ch = Σ(r_i ΔSOC_i) / Σ ΔSOC_i, with r_i = ΔSOC_i/Δt_i over charging intervals. Weighting by charge makes the CV tail count little |
| Temperature while charging | T_ch = time-weighted mean cell temperature over charging intervals |
| Cycle period | Δt₁ = 365 · 86,400 s / (cycles per year), including the rest |

**Rest between cycles (`add_rest`).** Laboratory ageing tests cycle back to back, but a
battery in real use cycles, for example, once a day and spends the rest of the day idle,
where it keeps ageing (calendar ageing). After the simulated cycle, the program adds a rest
at the final state of charge and at the ambient temperature, so that each cycle lasts its
real period. If the cycle itself is longer than the requested period, no rest is added and
the achievable number of cycles per year is used instead. The test
`test_resting_between_cycles_adds_calendar_ageing` confirms that daily cycling ages the
cell more than the same cycles run back to back.

### 6.3 Closed-form evaluation

The BLAST-Lite models compute degradation rates from one simulated cycle; because the cycle
repeats, their capacity-loss trajectories are evaluated in closed form (matches BLAST-Lite's
own cycle-by-cycle stepping within 0.0004).

BLAST-Lite integrates power-law states such as dL = k · p · L^((p−1)/p) · Δx incrementally.
With constant rates k (the same cycle repeating), that integrates exactly to L = k · x^p, with
x = t or EFC. So the whole trajectory of 20,000 cycles is one vectorised expression,
independent of the step size. `test_calendar_term_matches_blast_stepping` checks this against
BLAST-Lite's own stepping.

### 6.4 NMC: calendar term plus refitted cycling term with lithium plating

**Calendar** (BLAST-Lite, LG M50, Truong Bui et al. 2021):

```math
L_{\text{cal}} = k_{\text{cal}}(T, U_a, \text{SOC})\left(\frac{t_{\text{days}}}{10^4}\right)^{p_{\text{cal}}},
\qquad p_{\text{cal}} = 0.652
```

k_cal is the time average over the cycle of a fitted function of normalised temperature,
anode potential U_a(SOC) and SOC.

**Cycling** (`NmcRefit`, refitted):

```math
L_{\text{cyc}} = \text{DoD}^{\,B}\left[K_{\text{base}} + K_{\text{pl}}\, c_{\text{ch}}^{\,N}\, \exp\!\left(-\frac{T_{\text{ch}} - 25}{T_{\text{pl}}}\right)\right]\text{EFC}^{\,P}
```

The second term grows with the charge rate and with colder cell temperature while charging.
Luh & Blank (2024) attribute this fast loss to **lithium plating**. BLAST-Lite's own LG M50
cycling term is not used: it aged faster when warmer and gave about 10x the life at 3C
discharge as at 1C.

| Parameter | Value | Meaning |
|---|---|---|
| K_base | 6.905·10⁻³ | Base cycling loss coefficient |
| K_pl | 8.545·10⁻³ | Plating loss coefficient |
| N | 0.602 | Charge-rate exponent |
| T_pl | 24.56 °C | e-folding temperature of plating |
| P | 0.442 | EFC exponent (fixed at BLAST-Lite's LG M50 value) |
| B | 0.630 | Depth-of-discharge exponent |
| Fit | 24 points, typical error ×1.38 in cycles to 80 % | |
| Validity | 0–40 °C, DoD 0.2–1, charge ≤ 1.67C, discharge ≤ 3C | |

P is fixed because the data are cycles to 80 % only, which do not pin down the curve shape.
The curves of Luh & Blank (fast loss in the first ~100 cycles, then slower) and Preger's NMC
curves give a similar exponent (0.4–0.5). Discharge rate has no clear effect in the data
(Preger: 0.5–3C; Luh & Blank: 1/3 and 1C; Ohneseit: 1 and 2C), so it is not in the model.

**Charge rate.** NMC and LFP now age faster with faster charging. NMC also ages faster when
the cell is cold while charging (lithium plating), so cooling matters: a strongly cooled
cell stays colder during fast charging. Discharge rate has no effect for NMC (none was seen
in the data).

Pre-conditioning removes this cold-charge penalty: in `test_preconditioning_keeps_cold_nmc_alive_longer`
(5 °C ambient, 1.5C charge), the liquid cold plate keeps the cell above 20 °C and gives a
longer life than forced air.

### 6.5 NCA: calendar term plus refitted cycling term

**Calendar** (BLAST-Lite, Panasonic NCR18650B, Keil et al. 2016):

```math
L_{\text{cal}} = k_{\text{cal}}\, t_{\text{days}}^{\,0.512},
\qquad
k_{\text{cal}} = A_{\text{cal}}\, e^{B_{\text{cal}}/T}\, e^{C_{\text{cal}}\,\text{SOC}/T}
```

**Cycling** (`NcaRefit`, refitted to Preger et al. 2020, same cell):

```math
L_{\text{cyc}} = A\ \text{DoD}^{\,B}\ \text{clip}(c_{\text{dis}}, 0.5, 2)^{-C}\ \text{EFC}^{\,P}
```

| Parameter | Value |
|---|---|
| A | 1.469·10⁻³ |
| B (DoD exponent) | 0.806 |
| C (discharge-rate exponent) | 0.297 |
| P (EFC exponent) | 0.787 |
| Fit | 18 points, RMS error 2.0 %-points of capacity |
| Validity | 15–35 °C, DoD 0.2–1, charge ≤ 0.5C, discharge ≤ 2C |

Preger found no clear temperature effect on NCA cycling between 15 and 35 °C, so the cycling
term has none; temperature still acts through the calendar term. Faster discharge giving
slower fade is what Preger measured at all three temperatures (the cause is unclear).

### 6.6 LFP: rescaled BLAST-Lite model with a fast-charge factor

**Model** (BLAST-Lite, Sony-Murata 3 Ah 18650; Naumann et al. 2018, 2020; Gasper et al. 2022).
The calendar loss is a sigmoid in time, and the cycling loss is a power law in throughput:

```math
L_{\text{cal}} = 2 q_1\left(\tfrac12 - \frac{1}{1 + \exp\!\left[(q_2\, t_{\text{days}})^{q_3}\right]}\right),
\qquad
L_{\text{cyc}} = S \cdot \max\!\left(1, \frac{c_{\text{ch}}}{C_{\text{th}}}\right)^{M}\,(q_5\,\text{EFC})^{q_6}
```

q₁ and q₃ depend on temperature and anode potential, q₂ = 1.305·10⁻⁴ and q₆ = 1.128. q₅
depends on DoD and C-rate. A break-in term is added only above 3 equivalent full cycles
per day.

| Parameter | Value | Fitted to |
|---|---|---|
| S (scale) | 7.644 | Ohneseit et al. 2025, 21700 LFP, 0–100 %, 20 °C, 1C (≈1,600 cycles to 80 %) |
| C_th (charge-rate threshold) | 2.335C | Severson et al. 2019 (A123, 3.6–8C, 30 °C) and Preger et al. 2020 (A123, 0.5C) |
| M (fast-charge exponent) | 2.933 | Same as C_th |
| Fit (fast charge) | Typical error ×1.27 over 82 cells (81 Severson + 1 Preger) | |

The Sony-Murata cell is an unusually durable high-power cell. Its BLAST-Lite model gave
about 8,000 cycles to 80 % for full cycles at 20 °C and 1C, against about 1,450–1,900 measured
by Ohneseit et al. for a commercial 21700 LFP cell. Ohneseit's test used the same lab,
protocol and cell format as the NMC data, so the scale factor S puts LFP and NMC on a common
basis.

### 6.7 Sodium-ion

```math
q(n) = 1 - f\cdot \text{EFC}_n,
\qquad f = 0.001 \text{ per EFC (default; adjustable)}
```

The fade rate f is measured on a commercial hard carbon / NVPF cell (Carter et al. 2025,
100 cycles, CC-CV, C/3). The model counts cycles only, so neither rest nor temperature
changes it.

### 6.8 Parameter identification

The NCA and NMC cycling terms and the LFP cycling factors are fitted by
`python scripts/fit_ageing.py` to published values in `src/battery_twin/data/published_ageing.csv`
(read from the figures and text of Preger et al. 2020, Wittman et al. 2023, Ohneseit et al.
2025 and Luh & Blank 2024) and `severson2019_cycle_life.csv` (Severson et al. 2019,
Supplementary Table 9; all 124 cells). The raw data files were not used. BLAST-Lite's own NCA
cycling term gave about 5,000 cycles to 80 % where Preger measured about 430 on the same
cell; its NMC term had no depth-of-discharge or charge-rate effect, aged faster when warmer
(the data show the opposite for cycling) and gave about 10x the life at 3C discharge as at 1C.

`published_ageing.csv` contains 46 points:

| Chemistry | Source | Points |
|---|---|---|
| NCA | Preger et al. 2020, Fig. 2a, 3c, 3f, 3i (Panasonic NCR18650B) | 18 |
| NMC | Luh & Blank 2024, Fig. 12 (LG HG2; median of three cells, read from the figure's pixels) | 16 |
| NMC | Preger et al. 2020, Fig. 2a (LG HG2) | 3 |
| NMC | Wittman et al. 2023, text (LG HG2) | 3 |
| NMC | Ohneseit et al. 2025, Fig. 5/6 (NMC811 + Si 21700) | 2 |
| LFP | Ohneseit et al. 2025, Fig. 5/6 (21700 LFP) | 2 |
| LFP | Preger et al. 2020, Fig. 3g (A123 APR18650M1A) | 1 |

Each published test is rebuilt as a repeating laboratory cycle (CC discharge, rest, CC
charge with a 30-minute CV hold at 100 %, rest) and run through the *same*
`predict_capacity` function as the dashboard. The fitted model therefore includes the
calendar ageing that happened during each test.

```mermaid
flowchart TD
    CSV[("published_ageing.csv<br/>46 points")] --> NCA
    CSV --> NMC
    CSV --> LFP1
    SEV[("severson2019_cycle_life.csv<br/>124 cells, 81 used")] --> LFP2
    NCA["NCA: least squares on A, B, C, P<br/>residual: capacity at given EFC [%-points]"]
    NMC["NMC: bounded least squares on K_base, K_pl, N, T_pl, B (P fixed)<br/>residual: log(model / measured EFC to 80 %)"]
    LFP1["LFP step 1: scale S<br/>Ohneseit 1C, 20 °C"]
    LFP2["LFP step 2: C_th, M (+ own A123 level, not used)<br/>residual: log cycle-life ratio"]
    LFP1 --> LFP2
    NCA --> OUT["Constants copied into ageing.py"]
    NMC --> OUT
    LFP2 --> OUT
```

For NCA, the residual is the difference in capacity at the measured number of EFC. For NMC
and LFP, it is the logarithmic error in cycles to 80 %:

```math
r_i = \ln\frac{\text{EFC}_{80,\text{model}}}{\text{EFC}_{80,\text{measured}}},
\qquad \text{typical error} = \exp\!\left(\sqrt{\overline{r_i^2}}\right)
```

To keep the objective smooth, the model's cycles to 80 % are interpolated linearly between
cycles. Severson's 2017-06-30 batch is left out because the same charging policies gave much
shorter lives than in the other two batches (e.g. 4.8C: about 470 vs about 750 cycles). In
LFP step 2, the A123 cells get their own level factor, because they last longer than
Ohneseit's cell. Only C_th and M go into the program.

### 6.9 Sensitivity range and validity warnings

**Shaded range.** For lithium chemistries, the prediction is repeated with the cell
temperature shifted by −5 °C and +5 °C. For sodium-ion, it is repeated with the best and worst
measured commercial cells (0.01–0.1 %/cycle). The envelope of the three curves is shaded.

**Cut-off.** Capacity below 50 % is set to "no data".

**Warnings.** `validity_warnings` compares the mean cell temperature, charge and discharge
rates, depth of discharge and (for sodium-ion) cycle count with each model's
`experimental_range`. The dashboard lists every condition outside it.

---

## 7. Techno-economic analysis (money)

### 7.1 Application and method

The ageing curve tells the economics how much energy the battery delivers each year. The capacity curve feeds an arbitrage TEA (NPV, IRR, payback, LCOS, second life) cycle by cycle: when capacity drops below the retirement threshold (default 50 %, where the data ends) the battery stops earning and stops costing.

The modelled application is **energy arbitrage on the Portuguese day-ahead market**: the
battery buys electricity in the cheapest hours of a day and sells it in the dearest hours.
Earlier versions used a fixed price and spread; these were assumptions and have been
replaced by measured hourly prices (Section 7.2). Every other input now comes from a
published source or from the simulation (Section 7.3).

**Standards.** No ISO standard prescribes formulas for a techno-economic analysis, but
several standards set its structure:

| Standard | What it covers | How it is applied here |
|---|---|---|
| ISO/TS 14076:2025, *Environmental techno-economic assessment (eTEA): principles, requirements and guidance* | Framework for a TEA combined with an LCA. Clause 6 sets the phases: goal and scope, technical analysis, economic analysis, life cycle assessment, sensitivity analysis, combined interpretation. Clause 4 sets the principles: basis of production, functional unit and reference flows, transparency. Clause 7 sets the documentation requirements, including digital files | TEA and LCA use the same functional unit (1 kWh delivered), the same ageing curve and, by default, the same end of service life (70 %). Technical analysis: physics and ageing models. Sensitivity: tornado chart. Combined interpretation: LCOS and carbon footprint side by side (Compare tab). Documentation: downloadable cash-flow table (CSV) and every input with its source (JSON) |
| IEC 60300-3-3:2017, *Life cycle costing* | Life-cycle cost concepts: a cost breakdown over the life cycle (acquisition, operation and maintenance, disposal) | Cost breakdown per year: acquisition (CAPEX), operation (charging energy, grid fees), maintenance (O&M, warranty), income tax. Disposal: not included (no source) |
| ISO 15686-5:2017, *Life-cycle costing* (constructed assets) | Net present value, discount rate, real vs nominal costs, sensitivity | Nominal cash flows (prices, fees and O&M escalate) discounted at a nominal rate (Steffen's WACC is nominal) |
| IEC 62933-2-1, *EES systems: unit parameters and testing methods* | Round-trip efficiency of an energy storage system measured at its grid connection | The efficiency includes inverter and auxiliary losses, not only the cell (Section 7.3) |

Only the public scope and contents of these standards were available, not their full
text. The structure above follows their published clause titles. The full documents would
be needed to claim conformity.

**Daily dispatch.** For every day d of the price file, the program finds the best single
cycle with perfect foresight of that day's prices. A new battery needs
h_dis = DoD / c_dis hours to discharge and h_ch = DoD / (η_RT · c_ch) hours to charge at its
rated C-rates. For every split hour s, it charges in the cheapest h_ch hours before s and
discharges in the dearest h_dis hours after s (the last hour may be partial), and keeps
the split with the largest margin:

```math
\bar{p}^{\,\text{buy}}_d,\ \bar{p}^{\,\text{sell}}_d = \arg\max_{s}\left[\bar{p}^{\,\text{sell}}_{d}(s) - \frac{\bar{p}^{\,\text{buy}}_{d}(s)}{\eta_{\text{RT}}}\right],
\qquad
m_d = \bar{p}^{\,\text{sell}}_d - \frac{\bar{p}^{\,\text{buy}}_d}{\eta_{\text{RT}}}
```

Here m_d is the margin per kWh delivered. Prices may be negative (the battery is then paid
to charge). The battery cycles N_y times a year (sidebar); it uses the N_y days with the
highest margin, so with 365 cycles a year it cycles every day, including days on which it
loses money, as the ageing model assumes. The mean buying price p and the mean spread
s = p̄_sell − p are passed to the cash-flow model below. The price model allows one cycle
per day; above 365 cycles a year the extra cycles get the same mean prices (optimistic, and
the dashboard warns).

**Cash flows.** In year y the battery runs cycles
k ∈ K_y = {N_y(y−1)+1, …, N_y·y} (plus an offset for second life), and only the cycles with
q_k ≥ q_ret count. After the first cycle below q_ret, the battery is retired: it has no
revenue and no operating cost from then on.

```math
E^{\text{out}}_y = C_{\text{pack}}\cdot \text{DoD}\cdot \sum_{k\in K_y,\ q_k\ge q_{\text{ret}}} q_k,
\qquad
E^{\text{in}}_y = \frac{E^{\text{out}}_y}{\eta_{\text{RT}}}
```

```math
CF_0 = -\text{CAPEX} = -c_{\text{cap}}\, C_{\text{pack}},
\qquad
CF_y = \underbrace{\left[E^{\text{out}}_y\,(p + s) - E^{\text{in}}_y\,p\right](1+i)^y - \text{OPEX}_y - G_y}_{\text{EBITDA}_y} - T_y
```

Prices are those of 2025 and rise with inflation i = 2 % a year (ECB target; assumption).
G_y are the grid fees: zero until 2029, then optional (Section 7.3). T_y is the corporate
income tax:

```math
T_y = \tau_y \cdot \max\!\left(0,\ \text{EBITDA}_y - \frac{\text{CAPEX}}{Y} - L_{y-1}\right),
\qquad \tau_{2026} = 19\,\%,\ \tau_{2027} = 18\,\%,\ \tau_{\ge 2028} = 17\,\%
```

Here CAPEX/Y is straight-line depreciation (assumption) and L the tax losses carried
forward (without limit; assumption).

```math
\text{OPEX}_y = c_{\text{O\&M}}\,C_{\text{pack}}\,(1.025)^{\,y-1} + 0.009\cdot\text{CAPEX}\cdot[\,y \ge 3\,]
\qquad \text{(only while working)}
```

The earlier OPEX assumption, 1.5 % of CAPEX per year, has been replaced by Lazard's
general O&M plus warranty (Section 7.3). The LCOS below is before tax and includes grid
fees in its costs.

```math
\text{NPV} = \sum_{y=0}^{Y}\frac{CF_y}{(1+r)^y},
\qquad
\text{LCOS} = \frac{\text{CAPEX} + \sum_{y=1}^{Y}\frac{E^{\text{in}}_y p + \text{OPEX}_y}{(1+r)^y}}{\sum_{y=1}^{Y}\frac{E^{\text{out}}_y}{(1+r)^y}}
```

The IRR is the r for which NPV = 0 (numpy-financial). The discounted payback is the first
year in which the cumulative discounted cash flow is non-negative ("Never" if it does not
happen within the project).

```mermaid
flowchart LR
    PR[("OMIE hourly prices<br/>Portugal")] --> DA["Best cycle of each day<br/>buy cheapest, sell dearest<br/>(charge before discharge)"]
    DA --> SEL["N_y best days → mean p_buy, p_sell"]
    Q["q(k) per cycle"] --> Y{"For each year y"}
    Y --> W["Working cycles:<br/>q ≥ q_ret and not retired earlier"]
    W --> EO["E_out = C·DoD·Σq"]
    EO --> EI["E_in = E_out / η"]
    EO --> R["Revenue = E_out (p+s)"]
    EI --> CC["Charging cost = E_in p"]
    SEL --> R
    SEL --> CC
    FEE["Grid fees: 0 to 2029 (ERSE),<br/>then chosen scenario"] --> CF
    TAX["IRC 19/18/17 %<br/>after depreciation"] --> CF
    R --> CF["CF_y = Revenue − Charging − OPEX − fees − tax<br/>(nominal, +2 %/year)"]
    CC --> CF
    CF --> NPV["NPV, IRR, payback"]
    EO --> LCOS["LCOS"]
    CC --> LCOS
```

### 7.2 Electricity prices

`scripts/download_omie_prices.py` downloads one calendar year of hourly marginal prices of
the Portuguese zone of the Iberian day-ahead market (OMIE) with the OMIEData package and
writes `src/battery_twin/data/omie_prices_pt_<year>.csv` (date, hour, €/MWh). The dashboard
uses the most recent file. Without a file, it falls back to the old fixed price and spread
and shows a warning. Since 1 October 2025 the day-ahead market clears in 15-minute periods.
OMIEData's reader keeps only the first 25 values of those files (00:00–06:15), so the script
reads the files itself and averages the quarter-hours to hours. The file in the repository
was made with the original reader, so it keeps only 1 January to 30 September 2025 (273
days); running the script again gives the full year.

### 7.3 Inputs and their sources

All dollar values are converted at the ECB 2025 average of 1.1300 USD per EUR.

| Input | Value | Source |
|---|---|---|
| CAPEX (whole system) | LFP and Na-ion €284/kWh; NMC €298/kWh; NCA €303/kWh | NREL (Cole et al. 2025): $321/kWh for a 4-hour system in 2025 (mid); NREL's system is LFP based. Plus the cell-price difference to LFP from Benchmark Mineral Intelligence's June 2025 assessment (weighted averages: LFP $50.2, NCM $66.0, NCA $71.7/kWh). Sodium-ion: Keiner et al. (2026) estimate sodium-ion cells at about 93 €/kWh in 2023, the same as LFP. The previous version used BNEF's pack prices (LFP $81, NMC $128), which mix regions and segments, and had no NCA or sodium-ion price |
| Electricity buying price p and spread s | From the hourly prices | OMIE, Portugal (Section 7.2) |
| Round-trip efficiency η_RT | Simulated cell efficiency × 83/91 (= 0.912) | PNNL-27237 (Viswanathan et al. 2018), Table 2.2: on a 1 MW lithium-ion battery at 1C, 91 % without and 83 % with auxiliary loads and rest periods. The previous factor (0.91) was chosen to match NREL's 85 %; the measured ratio gives the same value. Check: LFP at the default settings gives 85 % (NREL 85 %; PNNL 2020 measured 83–87 %). Schimpe et al. (2018) found 70–80 % for a small low-voltage system, where power electronics and auxiliaries weigh more |
| Depth of discharge | Simulated cycle (100 %) | Physics model. Earlier versions assumed 80 % while the ageing model used 100 %; now both use the same cycle |
| Operation and maintenance | $1.53/kWh per year (€1.35), +2.5 %/year; warranty 0.9 % of CAPEX per year from year 3 | Lazard LCOS 7.0 (2021). Lazard's augmentation cost (3 % of equipment) is left out, because the program models the fade and retirement itself |
| Project lifetime Y | 15 years | NREL (Cole et al. 2025) |
| Discount rate r | 7.4 % | Steffen (2020), Table 2: after-tax WACC for Portugal (onshore wind, the closest technology with data), at 2017 interest rates. High case: Lazard's financing (80 % equity at 12 %, 20 % debt at 8 %, 21 % tax) = 10.9 % |
| Cycles per year N_y | From the sidebar (default 365) | Setting |
| Retirement threshold q_ret | 70 % | Setting. Default = the LCA's end of service life (CFB-IND: ≥ 70 %), so TEA and LCA describe the same service life (ISO/TS 14076). The previous default was 50 %, where the ageing data end |
| Grid fees | 0 until the end of 2029; afterwards a choice | ERSE Regulamento Tarifário (Regulamento n.º 1218/2025), art. 56: storage that does not take part in self-consumption is exempt from network access tariffs on energy that is later fed back, until the end of 2029. ERSE Orientação n.º 1/2026: system regulation charges are exempt on charging, and on injection below 10 MVA. From 2030 the choice is: exemption continues (default), MT access tariff or BTE access tariff (2026 values, ERSE Diretiva 10/2025, art. 15): energy in "horas cheias" (MT €0.0182/kWh, BTE €0.0353/kWh), the midday hours in which the battery charges, plus contracted power (MT €0.0458, BTE €0.0563 per kW per day) at the charging power |
| Corporate income tax (IRC) | 19 % (2026), 18 % (2027), 17 % (2028 onwards) | EY Tax Alert on the 2026 State Budget (Proposta de Lei n.º 16/XVII, approved by Parliament on 18 September 2025). Straight-line depreciation over the project lifetime, losses carried forward, no municipal or state surcharges (assumptions). The reduced 15 % rate for SMEs on the first €50,000 is not applied |
| Inflation and start year | 2 % a year; operation from 2026 | Assumptions (ECB inflation target). Needed because the discount rate is nominal |
| Second-life battery | $72/kWh (range $44–180) | Dong et al. (2023), review: repurposed EV battery prices, including collection, testing and repackaging |

The earlier default values were CAPEX NMC 125, LFP 95, NCA 130, Na-ion 90 €/kWh (battery
only, indicative), electricity price 0.20 €/kWh, spread 0.10 €/kWh, round-trip efficiency
0.90, depth of discharge 0.80, discount rate 7 % and OPEX 1.5 % of CAPEX. All were
assumptions.

**Not included:** disposal or recycling costs, ancillary-service revenues and intraday
trading. Earlier versions also left out grid fees, taxes and inflation; these are now
included (ERSE's 2026 tariff announcement, the first source checked, gives only the yearly
changes, so the tariff regulation and directive themselves are used).

### 7.4 Sensitivity and second life

- **Tornado chart (ISO/TS 14076, sensitivity analysis):** the NPV change when CAPEX, the
  electricity price level, the arbitrage spread, the discount rate, the round-trip
  efficiency or the O&M cost change by ±20 %, one at a time.
- **Documentation (ISO/TS 14076, clause 7):** the Economics tab shows the yearly cash flows
  and downloads them as CSV, and downloads every input with its source or status as JSON.
- **Second life:** an EV battery reused for stationary storage after a given number of
  cycles. The same `calculate_tea` is used, starting at that cycle. CAPEX is replaced by
  the second-life system cost: the repurposed battery plus a new balance of system (NREL
  system cost minus the BNEF stationary pack price, $251/kWh). Earlier versions used only a
  repurposing cost (default €20/kWh).
- **Comparison:** the "Compare chemistries" tab runs all four chemistries through the same
  function with the same inputs (except their own CAPEX), so the main result, the
  sensitivity, the second-life value and the comparison always agree.

---

## 8. Screening life cycle assessment (environment)

A screening LCA gives CO2eq, water and ecotoxicity. The carbon footprint was originally
computed from the data sheet and pack size only. It now also uses the ageing curve, because
the functional unit is the energy delivered over the service life. The full report that the
dashboard downloads is described in Section 8.6.

### 8.1 Goal and scope (ISO 14044 §4.2)

- **Goal:** to estimate, at screening level, the climate change, water consumption and
  freshwater ecotoxicity of the simulated battery per unit of service, and to show how the
  operating conditions (through ageing) change them.
- **Statement:** *a screening LCA following ISO 14040/14044, not critically reviewed.* The
  results are not suitable for comparative assertions disclosed to the public (ISO 14044
  §5.2 and §6).
- **Functional unit:** 1 kWh of energy delivered by the battery over its service life
  (Regulation (EU) 2023/1542, Annex II; CFB-IND rules).
- **Reference flow:** the battery mass needed per functional unit,
  m_pack / E_total, where m_pack = C_pack / (specific energy).
- **System boundary:**

```mermaid
flowchart LR
    subgraph IN["Included"]
        direction TB
        RM["Raw materials and<br/>cell manufacturing<br/>(cradle-to-gate, cell level)<br/>Degen et al. 2024"]
        USE["Use phase: battery losses<br/>E_total (1/η − 1) × grid intensity<br/>(reported separately)"]
        EOL["End of life: recycling credit<br/>(assumption, reported separately)"]
    end
    subgraph OUT["Excluded (cut-off)"]
        direction TB
        PACK["Pack components: housing,<br/>BMS, thermal system<br/>(≈29 % of pack material energy, IVL C444)"]
        TR["Transport and distribution"]
        CFF["Circular Footprint Formula"]
    end
    RM --> USE --> EOL
```

### 8.2 Life cycle inventory and the functional unit (ISO 14044 §4.3)

For stationary storage, the total energy delivered follows CFB-IND §3.2.1. Each cycle
delivers the pack capacity times its remaining capacity fraction, until the capacity first
falls below the end-of-service-life threshold q_EoL (≥ 70 %). The service life is also
limited to Y_s · min(N_y, 1000) cycles:

```math
E_{\text{total}} = C_{\text{pack}} \sum_{k=1}^{n^*} q_k,
\qquad
n^* = \min\!\left(\min\{k : q_k < q_{\text{EoL}}\},\ Y_s\cdot\min(N_y, 1000)\right)
```

For the electric-vehicle case, the CFB-EV rule is used: E_total = lifetime distance ×
consumption (default 200,000 km × 0.16 kWh/km).

The inventory table of the report labels each input as one of the following:

- *Setting*: a dashboard input.
- *Simulated*: from PyBaMM, such as the cell capacity and energy, the mean cell temperature,
  and the round-trip efficiency (the mean simulated energy efficiency, clipped to 0.70–0.98).
- *Calculated*: such as the cycles counted, E_total and the battery losses.
- *Literature*: the production factors.
- *Assumption*: the grid intensity (210 g CO₂eq/kWh), the specific energy and the recycling
  credit.

### 8.3 Impact assessment (ISO 14044 §4.4)

The characterisation follows ReCiPe 2016 v1.03, hierarchist perspective, as used by Degen et
al. (2024) with ecoinvent 3.10. Only the mandatory elements are applied (classification and
characterisation). There is no normalisation or weighting.

| Impact category | Indicator | Unit |
|---|---|---|
| Climate change | GWP100 | kg CO₂eq |
| Water use | Water consumption potential (WCP) | m³ |
| Toxicity | Freshwater ecotoxicity potential (FETP) | kg 1,4-DCB eq |

The EF 3.1 indicators AWARE (water scarcity) and USEtox (ecotoxicity, CTUe) were requested
but are not available for these cells in the sources at hand (GREET does not provide them
either), so the ReCiPe indicators above are used. Production factors per kWh of **cell**
capacity were read from Degen et al. (2024), Fig. 6 and 7 (`data/lca_degen2024.csv`):

| Chemistry (Degen cell) | Configuration | GWP [kg CO₂eq/kWh] | WCP [m³/kWh] | FETP [kg 1,4-DCB eq/kWh] |
|---|---|---|---|---|
| NCA | High energy (used) | 61.6 | 3.67 | 12.9 |
| NCA | High power (sensitivity) | 67.8 | 3.73 | 20.9 |
| NMC (NMC811) | High energy | 64.7 | 4.02 | 13.8 |
| NMC (NMC811) | High power | 71.3 | 4.09 | 22.3 |
| LFP | High energy | 58.5 | 0.91 | 16.0 |
| LFP | High power | 69.3 | 1.02 | 30.2 |
| Na-ion (NaNFM442) | High energy | 74.0 | 2.62 | 4.2 |
| Na-ion (NaNFM442) | High power | 86.1 | 2.71 | 4.9 |

Degen's sodium-ion cell has a layered-oxide cathode, whereas the physics model uses NVPF.
The water axis of Degen's Fig. 7 has rounded labels and was read linearly as 0–7 m³/kWh.

The impacts per functional unit are:

```math
\text{CF}_{\text{reg}} = \frac{C_{\text{pack}}\,\text{GWP}_{\text{prod}} - m_{\text{pack}}\,e_{\text{EoL}}}{E_{\text{total}}},
\qquad
\text{CF}_{\text{use}} = \text{CF}_{\text{reg}} + \frac{E_{\text{total}}\,(1/\eta_{\text{RT}} - 1)\,g_{\text{grid}}}{E_{\text{total}}}
```

```math
\text{WCP}_{\text{FU}} = \frac{C_{\text{pack}}\,\text{WCP}_{\text{prod}}}{E_{\text{total}}},
\qquad
\text{FETP}_{\text{FU}} = \frac{C_{\text{pack}}\,\text{FETP}_{\text{prod}}}{E_{\text{total}}}
```

CF_reg is the footprint in the scope of the regulation (production and end of life; the use
phase is excluded). CF_use adds the energy lost in the battery. Water and ecotoxicity are
assessed for production only, so the use and end-of-life rows show "not assessed".

### 8.4 Interpretation (ISO 14044 §4.5)

The report identifies the significant issues (the production share), checks completeness
(the cut-off of pack components), and checks consistency. It also runs a one-at-a-time
sensitivity analysis on the carbon footprint:

| Variant | Purpose |
|---|---|
| High-power cell configuration (Degen HP) | Production data uncertainty |
| No end-of-life recycling credit | Unsourced assumption |
| Grid carbon intensity −50 % / +50 % | Use-phase assumption |
| Round-trip efficiency −5 %-points | Simulated value uncertainty |
| End of service life at 80 % instead of 70 % | CFB-IND threshold choice |
| Service life cap halved | Calendar life uncertainty |

As a cross-check, the production result is compared at pack level with Llamas-Orozco et al.
(2023): NMC 77.4, NCA 82.3, LFP 55.0 kg CO₂eq/kWh.

### 8.5 Regulatory context

Regulation (EU) 2023/1542 (Art. 7, Annex II) requires a carbon footprint declaration for
EV, LMT and rechargeable industrial batteries above 2 kWh. The JRC rules (CFB-EV 2023;
CFB-IND, Andreasi Bassi et al. 2025) define the functional unit, the total energy, the use
of the Circular Footprint Formula and primary-data requirements. This tool follows the
functional-unit and total-energy rules but does **not** apply the Circular Footprint Formula
and does not use primary data, so it is a screening estimate, not a declaration.

### 8.6 Downloadable report

The Environment tab's **"Download screening LCA report (PDF)"** button generates a report
from the current simulation (`lca_report.build_lca_report`, ReportLab). It covers the five
ISO 14040/14044 elements:

```mermaid
flowchart TD
    R1["1. Goal and scope<br/>FU, reference flow, system boundary, cut-off,<br/>allocation and EoL, impact categories,<br/>data quality requirements, assumptions,<br/>critical review: none"]
    R2["2. Life cycle inventory<br/>inventory table (setting / simulated / calculated /<br/>literature / assumption), calculation procedures, validation"]
    R3["3. Life cycle impact assessment<br/>mandatory elements only; results per stage and per FU"]
    R4["4. Interpretation<br/>significant issues, completeness, sensitivity,<br/>Llamas-Orozco cross-check, consistency, conclusions"]
    R5["5. Reporting<br/>statement, run settings, references"]
    R1 --> R2 --> R3 --> R4 --> R5
```

Every page carries the footer *"A screening LCA following ISO 14040/14044, not critically
reviewed"*.

---

## 9. Results at the default settings

Default settings: 20 °C ambient, forced air / passive cooling (h = 25 W/m²K), 0.3C charge,
1C discharge, 1,000 cycles, 365 cycles per year, 60 kWh pack, SPMe (DFN for sodium-ion).
TEA inputs as in Section 7.3 (retired at 70 %, grid fees exempt after 2029, income tax), with OMIE prices for January–September 2025 (Section 7.2). LCA: stationary, end of service life at 70 %, 15-year cap,
simulated round-trip efficiency, 210 g CO₂eq/kWh.

| Quantity | NMC | LFP | NCA | Na-ion |
|---|---|---|---|---|
| Simulated cell capacity [Ah] | 4.64 | 1.94 | 0.47 | 1.34 |
| Simulated cell energy [Wh] | 16.28 | 5.97 | 1.72 | 4.20 |
| Mean cell temperature while cycling [°C] | 21.7 | 20.4 | 20.0 | 20.0 (isothermal) |
| Simulated energy efficiency [%] | 91.0 | 93.3 | 98.4 | 78.1 |
| Whole-system round-trip efficiency used in the TEA [%] | 83 | 85 | 90 | 71 |
| System cost (CAPEX) [€/kWh] | 298 | 284 | 303 | 284 |
| Cycles to 80 % (range ±5 °C or best/worst cell) | 373 (327–404) | 1,229 (1,127–1,334) | 341 (319–362) | 201 (201–2,001) |
| Capacity after 1,000 cycles [%] | 67.8 | 83.2 | 56.4 | < 50 |
| NPV [€] (retired at 70 %, grid fees exempt, after tax) | −14,952 | −10,639 | −15,872 | −15,906 |
| LCOS [€/kWh] (before tax) | 0.530 | 0.258 | 0.712 | 1.241 |
| Retired in the TEA (below 70 %) in year | 3 | 6 | 2 | 1 |
| Reaches 50 % (end of the ageing data) in year | 7 | 10 | 4 | 2 |
| NPV [€] if retired at 50 % instead | −11,691 | −8,091 | −14,561 | −15,479 |
| Energy delivered to 70 % [MWh] | 41.3 | 97.8 | 29.6 | 15.3 |
| Carbon footprint, regulation scope [g CO₂eq/kWh] | 70.6 | 27.5 | 89.5 | 262.3 |
| Carbon footprint incl. losses [g CO₂eq/kWh] | 91.2 | 42.5 | 93.8 | 321.3 |
| Water consumption [L/kWh] | 5.84 | 0.56 | 7.45 | 10.28 |
| Freshwater ecotoxicity [g 1,4-DCB eq/kWh] | 20.1 | 9.8 | 26.2 | 16.5 |

**Discussion.**

- **Lifetime ranking.** LFP outlasts NMC by a factor of about 3.3. That is consistent with
  Ohneseit et al. (2025), whose LFP and NMC 21700 cells were cycled by the same lab under
  the same protocol (about 1,600 vs about 500 cycles to 80 %). NCA (Panasonic NCR18650B)
  lasts about as long as NMC, as in Preger et al. (2020) and Wittman et al. (2023) (about
  430 and 460 cycles to 80 % at 25 °C, 1C).
- **Lifetime drives the footprint per kWh.** LFP has a similar production footprint per kWh
  of capacity (58.5 vs 64.7 kg CO₂eq/kWh for NMC). Its footprint per kWh *delivered* is about
  2.6 times lower than NMC's, because it delivers about 2.4 times more energy before reaching
  70 %. Sodium-ion has the lowest ecotoxicity per kWh of capacity (4.2 kg 1,4-DCB eq/kWh), but
  at the measured worst-case fade rate (0.1 %/cycle) it delivers so little energy that every
  indicator per kWh delivered is the highest except ecotoxicity. At 0.01 %/cycle the ranking
  changes completely, which shows how sensitive the result is to that one input.
- **Economics.** With real 2025 prices, the daily cycle buys at a mean of €26/MWh (midday
  solar hours, sometimes below zero) and sells at €121/MWh (evening), a margin of about
  €0.09 per kWh delivered. Every day of the price data was profitable. Even so, no chemistry
  pays back a sourced system cost of €284–303/kWh with day-ahead arbitrage alone: at one
  cycle a day, LFP's after-tax cash flow is about €1,700 in the first year (2026), falling
  as the battery fades, against €17,000 of investment, and it reaches 70 % capacity, the
  end of service life shared with the LCA, in year 6. CAPEX and the spread move the NPV
  most, then the round-trip efficiency (tornado chart). Grid fees do not matter for NMC and
  NCA, which are retired before the exemption ends in 2029; for LFP, the MT access tariff
  from 2030 lowers the NPV by about €800. Income tax (about €400 for LFP) is paid in the
  first profitable years; the loss when the battery is written off at retirement comes too
  late to recover it. The NPVs here are lower than in the previous version (LFP −€8,572)
  mainly because the battery is retired at 70 % instead of 50 %.
  Commercial batteries usually add ancillary services and use cells rated for several
  thousand cycles. The earlier results (LFP +€575 at an assumed 0.10 €/kWh spread and
  €95/kWh battery-only cost) were optimistic mainly because that cost left out the inverter,
  enclosure and installation, which are about 78 % of NREL's system cost.
- **Second life.** A repurposed battery saves only the pack, about 22 % of a new system's
  cost at 2025 prices, so at the defaults second life does not pay either (NMC after 1,500 EV
  cycles, run down to 50 %: −€14,909).
- **NCA energy efficiency (98.4 %)** reflects the very small Kim 2011 pouch cell at low C-rate
  and is not representative of a commercial NCA cell.

These numbers are generated with the same functions as the dashboard and can be reproduced
there.

---

## 10. Validation and known limitations

### 10.1 Validation summary

```mermaid
flowchart LR
    subgraph PHY["Physics model"]
        V1["NMC lithium loss vs Kirkaldy 2024<br/>train 0.40, test 2.56 %-points RMSE"]
    end
    subgraph EMP["Empirical ageing"]
        V2["NMC: 24 conditions, ×1.38<br/>held-out Kirkaldy: 1.0–1.5 %-points"]
        V3["NCA: Preger, 8 of 9 within ≈15 %"]
        V4["LFP: Ohneseit level; Severson ×1.27"]
        V5["Na-ion: 100 cycles only"]
    end
    subgraph SW["Software"]
        V6["58 automated tests (pytest, CI)"]
    end
```

- **NMC physics** is calibrated to measured LG M50T data (Kirkaldy et al., J. Power Sources
  603, 2024, cycled at 70–85 % state of charge): lithium loss within 0.5 %-points at 28–41 °C;
  2.6 %-points too low at 16 °C (not used in the fit). `python scripts/validate.py`. The
  dashboard shows this comparison under "How accurate is this?".
- **NMC ageing model:** fitted to 24 measured conditions (0–40 °C, 0.33–1.67C charge,
  three labs); typical error x1.4 in cycles to 80 %. It reproduces the main trends:
  5/3C charging at 0 °C fails in about 40 cycles (measured 41), 1C at 25 °C about 300 (282),
  and charging at 40 °C is nearly unaffected by the rate. On the Kirkaldy 70–85 % window
  (not used in the fit) the error is 1.0–1.5 %-points (BLAST-Lite's original: 7–12).
  Worst points: 5/3C at 40 °C (model 395 vs 635), 20–80 % cycling (844 vs 1,650; those cells
  ranged 780–2,150), Wittman's 15 °C cells (303 vs 170). Luh & Blank also show that avoiding
  the bottom 10 % of charge extends life several times; the model's depth-of-discharge term
  cannot capture that. Charging above 5/3C is an extrapolation (the dashboard warns).
- **NCA ageing model** represents the Panasonic NCR18650B: within about 15 % of Preger's
  cycles to 80 % for 8 of 9 tests (0–100 % at 0.5C: 350 vs 240). Newer 21700 NCA cells last
  longer (Ohneseit et al.: about 1,300–1,500 cycles at 20 °C, 1C; model 460). It does not
  capture a late, sudden capacity drop ("knee").
- **Sodium-ion** rests on about 100 measured cycles at C/3; longer runs are extrapolations. The
  0.1 %/cycle comes from the worst of the four commercial sodium-ion cells in Carter et al.; two
  others kept more than 99 % after 100 cycles (< 0.01 %/cycle), and the authors warn against
  generalising from four cells. At 0.1 %/cycle the battery is worn out within about two years of
  daily cycling, so its NPV is negative; the rate can be changed in the sidebar. No
  temperature dependence is applied (Klick et al., Batteries & Supercaps 2025, saw similar fade
  at 25 and 40 °C on another commercial sodium-ion cell). PyBaMM's sodium model is isothermal.
- **LFP** physics (A123) and ageing (Sony-Murata) come from different cells of the same chemistry.
  The Sony-Murata model gave about 8,000 full cycles to 80 %; its cycling term is scaled so
  that 0–100 % cycling at 20 °C and 1C matches the 21700 LFP cell of Ohneseit et al. (about
  1,600; 2C: model 1,590 vs about 1,750). NMC is scaled to the same study, so LFP now lasts
  about 3× longer than NMC (dashboard defaults: about 1,240 vs 370 cycles). Durable cells can
  do much better: Preger's A123 18650 cells reached an estimated 6,400–8,800 (mostly
  extrapolated), so treat LFP life as typical, not best-in-class. Ohneseit's LFP cells also
  showed a sudden drop after about 2,200 cycles, which the model does not capture.
  Fast charging: life is unchanged up to about 2.3C (charge-weighted mean rate) and then
  falls steeply, fitted to Severson's A123 cells (3.6–8C, 30 °C; typical error x1.27 over
  82 cells). Severson's 2017-06-30 batch was left out because the same charging policies
  gave much shorter lives than in the other two batches. There are no data between 0.5 and
  3.6C for this cell, and none for LFP fast charging below 30 °C; the model has no cold-charge
  penalty for LFP, so cold results are optimistic (the dashboard warns below 20 °C).
- **Shaded range:** the capacity chart shows the result for a cell 5 °C cooler and 5 °C hotter
  (lithium) or for the best and worst measured commercial cells, 0.01–0.1 %/cycle (sodium-ion).
  It shows how sensitive the result is to that input, not a statistical confidence interval.
- All curves stop at 50 % capacity, where the data end. The dashboard warns whenever the
  temperature, charge/discharge rate or cycle count is outside the measured conditions. The
  default settings (20 °C, 0.3C charge, 1C discharge) are inside the data for NMC, LFP and NCA.
- **NCA** uses the Kim 2011 parameter set, a small pouch cell (about 1.7 Wh), so a pack needs
  many more cells than with the other chemistries.
- Costs, carbon, water and ecotoxicity factors are indicative assumptions, not sourced data.
  **Update:** this still holds for costs (CAPEX), the recycling credit, the specific energy
  and the grid carbon intensity. The production carbon, water and ecotoxicity factors now
  come from Degen et al. (2024) (Section 8.3).

### 10.2 Further methodological limitations

- **Representative cycle.** The ageing projection assumes that the last simulated cycle
  repeats unchanged. In reality the cell's resistance grows and its temperature and voltage
  limits are reached earlier, which changes the stress factors. The aged windows of the
  Physics tab show this effect, but it is not fed back into the projection.
- **Additive mechanisms.** Calendar and cycling losses are added. Interactions (for example,
  plating that accelerates SEI growth) and a sudden capacity drop ("knee") are not modelled.
- **Chemistry mismatch between models.** For LFP (A123 vs Sony-Murata vs Ohneseit 21700), NCA
  (Kim pouch vs Panasonic 18650B) and sodium-ion (NVPF physics vs NaNFM442 LCA data), the
  physics, the ageing and the LCA data describe different cells of the same chemistry.
- **Data extraction.** Most fitted points were read from published figures, not from raw data
  files. That adds a reading error of the order of a few percent.
- **Single-cell scale-up.** The pack is the cell times the number of cells. There is no
  cell-to-cell variation, no thermal gradients and no balancing.
- **LCA.** Screening level: secondary data, cell level only, no Circular Footprint Formula,
  no critical review, and no normalisation or weighting. Not suitable for public comparative
  assertions.
- **TEA.** Earlier versions used a fixed price and spread over the whole project. Now one
  year of hourly prices is repeated over the whole project: no price trend, no inflation.
  The daily dispatch has perfect foresight of the day's prices, so the revenue is an upper
  bound for day-ahead arbitrage. Prices and grid fees rise with an assumed 2 % inflation.
  Other limitations: no degradation of the efficiency, no replacement, no subsidies, no
  disposal cost and no ancillary services. The tax model is simplified (straight-line
  depreciation, no derramas, unlimited loss carry-forward) and the grid-fee rule after
  2029 is unknown. Costs are US (NREL) and global (Benchmark) values converted to euro;
  European system costs may differ. The discount rate is for onshore wind, which is
  probably less risky than merchant storage. The structure follows ISO/TS 14076,
  IEC 60300-3-3 and ISO 15686-5 as far as their public contents show; conformity with
  their full text has not been checked.

---

## 11. Software implementation, testing and reproducibility

### 11.1 Repository layout

```
app.py                      Streamlit dashboard
src/battery_twin/
    chemistry.py            chemistry table, PyBaMM physics, battery test
    ageing.py               empirical ageing models and validity warnings
    sources.py              all published sources (shown in the Sources tab)
    economics.py            TEA        environment.py   LCA
    lca_report.py           screening LCA report (PDF, ISO 14040/14044 structure)
    calibration.py          NMC physics calibration against Kirkaldy et al. 2024
    data/                   measured data (CC-BY-4.0) and calibration.json, read by chemistry.py
        calibration.json            result of the NMC calibration
        kirkaldy2024/               Kirkaldy et al. 2024 processed data (6 cells)
        published_ageing.csv        46 points read from published ageing studies
        severson2019_cycle_life.csv Severson et al. 2019, Supplementary Table 9 (124 cells)
        lca_degen2024.csv           production impacts per kWh, Degen et al. 2024
        omie_prices_pt_<year>.csv   hourly OMIE day-ahead prices, Portugal
    _vendor/blast_lite/     subset of NREL BLAST-Lite (BSD-3-Clause), patched for NumPy 2
scripts/                    run_single, study_temperature, study_charge_rate,
                            export_csv, calibrate, validate, fit_ageing (outputs go to ./results)
tests/                      pytest suite (physics, ageing, economics, dashboard)
```

### 11.2 Main functions

| Function | File | Purpose |
|---|---|---|
| `build_model`, `build_experiment`, `run_simulation` | chemistry.py | PyBaMM model, protocol and solution → DataFrames |
| `run_battery_test` | chemistry.py | Physics (10 cycles) + ageing projection (20,000 cycles) + range + warnings |
| `run_aged_window`, `cycle_windows` | chemistry.py | Aged-cell simulations for the Physics tab |
| `cooling_conditions` | chemistry.py | Cooling option → (h, temperature while cycling) |
| `add_rest`, `predict_capacity`, `validity_warnings` | ageing.py | Real-time cycle period, closed-form capacity fade, range checks |
| `daily_arbitrage`, `arbitrage_prices` | economics.py | Best daily cycle from hourly prices; mean buying and selling prices |
| `system_capex_eur_kwh`, `second_life_capex_eur_kwh` | economics.py | Sourced system costs in euro |
| `calculate_tea`, `sensitivity`, `second_life` | economics.py | Cash flows, NPV, IRR, payback, LCOS |
| `total_energy_kwh`, `calculate_lca` | environment.py | CFB-IND total energy, impacts per phase and per FU |
| `lca_results`, `sensitivity`, `build_lca_report` | lca_report.py | LCA case, sensitivity table, PDF |

### 11.3 Scripts

| Script | Output |
|---|---|
| `scripts/run_single.py` | One battery test, printed |
| `scripts/study_temperature.py`, `scripts/study_charge_rate.py` | Parameter studies (results/) |
| `scripts/export_csv.py` | CSV export of a run |
| `scripts/calibrate.py` | NMC calibration → results/calibration.json and calibration_fit.png |
| `scripts/validate.py` | Physics and empirical NMC models vs Kirkaldy data → results/model_vs_measured.csv |
| `scripts/fit_ageing.py` | Refitted ageing constants and a measured-vs-model table |
| `scripts/download_omie_prices.py` | One year of hourly OMIE prices for Portugal → src/battery_twin/data/omie_prices_pt_<year>.csv |

### 11.4 Verification (automated tests)

58 tests (`pytest -q`, about 1.5 min) run on every push through GitHub Actions
(`.github/workflows/tests.yml`, Python 3.12):

| File | What it verifies |
|---|---|
| `test_physics.py` | Capacity falls with cycles; hotter cells grow more SEI; Coulombic efficiency ≤ 100 %; sodium-ion runs; NMC capacity matches the measured 4.857 Ah and the calibration file is used; first, middle and last windows |
| `test_ageing.py` | Closed form matches BLAST-Lite stepping; published cycles to 80 % (Preger, Wittman, Ohneseit, Luh & Blank, Severson) are reproduced within stated bounds; trends (shallow cycling, heat, fast/cold charging, rest); sodium-ion fade; range band; warnings |
| `test_cooling.py` | Cooling options, pre-conditioning, longer NMC life with pre-conditioning in the cold |
| `test_economics_environment.py` | TEA retirement and cash flows; cash-flow table adds up; grid fees only after 2029; income tax rates and loss carry-forward; daily arbitrage (buys cheap, sells dear, charges before discharging); sourced costs; CFB-IND total energy (70 % threshold, 1000 cycles/year cap); Degen data; PDF report for all chemistries |
| `test_app.py` | The dashboard runs end to end for every chemistry; cooling warnings; Sources tab |

### 11.5 Reproducibility

All inputs to the fitted models are in `src/battery_twin/data/` as plain CSV/JSON files with
their source in each row. The calibration and the fits can be re-run with the scripts above.
The physics results depend on the PyBaMM version (≥ 25.10).

---

## 12. Conclusions and future work

### 12.1 Conclusions

1. A hybrid digital twin, with physics for the short time scale and empirical ageing for the
   long one, gives voltage, thermal and lifetime results in seconds. Every ageing parameter
   can be traced to a published measurement.
2. Refitting the BLAST-Lite cycling terms was necessary. The original NCA term overestimated
   life about twelve-fold. The original NMC term had the wrong sign of the temperature
   effect for cycling and no charge-rate effect.
3. Charge rate and temperature while charging dominate NMC life (lithium plating). The cooling
   strategy and pre-conditioning therefore have a first-order effect on lifetime, and so on
   the economics and the footprint per kWh delivered.
4. Because the functional unit is energy delivered, the environmental ranking of chemistries
   depends as much on cycle life as on production impacts: at the default settings LFP has
   the lowest carbon footprint per kWh delivered, although its production footprint per kWh
   of capacity is similar to NMC's.

### 12.2 Future work

- Feed resistance growth back into the projection (iterate physics and ageing windows).
- Model the knee and the extra life from avoiding the lowest state of charge (Luh & Blank).
- Add an LFP cold-charge (plating) term once data below 30 °C at high C-rate are available.
- Use EF 3.1 indicators (AWARE, USEtox) and pack-level inventories, apply the Circular
  Footprint Formula, and commission a critical review for any public comparative use.
- Use several years of prices and a price outlook, add intraday and ancillary-service revenues, and Portuguese grid fees.
- Gather more sodium-ion ageing data beyond 100 cycles.

---

## 13. Development

This project was developed with AI assistance (Claude, by Anthropic). The AI wrote most of
the code and helped find and evaluate the published data and models it builds on. I defined
the goals and requirements, chose the direction at each step, ran and tested the code on my
own machine, reported problems and decided which results to keep.

---

## 14. Licences and credits

Code: MIT (see `LICENSE`). Vendored BLAST-Lite: BSD-3-Clause, © Alliance for Energy
Innovation (NREL), see `src/battery_twin/_vendor/blast_lite/`. Kirkaldy et al. data:
CC-BY-4.0, https://doi.org/10.5281/zenodo.10637534. PyBaMM parameter sets are cited by
name in `chemistry.py`. See `src/battery_twin/data/published_ageing.csv`: values read 
from the figures and text of Preger et al. 2020, Wittman et al. 2023, Ohneseit et al. 
2025 and Luh & Blank 2024 (see the file and the Sources tab); credit and licences 
belong to those publications. See `src/battery_twin/data/severson2019_cycle_life.csv`: 
Severson et al., Nature Energy 4,383 (2019), Supplementary Table 9.
See `src/battery_twin/data/lca_degen2024.csv`: values read from Degen et al., Journal of
Industrial Ecology (2024), Fig. 6 and 7; credit belongs to that publication.

---

## 15. References

**Physics and calibration**

1. Sulzer V., Marquis S. G., Timms R., Robinson M., Chapman S. J. (2021). Python Battery Mathematical Modelling (PyBaMM). *Journal of Open Research Software* 9(1), 14. https://doi.org/10.5334/jors.309
2. Chen C.-H., Brosa Planella F., O'Regan K., Gastol D., Widanage W. D., Kendrick E. (2020). Development of experimental techniques for parameterization of multi-scale lithium-ion battery models. *J. Electrochem. Soc.* 167, 080534. https://doi.org/10.1149/1945-7111/ab9050
3. Prada E. et al. (2013). A simplified electrochemical and thermal aging model of LiFePO4-graphite Li-ion batteries. *J. Electrochem. Soc.* 160, A616. https://doi.org/10.1149/2.053304jes
4. Kim G.-H., Smith K., Lee K.-J., Santhanagopalan S., Pesaran A. (2011). Multi-domain modeling of lithium-ion batteries encompassing multi-physics in varied length scales. *J. Electrochem. Soc.* 158, A955. https://doi.org/10.1149/1.3597614
5. Chayambuka K. et al. (2022). Physics-based modeling of sodium-ion batteries part II. Model and validation. *Electrochimica Acta*.
6. O'Kane S. E. J. et al. (2022). Lithium-ion battery degradation: how to model it. *Phys. Chem. Chem. Phys.* 24, 7909. https://doi.org/10.1039/D2CP00417H
7. Kirkaldy N., Samieian M. A., Offer G. J., Marinescu M., Patel Y. (2024). Lithium-ion battery degradation: comprehensive cycle ageing data and analysis for commercial 21700 cells. *J. Power Sources* 603, 234185. https://doi.org/10.1016/j.jpowsour.2024.234185. Dataset: https://doi.org/10.5281/zenodo.10637534
8. Incropera F. P., DeWitt D. P., Bergman T. L., Lavine A. S. *Fundamentals of Heat and Mass Transfer*, Table 1.1.

**Ageing**

9. NREL BLAST-Lite, battery lifetime models (Gasper P. et al.). https://github.com/NREL/BLAST-Lite
10. Truong Bui et al. (2021). IEEE: LG M50 ageing data used by BLAST-Lite.
11. Luh M., Blank T. (2024). Comprehensive battery aging dataset: capacity and impedance fade measurements of a lithium-ion NMC/C-SiO cell. *Scientific Data* 11, 1004. https://doi.org/10.1038/s41597-024-03831-x
12. Preger Y. et al. (2020). Degradation of commercial lithium-ion cells as a function of chemistry and cycling conditions. *J. Electrochem. Soc.* 167, 120532. https://doi.org/10.1149/1945-7111/abae37
13. Wittman R. M. et al. (2023). Characterization of cycle-aged commercial NMC and NCA lithium-ion cells: I. Temperature-dependent degradation. *J. Electrochem. Soc.* 170, 120538. https://doi.org/10.1149/1945-7111/ad1450
14. Ohneseit S. et al. (2025). Aging behavior beyond SOH 80: an experimental aging study on commercial lithium-ion batteries with different cathode materials. *Batteries & Supercaps*. https://doi.org/10.1002/batt.202400713
15. Severson K. A. et al. (2019). Data-driven prediction of battery cycle life before capacity degradation. *Nature Energy* 4, 383. https://doi.org/10.1038/s41560-019-0356-8
16. Naumann M. et al. (2018, 2020). *J. Energy Storage* and *J. Power Sources*. Model identification: Gasper P. et al. (2022), *J. Electrochem. Soc.* https://doi.org/10.1149/1945-7111/ac86a8
17. Keil P. et al. (2016). Calendar aging of lithium-ion batteries. *J. Electrochem. Soc.* 163, A1872. https://doi.org/10.1149/2.0411609jes
18. Carter et al. (2025). *Energies* 18, 661.
19. Klick et al. (2025). *Batteries & Supercaps*.

**Environment (LCA)**

20. ISO 14040:2006 and ISO 14044:2006 (with amendments). Environmental management – Life cycle assessment.
21. Regulation (EU) 2023/1542 concerning batteries and waste batteries, Article 7 and Annex II. https://eur-lex.europa.eu/eli/reg/2023/1542/oj
22. Andreasi Bassi S. et al. (2025). Rules for the calculation of the Carbon Footprint of industrial Batteries without external storage (CFB-IND). JRC, EUR 40286. https://doi.org/10.2760/6346639
23. JRC (2023). Harmonised rules for the calculation of the Carbon Footprint of Electric Vehicle Batteries (CFB-EV). https://eplca.jrc.ec.europa.eu/GRB-CBF_CarbonFootprintRules-EV.pdf
24. Degen F., Mitterfellner M., Kampker A. (2024). Comparative life cycle assessment of lithium-ion, sodium-ion, and solid-state battery cells for electric vehicles. *Journal of Industrial Ecology*. https://doi.org/10.1111/jiec.13594
25. Llamas-Orozco J. A. et al. (2023). Estimating the environmental impacts of global lithium-ion battery supply chain. *PNAS Nexus* 2(11), pgad361. https://doi.org/10.1093/pnasnexus/pgad361
26. Emilsson E., Dahllöf L. (2019). Lithium-ion vehicle battery production – status 2019. IVL Swedish Environmental Research Institute, report C 444.
27. Huijbregts M. A. J. et al. (2017). ReCiPe2016: a harmonised life cycle impact assessment method at midpoint and endpoint level. *Int. J. Life Cycle Assess.* 22, 138–147. https://doi.org/10.1007/s11367-016-1246-y

**Economics (TEA)**

28. OMIE, Iberian electricity market operator: day-ahead market hourly marginal prices, Portuguese zone. https://www.omie.es (downloaded with the OMIEData package, https://pypi.org/project/OMIEData)
29. Cole W., Ramasamy V., Olmez Turan M. (2025). Cost Projections for Utility-Scale Battery Storage: 2025 Update. NREL/TP-6A40-93281. https://docs.nrel.gov/docs/fy25osti/93281.pdf
30. NREL Annual Technology Baseline, Utility-Scale Battery Storage. https://atb.nlr.gov/electricity/2025/utility-scale_battery_storage
31. BloombergNEF (2025). Lithium-ion battery pack prices fall to $108 per kilowatt-hour despite rising metal prices. https://about.bnef.com/insights/clean-transport/lithium-ion-battery-pack-prices-fall-to-108-per-kilowatt-hour-despite-rising-metal-prices-bloombergnef/
32. Lazard (2021). Lazard's Levelized Cost of Storage Analysis, version 7.0.
33. Steffen B. (2020). Estimating the cost of capital for renewable energy projects. *Energy Economics* 88, 104783. https://doi.org/10.1016/j.eneco.2020.104783
34. Dong Q., Liang S., Li J., Kim H. C., Shen W., Wallington T. J. (2023). Cost, energy, and carbon footprint benefits of second-life electric vehicle battery use. *iScience* 26, 107195. https://doi.org/10.1016/j.isci.2023.107195
35. European Central Bank euro reference rates: 2025 annual average, 1.1300 USD per EUR (published by the Bank of Finland). https://www.suomenpankki.fi/en/statistics/interest-rates-and-exchange-rates/exchange-rates/average-annual-exchange-rates-for-the-year-2025/
36. ISO/TS 14076:2025. Environmental management — Environmental techno-economic assessment — Principles, requirements and guidance. https://www.iso.org/standard/61119.html
37. IEC 60300-3-3:2017. Dependability management — Part 3-3: Application guide — Life cycle costing. https://webstore.iec.ch/en/publication/31206
38. ISO 15686-5:2017. Buildings and constructed assets — Service life planning — Part 5: Life-cycle costing.
39. IEC 62933-2-1. Electrical energy storage (EES) systems — Part 2-1: Unit parameters and testing methods — General specification.
40. Benchmark Mineral Intelligence (2025). Lithium Ion Battery Cell Price Assessment, June 2025.
41. Keiner D., Jasper F., Bogdanov D., Lopez G., Peters J., Baumann M., Breyer C., Weil M. (2026). Sodium-ion battery cost projections and their impact on the global energy system transition until 2050. *Journal of Energy Storage* 146, 119861. https://doi.org/10.1016/j.est.2025.119861
42. Viswanathan V., Wu D., Crawford A., Hardy T., Alam J., Mongird K., Balducci P. (2018). Snohomish Public Utility District MESA-1: An Assessment of Battery Technical Performance. PNNL-27237. https://www.pnnl.gov/main/publications/external/technical_reports/PNNL-27237.pdf
43. Mongird K., Viswanathan V., Alam J., Vartanian C., Sprenkle V., Baxter R. (2020). 2020 Grid Energy Storage Technology Cost and Performance Assessment (lithium-ion methodology). DOE/PA-0204.
44. Schimpe M., Naumann M., Truong N., Hesse H. C., Santhanagopalan S., Saxon A., Jossen A. (2018). Energy efficiency evaluation of a stationary lithium-ion battery container storage system via electro-thermal modeling and detailed component analysis. *Applied Energy* 210, 211–229. https://doi.org/10.1016/j.apenergy.2017.10.129
45. ERSE (2025). Regulamento Tarifário do setor elétrico, Regulamento n.º 1218/2025 (ERSE n.º 2/2025), article 56.
46. ERSE (2025). Diretiva n.º 10/2025: Tarifas e preços para a energia elétrica e outros serviços em 2026.
47. ERSE (2026). Orientação n.º 1/2026: Aplicação dos encargos de regulação para o sistema às instalações de armazenamento. ERSE (2026). Storage development in Portugal (28 May 2026).
48. EY (2025). Tax Alert: Proposta de Lei do Orçamento do Estado para 2026.

The dashboard's **Sources** tab lists the same sources with what each is used for.

---

## Appendix A: Nomenclature

| Symbol | Meaning | Unit |
|---|---|---|
| a_k | Specific interfacial area of electrode k | m⁻¹ |
| A_cool | Cell cooling surface area | m² |
| C_pack | Pack energy capacity (initial, usable) | kWh |
| c_s, c_e | Lithium concentration in solid, electrolyte | mol m⁻³ |
| c_ch, c_dis | Charge-weighted charge C-rate, mean discharge C-rate | h⁻¹ |
| CF_y | Cash flow in year y | € |
| D_s, D_e, D_sol | Diffusivity in solid, electrolyte, of SEI solvent | m² s⁻¹ |
| DoD | Depth of discharge | – |
| E_SEI | SEI growth activation energy | J mol⁻¹ |
| E_total | Energy delivered over the service life | kWh |
| EFC | Equivalent full cycles | – |
| F, R | Faraday constant, gas constant | C mol⁻¹, J mol⁻¹ K⁻¹ |
| g_grid | Grid carbon intensity | kg CO₂eq kWh⁻¹ |
| h | Total (effective) heat transfer coefficient | W m⁻² K⁻¹ |
| j, j_0 | Interfacial current density, exchange current density | A m⁻³, A m⁻² |
| L_cal, L_cyc | Calendar and cycling capacity loss (fractions) | – |
| N_y | Cycles per year | yr⁻¹ |
| p, s | Electricity price, arbitrage spread | € kWh⁻¹ |
| q(n) | Capacity fraction after n cycles (SOH/100) | – |
| q_ret, q_EoL | Retirement threshold (TEA), end of service life (LCA) | – |
| r | Discount rate | – |
| SOC | State of charge | – |
| T, T_amb, T_ch | Cell, ambient, mean charging temperature | K or °C |
| U_k, U_a | Open-circuit potential of electrode k, anode potential | V |
| η, η_RT | Overpotential; round-trip energy efficiency | V; – |
| φ_s, φ_e | Solid and electrolyte potential | V |
