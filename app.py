"""Battery Digital Twin dashboard. Start it with:  python -m streamlit run app.py"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from battery_twin.ageing import SodiumIonNVPF, add_rest, predict_capacity
from battery_twin.chemistry import (CALIBRATED_H_COOLING, CALIBRATION, CHEMISTRIES, DETAILED_CYCLES, MIN_SOH,
                                    PROJECTION_CYCLES, run_battery_test, standard_profile)
from battery_twin.economics import calculate_tea, second_life, sensitivity
from battery_twin.environment import calculate_lca

# Started with "python app.py" or the editor's Run button: explain and stop.
if not st.runtime.exists():
    sys.exit("This is a Streamlit dashboard. Start it from the project folder with:\n"
             "    python -m streamlit run app.py")

st.set_page_config(page_title="Battery Digital Twin", page_icon="🔋", layout="wide")

VALIDATION_FIGURE = Path(__file__).parent / "docs" / "calibration_fit.png"


@st.cache_data(show_spinner=False)
def simulate(chemistry, model_type, c_charge, c_discharge, n_cycles, ambient_c, h_cooling, na_fade,
             cycles_per_year):
    return run_battery_test(chemistry, model_type, c_charge, c_discharge, n_cycles, ambient_c,
                            h_cooling, na_fade, cycles_per_year)


def table(df):
    st.dataframe(df.round(3), width="stretch", hide_index=True)


def fmt_number(x, decimals=0, missing="n/a"):
    """Format a number; when there is no number, show words instead of a blank dash."""
    if x is None or not math.isfinite(x):
        return missing
    return f"{x:,.{decimals}f}"


# ---------------------------------------------------------------------------
# Sidebar: only the battery test
# ---------------------------------------------------------------------------
st.sidebar.title("🔋 Battery test")
chemistry = st.sidebar.selectbox("Chemistry", list(CHEMISTRIES),
                                 format_func=lambda k: CHEMISTRIES[k]["label"])
n_cycles = st.sidebar.select_slider(
    "Number of cycles", [10, 50, 100, 250, 500, 1000, 2000, 3000, 5000, 10000], value=1000,
    help=f"The first {DETAILED_CYCLES} cycles are simulated with the physics model; "
         "capacity fade is predicted by an empirical model fitted to measured data.")
c_charge = st.sidebar.select_slider("Charge rate (C)", [0.3, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0], value=0.3,
                                    help="1C = full charge in about one hour.")
c_discharge = st.sidebar.select_slider("Discharge rate (C)", [0.3, 0.5, 1.0, 1.5, 2.0, 3.0], value=1.0)
ambient_c = st.sidebar.slider("Ambient temperature (°C)", 5, 45, 20, 5,
                              help="The default settings (20 °C, 0.3C charge, 1C discharge) stay "
                                   "inside the measured ageing data for NMC, LFP and NCA.")
cycles_per_year = st.sidebar.number_input(
    "Cycles per year", min_value=12, max_value=3650, value=365, step=1,
    help="How often the battery is cycled in real use (365 = once a day). Between cycles it "
         "rests, and it keeps ageing while resting, so this changes the lifetime as well as "
         "the economics.")
pack_kwh = st.sidebar.number_input("Pack size (kWh)", min_value=0.1, value=60.0, step=5.0,
                                   help="Used for the cell count, economics and environment.")

with st.sidebar.expander("Advanced"):
    detailed = st.checkbox("Detailed physics (DFN, slower)",
                           help="Charging above 2C always uses the detailed model.")
    h_cooling = st.slider("Cooling coefficient h (W/m²K)", 5, 100, int(CALIBRATED_H_COOLING), 1,
                          help="13 W/m²K matches the measured self-heating in Kirkaldy et al. (2024).")

is_sodium = CHEMISTRIES[chemistry]["family"] == "sodium_ion"
na_fade = SodiumIonNVPF.FADE_PER_EFC
if is_sodium:
    na_fade_pct = st.sidebar.number_input(
        "Sodium-ion capacity loss (% per cycle)", min_value=0.0, max_value=1.0,
        value=100 * SodiumIonNVPF.FADE_PER_EFC, step=0.01, format="%.3f",
        help="0.1 % is the measured value for the NVPF cell in Carter et al. (2025), the worst "
             "of the four commercial sodium-ion cells they tested. Two other cells kept more "
             "than 99 % after 100 cycles, i.e. under 0.01 % per cycle.")
    na_fade = na_fade_pct / 100
model_type = "DFN" if (detailed or c_charge > 2.0 or is_sodium) else "SPMe"
if c_charge > 2.0 and not detailed and not is_sodium:
    st.sidebar.caption("Charging above 2C: the detailed model is used automatically.")

inputs = (chemistry, model_type, c_charge, c_discharge, n_cycles, ambient_c, h_cooling, na_fade,
          int(cycles_per_year))
if st.sidebar.button("▶ Run", type="primary", width="stretch"):
    with st.spinner("Simulating..."):
        try:
            st.session_state["result"] = simulate(*inputs)
            st.session_state["inputs"] = inputs
            st.session_state.pop("error", None)
        except Exception as err:
            st.session_state.pop("result", None)
            st.session_state["error"] = str(err)

# ---------------------------------------------------------------------------
# Nothing to show yet
# ---------------------------------------------------------------------------
st.title("Battery Digital Twin")
if "error" in st.session_state:
    st.error("The simulation did not converge. Try a lower charge or discharge rate.\n\n"
             f"Details: {st.session_state['error'][:400]}")
if "result" not in st.session_state:
    st.info("Choose the battery test in the sidebar and press **▶ Run**.")
    st.stop()

result = st.session_state["result"]
chem, model_run, cc_run, cd_run, n_run, t_run, h_run, na_fade_run, _ = st.session_state["inputs"]
cycles_df, series_df, eff_df, meta = result["cycles"], result["series"], result["efficiency"], result["meta"]
if st.session_state["inputs"] != inputs:
    st.warning("The settings have changed. Press **▶ Run** to update the results.")

# Values shared by all tabs
label = CHEMISTRIES[chem]["label"]
cpy_run = meta["cycles_per_year"]          # cycles per year actually used by the ageing
is_sodium_run = CHEMISTRIES[chem]["family"] == "sodium_ion"
soh_final = float(cycles_df["SOH [%]"].iloc[-1])
projection = result["projection"]
data_end = meta["cycles_to_data_end"]
soh_text = f"{soh_final:.1f} %" if math.isfinite(soh_final) else f"below {MIN_SOH:.0f} %"
life_80 = meta["cycles_to_80pct"]
if math.isfinite(life_80):
    life_text = fmt_number(life_80)
else:
    life_text = f"> {PROJECTION_CYCLES:,}"
max_temp = float(cycles_df["Max temperature [°C]"].max())
cells_needed = math.ceil(pack_kwh * 1000 / meta["cell_energy_wh"])

summary_tab, physics_tab, economics_tab, environment_tab, compare_tab, download_tab = st.tabs(
    ["Summary", "Physics", "Economics", "Environment", "Compare chemistries", "Download"])

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
with summary_tab:
    st.subheader(label)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"Capacity left after {n_run:,} cycles", soh_text)
    m2.metric("Cycles until 80 % capacity", life_text)
    m3.metric("Peak cell temperature", f"{max_temp:.1f} °C")
    m4.metric(f"Cells for {pack_kwh:g} kWh", f"{cells_needed:,}")
    st.caption(f"One simulated cell: {meta['cell_capacity_ah']:.2f} Ah, "
               f"{meta['cell_energy_wh']:.2f} Wh. " + CHEMISTRIES[chem].get("cell_note", ""))

    years_80 = life_80 / cpy_run
    st.write(
        f"Charging at **{cc_run:g}C** and discharging at **{cd_run:g}C** at **{t_run} °C**, "
        f"the battery keeps **{soh_text}** of its capacity after **{n_run:,} cycles**. "
        + (f"It reaches 80 % after about **{life_80:,.0f} cycles** "
           f"(≈ {years_80:.1f} years at {cpy_run:,.0f} cycles per year)." if math.isfinite(life_80) else ""))
    if cpy_run < st.session_state["inputs"][-1] - 0.5:
        st.warning(f"One cycle takes {meta['cycle_duration_h']:.1f} hours, so at most "
                   f"{cpy_run:,.0f} cycles fit in a year. The results use that number instead of "
                   f"the {st.session_state['inputs'][-1]:,} you asked for.")

    if not math.isfinite(soh_final):
        st.warning(f"The capacity falls below {MIN_SOH:.0f} % at cycle {data_end:,.0f}. The ageing "
                   "data do not go lower, so the curve stops there instead of guessing.")
    if is_sodium_run:
        st.info(f"**Sodium-ion ageing uses {100 * na_fade_run:.3f} % capacity loss per cycle.** "
                "The measured 0.1 % comes from 100 cycles on one commercial NVPF cell, the worst of "
                "four commercial sodium-ion cells in Carter et al. (2025); two others lost under "
                "0.01 % per cycle. Everything past 100 cycles is a straight-line extrapolation, so "
                "change the rate in the sidebar to see how sensitive the results are.")

    # Shaded range: best and worst case of the uncertain input (see meta["range_basis"]).
    # Where the worst case is already below the data (50 %), the band is drawn down to 50 %.
    high = cycles_df["SOH high [%]"]
    low = cycles_df["SOH low [%]"].fillna(MIN_SOH).where(high.notna())
    fig = go.Figure([
        go.Scatter(x=cycles_df["Cycle"], y=high, mode="lines", line_width=0,
                   showlegend=False, hoverinfo="skip"),
        go.Scatter(x=cycles_df["Cycle"], y=low, mode="lines", line_width=0, fill="tonexty",
                   fillcolor="rgba(99, 110, 250, 0.2)", name=f"Range ({meta['range_basis']})",
                   hoverinfo="skip"),
        go.Scatter(x=cycles_df["Cycle"], y=cycles_df["SOH [%]"], mode="lines",
                   line_color="rgb(99, 110, 250)", name="Expected"),
    ])
    fig.update_layout(title="Capacity over cycles", xaxis_title="Cycle", yaxis_title="SOH [%]",
                      legend=dict(orientation="h", y=-0.2))
    fig.add_hline(y=80, line_dash="dot", annotation_text="80 % (typical end of life)")
    st.plotly_chart(fig, width="stretch")
    lo80, hi80 = meta["cycles_to_80pct_range"]
    st.caption(f"Shaded range: {meta['range_basis']}. Cycles until 80 % capacity: "
               f"{fmt_number(lo80, missing='–')} to "
               f"{fmt_number(hi80, missing=f'over {PROJECTION_CYCLES:,}')}. "
               "It shows how much the result depends on that input; it is not a statistical "
               "confidence interval.")

    # Where the numbers come from, in one place
    st.info(f"**Ageing data:** {CHEMISTRIES[chem]['ageing_source']}. Curves stop at 50 % capacity, where the data end.")
    if meta["ageing_warnings"]:
        st.warning("Outside the conditions of the ageing data, so treat the lifetime as an "
                   "extrapolation: " + "; ".join(meta["ageing_warnings"]) + ".")
    if CHEMISTRIES[chem]["calibration"]:
        st.caption(f"Physics model: {CHEMISTRIES[chem]['calibration']}.")
    if is_sodium_run:
        st.caption("Physics model: PyBaMM's sodium-ion model is isothermal, so the cell "
                   "temperature equals the ambient temperature.")
    if max_temp > 60:
        st.warning("The cell goes above 60 °C, beyond typical test and safety limits.")
    st.caption(f"Cycles 1–{DETAILED_CYCLES} are simulated with the physics model ({model_run}). "
               f"Their state-of-charge swing and cell temperature (mean "
               f"{meta['mean_cell_temperature_c']:.1f} °C) drive the empirical ageing model.")

    with st.expander("How accurate is this?"):
        if chem == "NMC":
            st.write(
                "The NMC physics model was tuned to real measurements: LG M50T cells aged for "
                "258 days in three test chambers (Kirkaldy et al., 2024). The dots are the "
                "measured loss of lithium, the solid lines are this model. The 25 °C and 40 °C "
                "cells were used for tuning; the 10 °C cells were kept aside to test the model "
                "on data it had not seen. The dotted lines show PyBaMM's default settings, which "
                "were about ten times too low.")
            if VALIDATION_FIGURE.exists():
                st.image(str(VALIDATION_FIGURE))
            st.write(
                f"Average error: **{CALIBRATION['rmse_lli_train_pct']:.1f} percentage points** "
                f"on the cells used for tuning and **{CALIBRATION['rmse_lli_test_10C_pct']:.1f} "
                "percentage points** on the unseen 10 °C cells.")
            st.caption("This checks the physics model. The long-term capacity curve comes from a "
                       "separate ageing model fitted by NREL to other LG M50 cells; see the README "
                       "for how it compares with these measurements.")
        else:
            st.write(
                f"The {chem} physics model uses its published parameter set without further "
                "tuning, so it has not been checked against measurements in this project. "
                f"The capacity curve comes from: {CHEMISTRIES[chem]['ageing_source']}.")
            st.caption("Only the NMC model has been compared with real measurements here. "
                       "The shaded range on the chart shows how sensitive the result is.")

# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------
with physics_tab:
    st.caption(f"Voltage and temperature of the {DETAILED_CYCLES} fully simulated cycles.")
    st.plotly_chart(px.line(series_df, x="Time [min]", y="Voltage [V]", color="Cycle",
                            title="Cell voltage"), width="stretch")
    st.plotly_chart(px.line(series_df, x="Time [min]", y="Temperature [°C]", color="Cycle",
                            title="Cell temperature"), width="stretch")
    with st.expander("Efficiency per cycle"):
        table(eff_df)

# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------
with economics_tab:
    with st.expander("Assumptions", expanded=False):
        a1, a2, a3 = st.columns(3)
        capex = a1.number_input("CAPEX (€/kWh)", min_value=0.0, step=5.0,
                                value=CHEMISTRIES[chem]["capex_eur_kwh"], key=f"capex_{chem}")
        price = a1.number_input("Electricity price (€/kWh)", min_value=0.0, value=0.20, step=0.01)
        spread = a1.number_input("Arbitrage spread (€/kWh)", min_value=0.0, value=0.10, step=0.01,
                                 help="Selling price minus buying price.")
        rte = a2.slider("Round-trip efficiency", 0.70, 0.98, 0.90, 0.01)
        years = a2.number_input("Project lifetime (years)", min_value=1, max_value=30, value=15)
        wacc = a3.number_input("Discount rate", min_value=0.0, max_value=0.3, value=0.07, step=0.01)
        retire_pct = a3.slider("Retire the battery below capacity (%)", int(MIN_SOH), 90,
                               int(MIN_SOH), 5,
                               help="Below this capacity the battery stops operating: no more "
                                    "revenue and no more operating costs. The default is where "
                                    "the ageing data end; 60–80 % is common for grid storage.")

    # The economics use the ageing curve itself, cycle by cycle
    soh_curve = projection["SOH [%]"].to_numpy() / 100.0
    tea_inputs = {"soh_curve": soh_curve, "capex_eur_kwh": capex, "capacity_kwh": pack_kwh,
                  "electricity_price": price, "spread": spread, "round_trip_eff": rte,
                  "cycles_per_year": int(round(cpy_run)), "years": int(years), "wacc": wacc,
                  "retire_below": retire_pct / 100.0}
    tea = calculate_tea(**tea_inputs)

    e1, e2, e3, e4 = st.columns(4)
    irr, payback, lcos = tea["IRR [%]"], tea["Discounted payback [years]"], tea["LCOS [€/kWh]"]
    e1.metric("Net present value", f"€{tea['NPV [€]']:,.0f}")
    e2.metric("Internal rate of return",
              f"{irr:.1f} %" if math.isfinite(irr) else "Not defined",
              help="Not defined when the cash flows never add up to a profit at any interest rate.")
    e3.metric("Payback", f"{payback:.0f} years" if math.isfinite(payback) else "Never",
              help=f"Never = the investment is not paid back within the {int(years)}-year project.")
    e4.metric("Cost of stored energy (LCOS)",
              f"€{lcos:.3f}/kWh" if math.isfinite(lcos) else "No energy delivered")
    retired = tea["Retired in year"]
    if retired is None:
        st.caption(f"Investment €{tea['CAPEX [€]']:,.0f}; capacity left after {int(years)} years: "
                   f"{tea['SOH at end [%]']:.1f} %.")
    else:
        st.caption(f"Investment €{tea['CAPEX [€]']:,.0f}; the battery reaches {retire_pct} % "
                   f"capacity and is retired in year {retired} of {int(years)}.")
    if tea["NPV [€]"] < 0 and retired is not None and retired <= int(years) / 2:
        st.warning("The NPV is negative mainly because the battery wears out early: it is retired "
                   f"in year {retired}, before the arbitrage income pays back the investment.")

    sens = sensitivity(tea_inputs)
    fig = go.Figure([
        go.Bar(y=sens["Parameter"], x=sens["ΔNPV at -20% [€]"], orientation="h", name="Input −20 %"),
        go.Bar(y=sens["Parameter"], x=sens["ΔNPV at +20% [€]"], orientation="h", name="Input +20 %"),
    ])
    fig.update_layout(title="What moves the NPV most?", barmode="relative", xaxis_title="Change in NPV [€]")
    st.plotly_chart(fig, width="stretch")

    with st.expander("Second life: EV battery reused for storage"):
        s1, s2, s3 = st.columns(3)
        first_life = s1.number_input("Cycles in the EV", min_value=1, value=1500)
        repurpose = s2.number_input("Repurposing cost (€/kWh)", min_value=0.0, value=20.0)
        second_years = s3.number_input("Second-life years", min_value=1, max_value=20, value=8)
        sl = second_life(tea_inputs, first_life, repurpose, second_years)
        r1, r2 = st.columns(2)
        start = sl["SOH at start [%]"]
        r1.metric("Capacity at start of second life",
                  f"{start:.1f} %" if math.isfinite(start) else f"Below {MIN_SOH:.0f} %")
        r2.metric("Second-life NPV", f"€{sl['NPV [€]']:,.0f}")
        if not math.isfinite(sl["SOH at start [%]"]):
            st.caption(f"After {first_life:,} cycles this battery is already below {MIN_SOH:.0f} % "
                       "capacity, so it has nothing left for a second life.")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
with environment_tab:
    with st.expander("Assumptions", expanded=False):
        b1, b2 = st.columns(2)
        vehicle = b1.radio("Use", ["Electric vehicle", "Stationary storage"]) == "Electric vehicle"
        if vehicle:
            lifetime_km = b1.number_input("Vehicle lifetime (km)", value=200000, step=10000)
            kwh_per_km = b1.number_input("Consumption (kWh/km)", value=0.16, step=0.01)
            lifetime_cycles = 3000
        else:
            lifetime_km, kwh_per_km = 200000, 0.16
            lifetime_cycles = b1.number_input("Lifetime (cycles)", value=3000, step=500)
        grid = b2.number_input("Grid carbon intensity (g CO2eq/kWh)", value=210.0, step=10.0)
        rte_lca = b2.slider("Round-trip efficiency ", 0.70, 0.98, 0.90, 0.01)

    lca_inputs = {"vehicle": vehicle, "lifetime_km": lifetime_km, "kwh_per_km": kwh_per_km,
                  "lifetime_cycles": lifetime_cycles, "round_trip_eff": rte_lca,
                  "grid_g_co2_per_kwh": grid}
    phases, ind = calculate_lca(chem, pack_kwh, **lca_inputs)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total footprint", f"{phases['Emissions [kg CO2eq]'].iloc[-1]:,.0f} kg CO2eq")
    c2.metric("Per kWh of capacity", f"{ind['Footprint per kWh capacity [kg CO2eq/kWh]']:.0f} kg CO2eq")
    c3.metric("Per MWh delivered", f"{ind['Levelised carbon [kg CO2eq/MWh delivered]']:.1f} kg CO2eq")
    st.plotly_chart(px.bar(phases.iloc[:-1], x="Phase", y="Emissions [kg CO2eq]",
                           title="Emissions by life-cycle phase"), width="stretch")
    st.caption(f"Pack mass ≈ {ind['Pack mass [kg]']:,.0f} kg. Screening study with indicative "
               "factors, not an ISO 14040 assessment.")

# ---------------------------------------------------------------------------
# Compare chemistries
# ---------------------------------------------------------------------------
with compare_tab:
    st.caption(f"All chemistries under the same simple cycle ({cc_run:g}C charge, {cd_run:g}C "
               f"discharge, full depth, {t_run} °C, {cpy_run:,.0f} cycles per year), each with its "
               "own empirical ageing model. "
               "Economics and environment use the assumptions in their tabs.")
    t_std, soc_std = standard_profile(cc_run, cd_run)
    # same real-time rest between cycles as the main result
    t_std, soc_std, temp_std, _ = add_rest(t_std, soc_std, [t_run] * len(t_std), cpy_run, t_run)
    rows = []
    for name in CHEMISTRIES:
        q = predict_capacity(name, t_std, soc_std, temp_std, PROJECTION_CYCLES, na_fade_run)
        q = np.where(q >= MIN_SOH / 100, q, np.nan)          # same cut-off as the main result
        soh_curve = pd.DataFrame({"Cycle": range(1, PROJECTION_CYCLES + 1), "SOH [%]": 100 * q})
        chem_tea = calculate_tea(**dict(tea_inputs, soh_curve=q,
                                        capex_eur_kwh=CHEMISTRIES[name]["capex_eur_kwh"]))
        _, chem_lca = calculate_lca(name, pack_kwh, **lca_inputs)
        below = soh_curve.loc[soh_curve["SOH [%]"] < 80, "Cycle"]
        rows.append({"Chemistry": name,
                     f"Capacity after {n_run:,} cycles": (f"{100 * q[n_run - 1]:.1f} %" if np.isfinite(q[n_run - 1])
                                                          else f"below {MIN_SOH:.0f} %"),
                     "Cycles until 80 %": f"{int(below.iloc[0]):,}" if len(below) else f"> {PROJECTION_CYCLES:,}",
                     "Pack cost [€]": chem_tea["CAPEX [€]"], "NPV [€]": chem_tea["NPV [€]"],
                     "LCOS [€/kWh]": chem_tea["LCOS [€/kWh]"],
                     "Retired in year": (f"year {chem_tea['Retired in year']}"
                                         if chem_tea["Retired in year"] else "still working"),
                     "Carbon [kg CO2eq/MWh]": chem_lca["Levelised carbon [kg CO2eq/MWh delivered]"]})
    compare = pd.DataFrame(rows)
    st.caption(f"Sodium-ion uses {100 * na_fade_run:.3f} % loss per cycle (sidebar setting when "
               "sodium-ion was last run; 0.1 % otherwise).")
    table(compare)
    st.plotly_chart(px.bar(compare, x="Chemistry", y="NPV [€]", title="Net present value"),
                    width="stretch")

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
with download_tab:
    d1, d2, d3 = st.columns(3)
    d1.download_button("Capacity per cycle (CSV)", cycles_df.to_csv(index=False),
                       f"cycles_{chem}.csv", "text/csv", width="stretch")
    d2.download_button("Voltage & temperature (CSV)", series_df.to_csv(index=False),
                       f"time_series_{chem}.csv", "text/csv", width="stretch")
    metadata = dict(meta, chemistry=chem, model=model_run, charge_rate_C=cc_run,
                    discharge_rate_C=cd_run, cycles=n_run, ambient_c=t_run, h_cooling=h_run,
                    final_soh_pct=soh_final, sodium_fade_per_cycle=na_fade_run,
                    retire_below_pct=retire_pct, cycles_to_80pct=life_80,
                    pack_kwh=pack_kwh, cells_needed=cells_needed)
    d3.download_button("Run settings (JSON)", json.dumps(metadata, indent=2, default=float),
                       f"settings_{chem}.json", "application/json", width="stretch")
    with st.expander("Preview: capacity per cycle"):
        table(cycles_df)
