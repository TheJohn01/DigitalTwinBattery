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
from battery_twin.chemistry import (CALIBRATION, CHEMISTRIES, COOLING_OPTIONS, DETAILED_CYCLES, MIN_SOH,
                                    PROJECTION_CYCLES, cooling_conditions, run_battery_test,
                                    standard_profile)
from battery_twin.economics import (GRID_FEE_SCENARIOS, LAZARD_WACC, NREL_LIFETIME_YEARS,
                                    POWER_CONVERSION_RTE, START_YEAR, tea_documentation,
                                    SECOND_LIFE_PACK_RANGE_USD, SECOND_LIFE_PACK_USD_KWH,
                                    STEFFEN_WACC_PORTUGAL, arbitrage_prices, best_retirement,
                                    calculate_tea,
                                    daily_arbitrage, load_prices, om_eur_kwh_year,
                                    second_life, second_life_capex_eur_kwh, sensitivity,
                                    system_capex_eur_kwh)
from battery_twin.lca_report import build_lca_report, lca_results
from battery_twin.tea_report import build_tea_report
from battery_twin.pack import COOLANTS, mean_heat_w, pack_ageing
from battery_twin.sources import SOURCES
from battery_twin.update import read_measurements, update_scale, updated_curve

# Started with "python app.py" or the editor's Run button: explain and stop.
if not st.runtime.exists():
    sys.exit("This is a Streamlit dashboard. Start it from the project folder with:\n"
             "    python -m streamlit run app.py")

st.set_page_config(page_title="Battery Digital Twin", page_icon="🔋", layout="wide")

VALIDATION_FIGURE = Path(__file__).parent / "docs" / "calibration_fit.png"
LFP_SHAPE_FIGURE = Path(__file__).parent / "docs" / "lfp_shape_severson.png"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@st.cache_data(show_spinner=False)
def simulate(chemistry, model_type, c_charge, c_discharge, n_cycles, ambient_c, cooling, na_fade,
             cycles_per_year):
    h_cooling, cycling_c = cooling_conditions(cooling, ambient_c)
    return run_battery_test(chemistry, model_type, c_charge, c_discharge, n_cycles, ambient_c,
                            h_cooling, na_fade, cycles_per_year, cycling_c, aged_windows=True)


@st.cache_data(show_spinner=False)
def arbitrage_days(c_charge, c_discharge, dod, rte):
    """Best daily cycle for every day of the OMIE price file (None if there is no file)."""
    prices = load_prices()
    if prices is None:
        return None, None
    return daily_arbitrage(prices, c_charge, c_discharge, dod, rte), prices.attrs["source"]


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
cooling = st.sidebar.selectbox(
    "Battery cooling", list(COOLING_OPTIONS),
    help="Sets the heat transfer coefficient h between the cells and their surroundings. "
         "The liquid options also pre-condition the cells (held at 25 °C while cycling).")
h_option, cycling_c_option = cooling_conditions(cooling, ambient_c)
st.sidebar.caption(f"Average h = **{h_option:.0f} W/m²K**; cells cycle at "
                   f"**{cycling_c_option:.0f} °C**.")
st.sidebar.warning(COOLING_OPTIONS[cooling]["warning"], icon="⚠️")
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

inputs = (chemistry, model_type, c_charge, c_discharge, n_cycles, ambient_c, cooling, na_fade,
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
chem, model_run, cc_run, cd_run, n_run, t_run, cool_run, na_fade_run, _ = st.session_state["inputs"]
h_run, cycling_c_run = cooling_conditions(cool_run, t_run)
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
# Settings and simulated values used by the LCA and TEA reports
run_info = {"c_charge": cc_run, "c_discharge": cd_run, "ambient_c": t_run,
            "cycling_c": cycling_c_run, "cooling": cool_run, "h": h_run,
            "mean_cell_temp": meta["mean_cell_temperature_c"],
            "cell_capacity_ah": meta["cell_capacity_ah"],
            "cell_energy_wh": meta["cell_energy_wh"], "cycles_per_year": cpy_run,
            "model": model_run, "n_cycles": n_run, "cycles_to_80": life_80}

(summary_tab, physics_tab, economics_tab, environment_tab, compare_tab, download_tab,
 sources_tab) = st.tabs(["Summary", "Physics", "Economics", "Environment", "Compare chemistries",
                         "Download", "Sources"])

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
        f"Charging at **{cc_run:g}C** and discharging at **{cd_run:g}C** at **{t_run} °C** "
        f"with **{cool_run.lower()}** cooling (cells cycling at {cycling_c_run:.0f} °C), "
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
                       "separate ageing model (NREL's LG M50 fit, rescaled to published cycling "
                       "data); see the README for how it compares with measurements.")
        else:
            st.write(
                f"The {chem} physics model uses its published parameter set without further "
                "tuning, so it has not been checked against measurements in this project. "
                f"The capacity curve comes from: {CHEMISTRIES[chem]['ageing_source']}.")
            st.caption("Only the NMC model has been compared with real measurements here. "
                       "The shaded range on the chart shows how sensitive the result is.")
        if chem == "LFP" and LFP_SHAPE_FIGURE.exists():
            st.write("**Shape of the LFP curve.** Severson et al. (2019) measured 123 A123 LFP "
                     "cells cycle by cycle. Their capacity stays nearly flat and then drops "
                     "sharply (a knee); the model fades almost in a straight line. The model's "
                     "cycle life is close (×1.3 typical error), but in mid-life it shows more "
                     "fade than the real cells, so energy delivered is underestimated.")
            st.image(str(LFP_SHAPE_FIGURE))

    with st.expander("Update with your own measurements"):
        st.write("Upload measured capacities of a cell used like this one. The prediction is "
                 "then adjusted: its capacity loss is multiplied by one factor, which moves "
                 "only as far as the measurements justify (method: README section 10.3).")
        upload = st.file_uploader("CSV: first column cycle number, second column capacity "
                                  "(% of new, or 0–1)", type="csv")
        if upload is not None:
            curve = projection["SOH [%]"].to_numpy() / 100.0
            n_meas, soh_meas = read_measurements(pd.read_csv(upload), len(curve))
            if len(n_meas) < 3:
                st.warning("Found fewer than 3 usable rows (cycle, capacity).")
            else:
                k = update_scale(n_meas, soh_meas, np.nan_to_num(curve, nan=MIN_SOH / 100))
                updated = updated_curve(curve, k)
                below = np.where(updated < 0.8)[0]
                life_updated = float(below[0] + 1) if len(below) else float("inf")
                u1, u2 = st.columns(2)
                u1.metric("Loss factor from your data", f"×{k:.2f}",
                          help="1 = the prediction as it was; below 1 = your cell fades slower")
                u2.metric("Cycles until 80 % (updated)", fmt_number(life_updated,
                          missing=f"over {PROJECTION_CYCLES:,}"),
                          delta=None if not (math.isfinite(life_updated) and math.isfinite(life_80))
                          else f"{life_updated - life_80:+,.0f} vs prediction")
                fig = go.Figure([
                    go.Scatter(x=projection["Cycle"], y=100 * curve, name="Prediction"),
                    go.Scatter(x=projection["Cycle"], y=100 * updated, name="Updated"),
                    go.Scatter(x=n_meas, y=100 * soh_meas, mode="markers", name="Your data")])
                fig.update_layout(xaxis_title="Cycle", yaxis_title="SOH [%]",
                                  legend=dict(orientation="h", y=-0.2))
                fig.add_hline(y=80, line_dash="dot")
                st.plotly_chart(fig, width="stretch")
                st.caption("The updated curve is shown here only; the economics and the LCA "
                           "still use the prediction.")
                if chem == "LFP":
                    st.warning("For LFP, treat the updated life as too long until the "
                               "measurements show the capacity dropping fast. On 82 Severson "
                               "test cells the update tracked the capacity better, but made the "
                               "life ×1.6–2.6 too long after 200–500 cycles, because these cells "
                               "fade little before a sudden drop.")

# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------
with physics_tab:
    windows = result.get("windows")
    if windows is not None and not windows["series"].empty:
        st.caption(f"Voltage and temperature of the first, middle and last {DETAILED_CYCLES} "
                   f"of the {n_run:,} cycles. The first {DETAILED_CYCLES} are the new cell. "
                   "The middle and last are an aged cell simulated with the physics model: "
                   "the new cell shrunk to the capacity the ageing model predicts there, so "
                   "it holds less charge and its resistance is higher. This is an "
                   "approximation; real ageing also changes the electrodes in other ways.")
        win = windows["series"]
        view = st.radio("Show", [f"All {DETAILED_CYCLES} cycles of each window",
                                 "One cycle of each window, on top of each other"],
                        horizontal=True)
        if view.startswith("All"):
            for y, title in [("Voltage [V]", "Cell voltage"),
                             ("Temperature [°C]", "Cell temperature")]:
                fig = px.line(win, x="Time [h]", y=y, color="Window", facet_row="Window",
                              hover_data=["Cycle"], title=title, height=650)
                fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width="stretch")
        else:
            # last cycle of each window, time measured from the start of that cycle
            last = win[win["Cycle"] == win.groupby("Window")["Cycle"].transform("max")].copy()
            last["Time in cycle [h]"] = last["Time [h]"] - last.groupby("Window")["Time [h]"].transform("min")
            last["Window"] = last["Window"] + " (cycle " + last["Cycle"].astype(str) + ")"
            for y, title in [("Voltage [V]", "Cell voltage"),
                             ("Temperature [°C]", "Cell temperature")]:
                st.plotly_chart(px.line(last, x="Time in cycle [h]", y=y, color="Window",
                                        title=title), width="stretch")
        table(windows["summary"])
        if n_run <= 2 * DETAILED_CYCLES:
            st.caption(f"With {n_run} cycles the windows would overlap, so fewer are shown.")
        with st.expander(f"Cycles 1–{DETAILED_CYCLES} one by one"):
            st.plotly_chart(px.line(series_df, x="Time [min]", y="Voltage [V]", color="Cycle",
                                    title="Cell voltage"), width="stretch")
            st.plotly_chart(px.line(series_df, x="Time [min]", y="Temperature [°C]",
                                    color="Cycle", title="Cell temperature"), width="stretch")
    else:
        st.caption(f"Voltage and temperature of the {DETAILED_CYCLES} fully simulated cycles.")
        st.plotly_chart(px.line(series_df, x="Time [min]", y="Voltage [V]", color="Cycle",
                                title="Cell voltage"), width="stretch")
        st.plotly_chart(px.line(series_df, x="Time [min]", y="Temperature [°C]", color="Cycle",
                                title="Cell temperature"), width="stretch")
    with st.expander("Efficiency per cycle"):
        table(eff_df)

    with st.expander("Pack: cells along one coolant channel"):
        st.write("The model simulates one cell in coolant at the inlet temperature. In a pack "
                 "the coolant warms as it passes each cell, so cells further along run hotter "
                 "and age differently. This shows that one effect for a row of cells sharing "
                 "a channel (coolant balance from ThermoWeave; see the README, section 4.7).")
        if is_sodium_run:
            st.info("The sodium-ion ageing model has no temperature effect, so every cell in "
                    "the row ages the same.")
        else:
            p1, p2, p3 = st.columns(3)
            n_row = p1.number_input("Cells along the channel", 2, 100, 12)
            coolant = p2.selectbox("Coolant", list(COOLANTS),
                                   index=0 if cool_run.startswith("Forced air") else 1)
            flow = p3.number_input("Flow per channel [L/min]", 0.1, 5000.0,
                                   60.0 if coolant == "Air" else 0.5)
            heat = mean_heat_w(eff_df.iloc[-1], meta["cycle_duration_h"])
            offsets, caps = pack_ageing(chem, result["profile"], n_row, heat, flow, coolant,
                                        cpy_run, t_run, PROJECTION_CYCLES)
            caps = np.where(caps >= MIN_SOH / 100, caps, np.nan)
            lives = [float(np.argmax(c < 0.8) + 1) if np.any(c < 0.8) else np.inf for c in caps]
            weakest = int(np.argmin(lives))
            q1, q2, q3 = st.columns(3)
            q1.metric("Heat per cell (mean)", f"{heat:.2f} W")
            q2.metric("Last cell warmer by", f"{offsets[-1]:.1f} K")
            q3.metric("Pack: cycles to 80 % (weakest cell)", fmt_number(lives[weakest],
                      missing=f"over {PROJECTION_CYCLES:,}"))
            row = pd.DataFrame({"Cell along the channel": np.arange(1, n_row + 1),
                                "Warmer than the simulated cell [K]": offsets,
                                "Cycles to 80 %": lives})
            st.plotly_chart(px.line(row, x="Cell along the channel", y="Cycles to 80 %",
                                    markers=True, title="Life of each cell in the row"),
                            width="stretch")
            st.caption(f"The weakest is cell {weakest + 1}. Cells in series can only deliver "
                       "what the weakest cell holds (no capacity balancing). For NMC, warmer "
                       "cells charge with less lithium plating, so cells further along can "
                       "last longer. Not included: heat conduction between cells and "
                       "differences between cells in capacity or resistance.")

# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------
with economics_tab:
    rte_cell = float(eff_df["Energy efficiency [%]"].mean() / 100)
    dod_run = float(np.clip(meta["depth_of_discharge"], 0.05, 1.0))
    with st.expander("Inputs and sources", expanded=False):
        a1, a2, a3 = st.columns(3)
        capex = a1.number_input(
            "System cost, CAPEX (€/kWh)", min_value=0.0, step=5.0,
            value=round(system_capex_eur_kwh(chem), 1), key=f"capex_{chem}",
            help="NREL 2025 cost of a complete 4-hour system ($321/kWh), plus the Benchmark "
                 "June 2025 cell-price difference between this chemistry and LFP (sodium-ion: "
                 "same as LFP, Keiner et al. 2026), at 1.13 $/€ (ECB, 2025 average).")
        rte = a2.slider("Round-trip efficiency (whole system)", 0.50, 0.98,
                        round(float(np.clip(rte_cell * POWER_CONVERSION_RTE, 0.5, 0.98)), 2), 0.01,
                        help=f"Simulated cell efficiency ({100 * rte_cell:.1f} %) × 83/91 "
                             f"= {POWER_CONVERSION_RTE:.3f}: PNNL measured 91 % without and 83 % "
                             "with auxiliary loads and rests on a 1 MW battery at 1C "
                             "(PNNL-27237). IEC 62933-2-1 measures efficiency at the grid "
                             "connection, auxiliaries included.")
        years = a2.number_input("Project lifetime (years)", min_value=1, max_value=30,
                                value=NREL_LIFETIME_YEARS, help="NREL: 15 years.")
        dep_rate = a2.slider(
            "Tax depreciation rate (% per year)", 10, 20, 20, 1,
            help="Straight-line. Batteries are not listed in the tax tables; the closest "
                 "category, electronic equipment, has a maximum of 20 % a year (PwC, Portugal). "
                 "The minimum allowed is half the maximum (Decreto Regulamentar 25/2009).") / 100
        wacc = a3.number_input("Discount rate (WACC)", min_value=0.0, max_value=0.3,
                               value=STEFFEN_WACC_PORTUGAL, step=0.005, format="%.3f",
                               help="Steffen 2020: 7.4 % after-tax for Portugal (onshore wind, "
                                    "2017 interest rates). Lazard's storage financing gives "
                                    f"{100 * LAZARD_WACC:.1f} %.")
        retire_pct = a3.slider("Retire the battery below capacity (%)", int(MIN_SOH), 90,
                               70, 5,
                               help="Below this capacity the battery stops operating: no more "
                                    "revenue and no more operating costs. Default 70 %, the end "
                                    "of service life of the LCA, so that both use the same "
                                    "functional unit (ISO/TS 14076).")
        fee_case = a3.selectbox(
            "Grid fees from 2030", list(GRID_FEE_SCENARIOS),
            help="ERSE Regulamento Tarifário, art. 56: storage is exempt from network access "
                 "tariffs on energy it feeds back, until the end of 2029. Afterwards the "
                 "rule is not yet known; the options use the 2026 access tariffs (ERSE "
                 "Diretiva 10/2025): energy in 'horas cheias' plus contracted power.")
        daily, price_source = arbitrage_days(cc_run, cd_run, dod_run, rte)
        if daily is None:
            st.warning("No hourly price file found, so fixed prices are used. Run "
                       "`python scripts/download_omie_prices.py 2025` to download OMIE prices.")
            price = a1.number_input("Electricity price (€/kWh)", min_value=0.0, value=0.20, step=0.01)
            spread = a1.number_input("Arbitrage spread (€/kWh)", min_value=0.0, value=0.10, step=0.01,
                                     help="Selling price minus buying price.")
            arb = None
        else:
            arb = arbitrage_prices(daily, cpy_run)
            price, spread = arb["electricity_price"], arb["spread"]
        st.caption(f"Operation and maintenance (Lazard LCOS 7.0): €{om_eur_kwh_year():.2f}/kWh per "
                   "year, rising 2.5 % a year, plus a warranty of 0.9 % of CAPEX a year from "
                   f"year 3. Depth of discharge: {100 * dod_run:.0f} % (simulated cycle). "
                   f"Operation starts in {START_YEAR}; prices and grid fees rise 2 % a year "
                   "(ECB inflation target). Corporate income tax (IRC) 19 % in 2026, 18 % in "
                   "2027, 17 % from 2028; losses carried forward, deductible up to 65 % of a "
                   "year's taxable income. "
                   "System regulation charges: exempt (ERSE Orientação 1/2026, below 10 MVA).")

    # The economics use the ageing curve itself, cycle by cycle
    soh_curve = projection["SOH [%]"].to_numpy() / 100.0
    tea_inputs = {"soh_curve": soh_curve, "capex_eur_kwh": capex, "capacity_kwh": pack_kwh,
                  "electricity_price": price, "spread": spread, "round_trip_eff": rte,
                  "cycles_per_year": int(round(cpy_run)), "dod": dod_run, "years": int(years),
                  "wacc": wacc, "retire_below": retire_pct / 100.0,
                  "grid_fee_eur_kwh": GRID_FEE_SCENARIOS[fee_case][0],
                  "grid_fee_eur_kw_day": GRID_FEE_SCENARIOS[fee_case][1],
                  "charge_power_kw": pack_kwh * cc_run, "depreciation_rate": dep_rate}
    tea = calculate_tea(**tea_inputs)

    if arb is not None:
        st.caption(f"Electricity prices: OMIE day-ahead, Portugal, {daily['date'].min()} to "
                   f"{daily['date'].max()} ({price_source}). The battery "
                   f"cycles on the {arb['days_used']} best days ({arb['profitable_days']} of "
                   f"{len(daily)} days are profitable), charging in the cheapest hours and "
                   f"discharging in the dearest: mean buying price €{price * 1000:.0f}/MWh, "
                   f"selling price €{(price + spread) * 1000:.0f}/MWh.")
        if cpy_run > 365:
            st.warning("The price model allows one cycle per day; cycles above 365 per year "
                       "are given the same mean prices, which is optimistic.")
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

    with st.expander("When to retire the battery"):
        retire_table, best = best_retirement(tea_inputs)
        best_pct = best["Retire below [%]"]
        gain = best["NPV [€]"] - tea["NPV [€]"]
        st.write(f"Highest NPV when the battery is retired below **{best_pct:.0f} %** capacity "
                 f"(NPV €{best['NPV [€]']:,.0f}, {'+' if gain >= 0 else '−'}€{abs(gain):,.0f} "
                 f"compared with retiring below {retire_pct} %).")
        st.caption("A retired battery earns nothing and has no resale value here, so it pays to "
                   "keep it while one more year of arbitrage covers that year's operating costs "
                   "(O&M, warranty, grid fees). Idea: Thelen et al. (2023), who chose the "
                   "retirement of each cell from its predicted capacity curve. The LCA keeps its "
                   "own end of life (70 %).")
        if best_pct <= MIN_SOH:
            st.caption(f"The best value is the lowest one tried: the ageing data end at "
                       f"{MIN_SOH:.0f} %, so the curve cannot say whether going lower pays.")
        table(retire_table)

    with st.expander("Cash flows by year (life-cycle cost breakdown)"):
        st.dataframe(tea["Table"].round(0), width="stretch", hide_index=True)
        st.caption("Cost breakdown as in IEC 60300-3-3 (life cycle costing): acquisition "
                   "(CAPEX, year 0), operation (charging energy, grid fees), maintenance "
                   "(O&M, warranty) and income tax. Nominal euro; disposal cost not included "
                   "(no source).")
        dl1, dl2 = st.columns(2)
        dl1.download_button("Cash flows (CSV)", tea["Table"].to_csv(index=False),
                            f"tea_cash_flows_{chem}.csv", "text/csv", width="stretch")
        dl2.download_button("All TEA inputs and their sources (JSON)",
                            json.dumps(tea_documentation(tea_inputs, chem, price_source), indent=2,
                                       default=float),
                            f"tea_parameters_{chem}.json", "application/json", width="stretch")

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
        sl_pack = s2.number_input(
            "Repurposed battery price ($/kWh)", min_value=0.0, value=SECOND_LIFE_PACK_USD_KWH,
            help=f"Dong et al. 2023 (review): ${SECOND_LIFE_PACK_RANGE_USD[0]:.0f}–"
                 f"{SECOND_LIFE_PACK_RANGE_USD[1]:.0f}/kWh including collection, testing and "
                 f"repackaging; ${SECOND_LIFE_PACK_USD_KWH:.0f}/kWh is Liu's estimate.")
        second_years = s3.number_input("Second-life years", min_value=1, max_value=20, value=8)
        sl_capex = second_life_capex_eur_kwh(sl_pack)
        sl = second_life(dict(tea_inputs, start_year=START_YEAR + int(first_life // cpy_run),
                              retire_below=MIN_SOH / 100),
                         first_life, sl_capex, second_years)
        st.caption(f"Second-life system cost: €{sl_capex:.0f}/kWh (repurposed battery plus a new "
                   "inverter, enclosure and installation: NREL system cost minus the BloombergNEF "
                   f"stationary pack price). A new {chem} system costs €{capex:.0f}/kWh. "
                   f"A second-life battery runs until it reaches {MIN_SOH:.0f} % capacity.")
        r1, r2 = st.columns(2)
        start = sl["SOH at start [%]"]
        r1.metric("Capacity at start of second life",
                  f"{start:.1f} %" if math.isfinite(start) else f"Below {MIN_SOH:.0f} %")
        r2.metric("Second-life NPV", f"€{sl['NPV [€]']:,.0f}")
        if not math.isfinite(sl["SOH at start [%]"]):
            st.caption(f"After {first_life:,} cycles this battery is already below {MIN_SOH:.0f} % "
                       "capacity, so it has nothing left for a second life.")

    st.info("**A techno-economic assessment following the framework of ISO/TS 14076:2025, not "
            "critically reviewed.** The report documents goal and scope, technical analysis, "
            "economic analysis (cash flows by year), the LCA results, sensitivity analysis and "
            "a combined interpretation for this run, with an abstract that explains the result.")
    report_prices = None if arb is None else {
        "source": price_source, "first": daily["date"].min(), "last": daily["date"].max(),
        "days": len(daily), "days_used": arb["days_used"],
        "profitable_days": arb["profitable_days"]}
    lca_for_tea = lca_results(chem, pack_kwh, soh_curve, "stationary",
                              eol_soh=max(retire_pct / 100, 0.70), service_years=int(years),
                              cycles_per_year=cpy_run, round_trip_eff=rte)["ind"]
    tea_report_args = (chem, run_info, tea_inputs, report_prices, fee_case, lca_for_tea)
    t1, t2 = st.columns(2)
    t1.download_button("📄 Download TEA report (PDF)", build_tea_report(*tea_report_args),
                       f"TEA_{chem}.pdf", "application/pdf", width="stretch")
    t2.download_button("📝 Download TEA report (Word)",
                       build_tea_report(*tea_report_args, fmt="docx"),
                       f"TEA_{chem}.docx", DOCX_MIME, width="stretch")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
with environment_tab:
    q_run = projection["SOH [%]"].to_numpy() / 100.0
    rte_sim = float(np.clip(eff_df["Energy efficiency [%]"].mean() / 100, 0.70, 0.98))
    with st.expander("Assumptions", expanded=False):
        b1, b2 = st.columns(2)
        stationary = b1.radio("Use", ["Stationary storage (this simulation)",
                                      "Electric vehicle"]).startswith("Stationary")
        if stationary:
            eol_pct = b1.slider("End of service life at capacity (%)", 70, 90, 70,
                                help="The EU carbon-footprint rules (JRC CFB-IND) require 70 % "
                                     "or more.")
            service_years = b1.number_input("Service life cap (years)", min_value=1,
                                            max_value=30, value=int(years))
            lifetime_km, kwh_per_km = 200000, 0.16
        else:
            eol_pct, service_years = 70, int(years)
            lifetime_km = b1.number_input("Vehicle lifetime (km)", value=200000, step=10000)
            kwh_per_km = b1.number_input("Consumption (kWh/km)", value=0.16, step=0.01)
        grid = b2.number_input("Grid carbon intensity (g CO2eq/kWh)", value=210.0, step=10.0,
                               help="Assumption: set it to the grid that charges the battery.")
        rte_lca = b2.slider("Round-trip efficiency ", 0.70, 0.98, round(rte_sim, 2), 0.01,
                            help="Default: the energy efficiency of the simulated cycles.")

    use_case = "stationary" if stationary else "ev"
    lca_args = {"eol_soh": eol_pct / 100, "service_years": service_years,
                "cycles_per_year": cpy_run, "round_trip_eff": rte_lca,
                "grid_g_co2_per_kwh": grid, "lifetime_km": lifetime_km,
                "kwh_per_km": kwh_per_km}
    lca = lca_results(chem, pack_kwh, q_run, use_case, **lca_args)
    phases, ind = lca["phases"], lca["ind"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Carbon footprint (EU scope)",
              f"{ind['Carbon footprint, regulation scope [g CO2eq/kWh delivered]']:.0f} g CO2eq/kWh",
              help="Production + end of life, per kWh delivered over the service life "
                   "(Regulation (EU) 2023/1542 excludes the use phase).")
    c2.metric("Incl. battery losses",
              f"{ind['Carbon footprint incl. use-phase losses [g CO2eq/kWh delivered]']:.0f} g CO2eq/kWh")
    c3.metric("Water consumption", f"{ind['Water consumption [L/kWh delivered]']:.2f} L/kWh",
              help="ReCiPe 2016 water consumption potential, production only (Degen et al. 2024).")
    c4.metric("Freshwater ecotoxicity (g 1,4-DCB eq/kWh)",
              f"{ind['Freshwater ecotoxicity [g 1,4-DCB eq/kWh delivered]']:.1f}",
              help="ReCiPe 2016 freshwater ecotoxicity potential, production only (Degen et al. 2024).")
    st.plotly_chart(px.bar(phases.iloc[:-1], x="Phase", y="Emissions [kg CO2eq]",
                           title="Climate change by life-cycle stage"), width="stretch")
    st.dataframe(phases.round(1).astype(object).where(phases.notna(), "not assessed").astype(str),
                 width="stretch", hide_index=True)
    life_text_lca = (f"{lca['cycles']:,} cycles until {eol_pct} % capacity or the "
                     f"{service_years}-year cap" if stationary else
                     f"{lifetime_km:,.0f} km")
    st.caption(f"Functional unit: 1 kWh delivered over the service life "
               f"({lca['energy_kwh'] / 1000:,.1f} MWh in total; {life_text_lca}). "
               f"Pack mass ≈ {ind['Pack mass [kg]']:,.0f} kg. Production data: Degen et al. "
               "2024 (ecoinvent 3.10, ReCiPe 2016), cell level; pack parts not included. The "
               "grid intensity and recycling credit are assumptions.")
    st.info("**A screening LCA following ISO 14040/14044, not critically reviewed.** The report "
            "below documents goal and scope, inventory, impact assessment, interpretation "
            "(with a sensitivity check) and reporting for this run.")
    r1, r2 = st.columns(2)
    r1.download_button("📄 Download screening LCA report (PDF)",
                       build_lca_report(chem, pack_kwh, q_run, use_case, run_info, lca_args),
                       f"screening_LCA_{chem}.pdf", "application/pdf", width="stretch")
    r2.download_button("📝 Download screening LCA report (Word)",
                       build_lca_report(chem, pack_kwh, q_run, use_case, run_info, lca_args,
                                        fmt="docx"),
                       f"screening_LCA_{chem}.docx", DOCX_MIME, width="stretch")

# ---------------------------------------------------------------------------
# Compare chemistries
# ---------------------------------------------------------------------------
with compare_tab:
    st.caption(f"All chemistries under the same simple cycle ({cc_run:g}C charge, {cd_run:g}C "
               f"discharge, full depth, cells at {cycling_c_run:.0f} °C while cycling and "
               f"{t_run} °C at rest, {cpy_run:,.0f} cycles per year), each with its "
               "own empirical ageing model. "
               "Economics and environment use the assumptions in their tabs.")
    t_std, soc_std = standard_profile(cc_run, cd_run)
    # same real-time rest between cycles as the main result
    t_std, soc_std, temp_std, _ = add_rest(t_std, soc_std, [cycling_c_run] * len(t_std), cpy_run,
                                           t_run)
    rows = []
    for name in CHEMISTRIES:
        q = predict_capacity(name, t_std, soc_std, temp_std, PROJECTION_CYCLES, na_fade_run)
        q = np.where(q >= MIN_SOH / 100, q, np.nan)          # same cut-off as the main result
        soh_curve = pd.DataFrame({"Cycle": range(1, PROJECTION_CYCLES + 1), "SOH [%]": 100 * q})
        chem_tea = calculate_tea(**dict(tea_inputs, soh_curve=q,
                                        capex_eur_kwh=system_capex_eur_kwh(name)))
        chem_lca = lca_results(name, pack_kwh, q, use_case, **lca_args)["ind"]
        below = soh_curve.loc[soh_curve["SOH [%]"] < 80, "Cycle"]
        rows.append({"Chemistry": name,
                     f"Capacity after {n_run:,} cycles": (f"{100 * q[n_run - 1]:.1f} %" if np.isfinite(q[n_run - 1])
                                                          else f"below {MIN_SOH:.0f} %"),
                     "Cycles until 80 %": f"{int(below.iloc[0]):,}" if len(below) else f"> {PROJECTION_CYCLES:,}",
                     "System cost [€]": round(chem_tea["CAPEX [€]"]),
                     "NPV [€]": round(chem_tea["NPV [€]"]),
                     "LCOS [€/kWh]": round(chem_tea["LCOS [€/kWh]"], 3),
                     "Retired in year": (f"year {chem_tea['Retired in year']}"
                                         if chem_tea["Retired in year"] else "still working"),
                     "Carbon [g CO2eq/kWh delivered]":
                         round(chem_lca["Carbon footprint, regulation scope [g CO2eq/kWh delivered]"], 1)})
    compare = pd.DataFrame(rows)
    st.caption(f"Sodium-ion uses {100 * na_fade_run:.3f} % loss per cycle (sidebar setting when "
               "sodium-ion was last run; 0.1 % otherwise).")
    table(compare)
    st.caption("Combined interpretation (ISO/TS 14076, eTEA): cost (LCOS) and carbon footprint "
               "share the same functional unit, 1 kWh delivered, and the same ageing curve; "
               "the TEA retires the battery at the LCA's end of service life (70 % by default).")
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
                    discharge_rate_C=cd_run, cycles=n_run, ambient_c=t_run, cooling=cool_run, h_cooling=h_run,
                    cycling_temperature_c=cycling_c_run,
                    final_soh_pct=soh_final, sodium_fade_per_cycle=na_fade_run,
                    retire_below_pct=retire_pct, cycles_to_80pct=life_80,
                    pack_kwh=pack_kwh, cells_needed=cells_needed)
    d3.download_button("Run settings (JSON)", json.dumps(metadata, indent=2, default=float),
                       f"settings_{chem}.json", "application/json", width="stretch")
    with st.expander("Preview: capacity per cycle"):
        table(cycles_df)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
with sources_tab:
    st.write("Every published source the program uses, and what it is used for. Values read "
             "from papers are in `src/battery_twin/data/`; the fits are in "
             "`scripts/fit_ageing.py`.")
    for area in dict.fromkeys(src["Area"] for src in SOURCES):
        st.markdown(f"#### {area}")
        for src in (x for x in SOURCES if x["Area"] == area):
            link = f" [{src['Link']}]({src['Link']})" if src["Link"] else ""
            st.markdown(f"- {src['Reference']}{link}  \n  *Used for:* {src['Used for']}")
