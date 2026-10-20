"""Battery Digital Twin dashboard. Start it with:  python -m streamlit run app.py"""
import json
import math
import sys
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from battery_twin.ageing import (MIN_SOH, SodiumIon, add_rest, cut_at_data_end, cycles_to,
                                 ev_first_life, predict_capacity, second_life_curve)
from battery_twin.chemistry import (CALIBRATION, CHEMISTRIES, COOLING_OPTIONS, DEFAULT_AMBIENT_C,
                                    DEFAULT_C_CHARGE, DEFAULT_C_DISCHARGE, DETAILED_CYCLES,
                                    DFN_ABOVE_C_CHARGE, PROJECTION_CYCLES, choose_model,
                                    cooling_conditions, is_sodium, run_battery_test,
                                    standard_profile)
from battery_twin.constants import CFB_MIN_EOL_SOH
from battery_twin.economics import (FIXED_ELECTRICITY_PRICE, FIXED_SPREAD, GRID_FEE_SCENARIOS,
                                    INFLATION, LAZARD_WACC, NREL_LIFETIME_YEARS,
                                    NREL_SYSTEM_USD_KWH, PNNL_RTE_NO_AUX, PNNL_RTE_WITH_AUX,
                                    POWER_CONVERSION_RTE, SECOND_LIFE_PACK_RANGE_USD,
                                    B2U_BUY_USD_KWH_LEFT, B2U_REPURPOSING_USD_KWH, START_YEAR,
                                    STEFFEN_WACC_PORTUGAL, calculate_tea, repurposed_pack_usd_kwh,
                                    USD_PER_EUR, arbitrage_prices, daily_arbitrage,
                                    irc_text, load_prices,
                                    om_text, second_life, second_life_capex_eur_kwh,
                                    sensitivity, system_capex_eur_kwh, tea_at_best_retirement,
                                    tea_documentation)
from battery_twin.environment import (CFB_KEY, CFB_USE_KEY, ECOTOX_KEY, GRID_G_CO2_PER_KWH,
                                      KWH_PER_KM, LIFETIME_KM, WATER_KEY, production_factors)
from battery_twin.lca_report import STATEMENT as LCA_STATEMENT, build_lca_report, lca_results
from battery_twin.pack import COOLANTS, mean_heat_w, pack_ageing
from battery_twin.report_doc import fmt_number
from battery_twin.tea_report import STATEMENT as TEA_STATEMENT, build_tea_report
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


@st.cache_data(show_spinner=False)
def tea_analysis(tea_inputs):
    """TEA with the battery retired at the threshold of highest NPV (the run's one end of
    life), its sensitivity and the NPV of every threshold. Cached, because every click on
    any widget reruns the whole script."""
    inputs, tea, retire_table, best = tea_at_best_retirement(tea_inputs)
    return inputs, tea, sensitivity(inputs, base_npv=tea["NPV [€]"]), retire_table, best


@st.cache_data(show_spinner=False)
def compare_chemistries(c_charge, c_discharge, cycling_c, ambient_c, cycles_per_year, na_fade,
                        n_cycles, tea_inputs, pack_kwh, use_case, lca_args):
    """Every chemistry under the same simple cycle, each with its own ageing model and its
    own end of life (the retirement threshold of highest NPV, used by its TEA and its LCA)."""
    t, soc = standard_profile(c_charge, c_discharge)
    # same real-time rest between cycles as the main result
    t, soc, temp, _ = add_rest(t, soc, [cycling_c] * len(t), cycles_per_year, ambient_c)
    rows = []
    for name in CHEMISTRIES:
        q = cut_at_data_end(predict_capacity(name, t, soc, temp, PROJECTION_CYCLES, na_fade))
        _, chem_tea, _, best = tea_at_best_retirement(
            dict(tea_inputs, soh_curve=q, capex_eur_kwh=system_capex_eur_kwh(name)))
        eol = float(best["Retire below [%]"])
        chem_lca = lca_results(name, pack_kwh, q, use_case,
                               **dict(lca_args, eol_soh=eol / 100))["ind"]
        rows.append({"Chemistry": name,
                     f"Capacity after {n_cycles:,} cycles": (
                         f"{100 * q[n_cycles - 1]:.1f} %" if np.isfinite(q[n_cycles - 1])
                         else f"below {MIN_SOH:.0f} %"),
                     "Cycles until 80 %": fmt_number(cycles_to(q, 0.8),
                                                     missing=f"> {PROJECTION_CYCLES:,}"),
                     "System cost [€]": round(chem_tea["CAPEX [€]"]),
                     "NPV [€]": round(chem_tea["NPV [€]"]),
                     "LCOS [€/kWh]": round(chem_tea["LCOS [€/kWh]"], 3),
                     "End of life (highest NPV)": f"{eol:.0f} %",
                     "Retired in year": (f"year {chem_tea['Retired in year']}"
                                         if chem_tea["Retired in year"] else "still working"),
                     "Carbon [g CO2eq/kWh delivered]": round(chem_lca[CFB_KEY], 1)})
    return pd.DataFrame(rows)


def table(df):
    st.dataframe(df.round(3), width="stretch", hide_index=True)


def cycle_charts(series):
    """Voltage and temperature of the fully simulated cycles, one line per cycle."""
    for y, title in [("Voltage [V]", "Cell voltage"), ("Temperature [°C]", "Cell temperature")]:
        st.plotly_chart(px.line(series, x="Time [min]", y=y, color="Cycle", title=title),
                        width="stretch")


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
c_charge = st.sidebar.select_slider("Charge rate (C)", [0.3, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0],
                                    value=DEFAULT_C_CHARGE,
                                    help="1C = full charge in about one hour.")
c_discharge = st.sidebar.select_slider("Discharge rate (C)", [0.3, 0.5, 1.0, 1.5, 2.0, 3.0],
                                       value=DEFAULT_C_DISCHARGE)
ambient_c = st.sidebar.slider("Ambient temperature (°C)", 5, 45, int(DEFAULT_AMBIENT_C), 5,
                              help=f"The default settings ({DEFAULT_AMBIENT_C:g} °C, "
                                   f"{DEFAULT_C_CHARGE:g}C charge, {DEFAULT_C_DISCHARGE:g}C "
                                   "discharge) stay inside the measured ageing data for NMC, LFP "
                                   "and NCA.")
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
                           help=f"Charging above {DFN_ABOVE_C_CHARGE:g}C always uses the "
                                "detailed model.")

sodium = is_sodium(chemistry)
na_fade = SodiumIon.FADE_PER_EFC
if sodium:
    na_fade_pct = st.sidebar.number_input(
        "Sodium-ion capacity loss (% per cycle)", min_value=0.0, max_value=1.0,
        value=100 * SodiumIon.FADE_PER_EFC, step=0.01, format="%.3f",
        help="0.05 % is measured on commercial layered-oxide 18650 cells cycled fully "
             "(Liu et al. 2026: 80 % after about 400 cycles). The best commercial sodium-ion "
             "cells lose under 0.01 % per cycle (Liu 2026; Carter et al. 2025). Quality still "
             "varies a lot between manufacturers and batches.")
    na_fade = na_fade_pct / 100
model_type = choose_model(chemistry, c_charge, detailed)
if c_charge > DFN_ABOVE_C_CHARGE and not detailed and not sodium:
    st.sidebar.caption(f"Charging above {DFN_ABOVE_C_CHARGE:g}C: the detailed model is used "
                       "automatically.")

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
cycles_df, series_df, eff_df, meta = result["cycles"], result["series"], result["efficiency"], result["meta"]
h_run, cycling_c_run = meta["h_cooling"], meta["cycling_c"]
if st.session_state["inputs"] != inputs:
    st.warning("The settings have changed. Press **▶ Run** to update the results.")

# Values shared by all tabs
label = CHEMISTRIES[chem]["label"]
cpy_run = meta["cycles_per_year"]          # cycles per year actually used by the ageing
sodium_run = is_sodium(chem)
soh_final = float(cycles_df["SOH [%]"].iloc[-1])
projection = result["projection"]
soh_curve = projection["SOH [%]"].to_numpy() / 100.0    # the ageing curve, used by every tab
rte_cell = float(eff_df["Energy efficiency [%]"].mean() / 100)   # simulated cell efficiency
data_end = meta["cycles_to_data_end"]
soh_text = f"{soh_final:.1f} %" if math.isfinite(soh_final) else f"below {MIN_SOH:.0f} %"
life_80 = meta["cycles_to_80pct"]
life_text = fmt_number(life_80, missing=f"> {PROJECTION_CYCLES:,}")
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
    if sodium_run:
        st.info(f"**Sodium-ion ageing uses {100 * na_fade_run:.3f} % capacity loss per cycle.** "
                "The default 0.05 % comes from two commercial layered-oxide 18650 cells cycled "
                "fully until 80 % (about 400 cycles, Liu et al. 2026); the best commercial "
                "sodium-ion cells lose under 0.01 %. Below 80 % the straight line is an "
                "extrapolation, so change the rate in the sidebar to see how sensitive the "
                "results are.")

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
        elif chem == "Na-ion":
            st.write(
                "The sodium-ion physics model is a commercial cell (Mushang NA18650-1250, "
                "1.25 Ah, layered oxide / hard carbon), parameterised by Schneider et al. "
                "(2025) from a teardown and three-electrode tests, with temperature-dependent "
                "kinetics and a thermal model. Checked here against their measured discharges "
                "from C/100 to 5C: voltage error 18–49 mV (RMS), capacity within 2 %, "
                "temperature rise at 1C 2.9 K (measured 3.2 K). Round-trip efficiency is about "
                "2 percentage points higher than Rehm et al. (2025) measured on the same cell "
                "(1C, 25 °C: 93.9 % vs 89–92 %), because the model has no voltage hysteresis.")
            st.caption("The charge side is less certain: the paper validated discharges only, "
                       "and the temperature dependence was measured at 10–40 °C (colder is "
                       "extrapolated; charging below 10 °C can come out unrealistically slow). "
                       "The capacity curve comes from: "
                       f"{CHEMISTRIES[chem]['ageing_source']}.")
        elif chem == "NCA":
            st.write(
                "The NCA physics model is a commercial cell (Samsung INR21700-50E, 4.9 Ah, NCA / "
                "graphite-SiOx), parameterised by Schmitt et al. (2023) from a teardown. Checked "
                "here against their measured discharges at 0.04C, 0.5C and 1C (25 °C): capacity "
                "within 1 %, voltage error 16–24 mV (RMS). The thermal properties and the "
                "electrolyte come from other sources (Chen 2020; Landesfeind & Gasteiger 2019), "
                "and the temperature rise has not been compared with measurements.")
            st.caption("The capacity curve comes from: "
                       f"{CHEMISTRIES[chem]['ageing_source']} (a different commercial NCA cell).")
        elif chem == "LFP":
            st.write(
                "The LFP physics model is a commercial BEV cell, the BYD Blade (135 Ah, LFP / "
                "graphite): geometry, electrode sizes, masses and capacity from the teardown of "
                "Gorsch et al. (2025), electrochemistry from Prada 2013 with five values fitted "
                "to measured LFP cells, including the Blade's own 1C pulse resistance (about "
                "1 mΩ at 20 °C). Checks against data not used in the fit: pulse resistance of "
                "BYD's 4680 LFP cell 10–14 Ω·cm² (measured 6–17; Liu et al. 2025), resistance "
                "and capacity at 15 and 35 °C within 4 % and 1 % of a 280 Ah LFP cell's trend "
                "(Gray & Vagg 2026), C/10 discharge voltage within 10 mV (RMS) of that cell, "
                "and the Blade's C/10 energy (432 Wh).")
            st.caption("No rate test of the Blade itself is published, so its rate behaviour "
                       "comes from BYD's 4680 LFP cell (same cathode coating). The "
                       "capacity curve comes from: "
                       f"{CHEMISTRIES[chem]['ageing_source']}; against 700 measured cycles of the "
                       "280 Ah cell at 1C it is about 3 percentage points pessimistic.")
        else:
            st.write(
                f"The {chem} physics model uses its published parameter set without further "
                "tuning, so it has not been checked against measurements in this project. "
                f"The capacity curve comes from: {CHEMISTRIES[chem]['ageing_source']}.")
            st.caption("The other models have been compared with real measurements here. The "
                       "shaded range on the chart shows how sensitive the result is.")
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
            curve = soh_curve
            n_meas, soh_meas = read_measurements(pd.read_csv(upload), len(curve))
            if len(n_meas) < 3:
                st.warning("Found fewer than 3 usable rows (cycle, capacity).")
            else:
                k = update_scale(n_meas, soh_meas, np.nan_to_num(curve, nan=MIN_SOH / 100))
                updated = updated_curve(curve, k)
                life_updated = cycles_to(updated, 0.8)
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
            cycle_charts(series_df)
    else:
        st.caption(f"Voltage and temperature of the {DETAILED_CYCLES} fully simulated cycles.")
        cycle_charts(series_df)
    with st.expander("Efficiency per cycle"):
        table(eff_df)

    with st.expander("Pack: cells along one coolant channel"):
        st.write("The model simulates one cell in coolant at the inlet temperature. In a pack "
                 "the coolant warms as it passes each cell, so cells further along run hotter "
                 "and age differently. This shows that one effect for a row of cells sharing "
                 "a channel (coolant balance from ThermoWeave; see the README, section 4.7).")
        if sodium_run:
            st.info("The sodium-ion ageing model has no temperature effect, so every cell in "
                    "the row ages the same.")
        else:
            p1, p2, p3 = st.columns(3)
            n_row = p1.number_input("Cells along the channel", 2, 100, 12)
            coolant = p2.selectbox("Coolant", list(COOLANTS),
                                   index=0 if cool_run.startswith("Forced air") else 1)
            # default flow for a 5 Ah cell, scaled up for larger cells (the 135 Ah LFP Blade)
            flow_scale = max(1.0, meta["cell_capacity_ah"] / 5.0)
            flow = p3.number_input("Flow per channel [L/min]", 0.1, 5000.0,
                                   round((60.0 if coolant == "Air" else 0.5) * flow_scale, 1))
            heat = mean_heat_w(eff_df.iloc[-1], meta["cycle_duration_h"])
            offsets, caps = pack_ageing(chem, result["profile"], n_row, heat, flow, coolant,
                                        cpy_run, t_run, PROJECTION_CYCLES)
            lives = [cycles_to(c, 0.8) for c in cut_at_data_end(caps)]
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
    dod_run = float(np.clip(meta["depth_of_discharge"], 0.05, 1.0))
    with st.expander("Inputs and sources", expanded=False):
        a1, a2, a3 = st.columns(3)
        capex = a1.number_input(
            "System cost, CAPEX (€/kWh)", min_value=0.0, step=5.0,
            value=round(system_capex_eur_kwh(chem), 1), key=f"capex_{chem}",
            help=f"NREL 2025 cost of a complete 4-hour system (${NREL_SYSTEM_USD_KWH:g}/kWh), "
                 "plus the Benchmark June 2025 cell-price difference between this chemistry and "
                 "LFP (sodium-ion: same as LFP, Keiner et al. 2026), at "
                 f"{USD_PER_EUR:g} $/€ (ECB, 2025 average).")
        rte = a2.slider("Round-trip efficiency (whole system)", 0.50, 0.98,
                        round(float(np.clip(rte_cell * POWER_CONVERSION_RTE, 0.5, 0.98)), 2), 0.01,
                        help=f"Simulated cell efficiency ({100 * rte_cell:.1f} %) × "
                             f"{100 * PNNL_RTE_WITH_AUX:g}/{100 * PNNL_RTE_NO_AUX:g} = "
                             f"{POWER_CONVERSION_RTE:.3f}: PNNL measured "
                             f"{100 * PNNL_RTE_NO_AUX:g} % without and "
                             f"{100 * PNNL_RTE_WITH_AUX:g} % with auxiliary loads and rests on a "
                             "1 MW battery at 1C "
                             "(PNNL-27237). IEC 62933-2-1 measures efficiency at the grid "
                             "connection, auxiliaries included.")
        years = a2.number_input("Project lifetime (years)", min_value=1, max_value=30,
                                value=NREL_LIFETIME_YEARS,
                                help=f"NREL: {NREL_LIFETIME_YEARS} years.")
        dep_rate = a2.slider(
            "Tax depreciation rate (% per year)", 10, 20, 20, 1,
            help="Straight-line. Batteries are not listed in the tax tables; the closest "
                 "category, electronic equipment, has a maximum of 20 % a year (PwC, Portugal). "
                 "The minimum allowed is half the maximum (Decreto Regulamentar 25/2009).") / 100
        wacc = a3.number_input("Discount rate (WACC)", min_value=0.0, max_value=0.3,
                               value=STEFFEN_WACC_PORTUGAL, step=0.005, format="%.3f",
                               help=f"Steffen 2020: {100 * STEFFEN_WACC_PORTUGAL:.1f} % "
                                    "after-tax for Portugal (onshore wind, "
                                    "2017 interest rates). Lazard's storage financing gives "
                                    f"{100 * LAZARD_WACC:.1f} %.")
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
            price = a1.number_input("Electricity price (€/kWh)", min_value=0.0,
                                    value=FIXED_ELECTRICITY_PRICE, step=0.01)
            spread = a1.number_input("Arbitrage spread (€/kWh)", min_value=0.0,
                                     value=FIXED_SPREAD, step=0.01,
                                     help="Selling price minus buying price.")
            arb = None
        else:
            arb = arbitrage_prices(daily, cpy_run)
            price, spread = arb["electricity_price"], arb["spread"]
        st.caption(f"Operation and maintenance ({om_text()}). Depth of discharge: "
                   f"{100 * dod_run:.0f} % (simulated cycle). Operation starts in {START_YEAR}; "
                   f"prices and grid fees rise {100 * INFLATION:g} % a year (ECB inflation "
                   f"target). {irc_text()}. System regulation charges: exempt (ERSE Orientação "
                   "1/2026, below 10 MVA).")

    # The economics use the ageing curve itself, cycle by cycle. The battery is retired at the
    # capacity threshold with the highest NPV: the run's one end of life, also used by the LCA.
    tea_inputs = {"soh_curve": soh_curve, "capex_eur_kwh": capex, "capacity_kwh": pack_kwh,
                  "electricity_price": price, "spread": spread, "round_trip_eff": rte,
                  "cycles_per_year": int(round(cpy_run)), "dod": dod_run, "years": int(years),
                  "wacc": wacc,
                  "grid_fee_eur_kwh": GRID_FEE_SCENARIOS[fee_case][0],
                  "grid_fee_eur_kw_day": GRID_FEE_SCENARIOS[fee_case][1],
                  "charge_power_kw": pack_kwh * cc_run, "depreciation_rate": dep_rate}
    tea_inputs, tea, sens, retire_table, best = tea_analysis(tea_inputs)
    retire_pct = round(100 * tea_inputs["retire_below"])        # end of life [%]
    # for both reports: the one end of life and the two efficiencies (each report explains its own)
    run_info.update({"eol_basis": "Retirement threshold with the highest NPV (TEA of this run)",
                     "rte_cell": rte_cell, "rte_system": rte})

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

    st.info(f"**End of life: {retire_pct} % capacity**, the retirement threshold with the "
            "highest NPV. The economics, the LCA (Environment tab) and both reports all use it.")
    with st.expander("When to retire the battery"):
        st.write(f"Highest NPV when the battery is retired below **{retire_pct} %** capacity "
                 f"(NPV €{best['NPV [€]']:,.0f}). The table shows the NPV of every threshold "
                 "tried.")
        st.caption("A retired battery earns nothing and has no resale value here, so it pays to "
                   "keep it while one more year of arbitrage covers that year's operating costs "
                   "(O&M, warranty, grid fees). Idea: Thelen et al. (2023), who chose the "
                   "retirement of each cell from its predicted capacity curve.")
        if retire_pct <= MIN_SOH:
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

    fig = go.Figure([
        go.Bar(y=sens["Parameter"], x=sens["ΔNPV at -20% [€]"], orientation="h", name="Input −20 %"),
        go.Bar(y=sens["Parameter"], x=sens["ΔNPV at +20% [€]"], orientation="h", name="Input +20 %"),
    ])
    fig.update_layout(title="What moves the NPV most?", barmode="relative", xaxis_title="Change in NPV [€]")
    st.plotly_chart(fig, width="stretch")

    with st.expander("Second life: EV battery reused for storage"):
        st.write("First life in a car (one drive and one charge a day, to 100 % for LFP and "
                 "80 % for the others, parked in between at the ambient temperature), then the same battery runs the storage cycle above "
                 "from the capacity it left the car with.")
        s1, s2, s3 = st.columns(3)
        ev_years = s1.number_input("Years in the car", min_value=1, max_value=20, value=8)
        km_day = s2.number_input("Distance per day (km)", min_value=1.0, value=50.0, step=5.0,
                                 help="50 km/day for 8 years is Euro 7's 160,000 km.")
        ev_charge = s3.number_input("Charge rate in the car (C)", min_value=0.05, max_value=5.0,
                                    value=0.18, step=0.05,
                                    help="0.18C is 11 kW AC on a 60 kWh pack; DC fast "
                                         "charging is about 1-2C.")
        s4, s5 = st.columns(2)
        sl_buy = s4.number_input(
            "Price paid for the used battery ($ per kWh it still holds)", min_value=0.0,
            value=round(B2U_BUY_USD_KWH_LEFT, 2),
            help="NREL B2U Repurposing Cost Calculator (2020) at its defaults: $19.62 per "
                 "nameplate kWh for a battery with 70 % left.")
        second_years = s5.number_input("Second-life years", min_value=1, max_value=20, value=8)
        q_ev, euro7, car_loss = ev_first_life(chem, ev_years, km_day, pack_kwh, KWH_PER_KM,
                                              ev_charge, t_run)
        t_age, soc_age, temp_age = result["ageing_cycle"]
        sl_curve = cut_at_data_end(second_life_curve(chem, t_age, soc_age, temp_age,
                                                     PROJECTION_CYCLES, car_loss, na_fade_run))
        sl_capex = second_life_capex_eur_kwh(q_ev[-1], sl_buy)
        sl_start = START_YEAR + int(ev_years)
        sl = second_life(dict(tea_inputs, start_year=sl_start, retire_below=MIN_SOH / 100),
                         sl_curve, sl_capex, second_years)
        new = calculate_tea(**dict(tea_inputs, start_year=sl_start, years=int(second_years)))
        st.caption(f"Second-life system cost: €{sl_capex:.0f} per nameplate kWh: the used "
                   f"battery (${repurposed_pack_usd_kwh(q_ev[-1], sl_buy):.0f}/kWh, of which "
                   f"${B2U_REPURPOSING_USD_KWH:.2f} is collection, testing and repackaging, "
                   "NREL B2U; Dong et al. 2023 report "
                   f"${SECOND_LIFE_PACK_RANGE_USD[0]:.0f}–{SECOND_LIFE_PACK_RANGE_USD[1]:.0f}"
                   "/kWh) plus a new inverter, enclosure and installation (NREL system cost "
                   f"minus the BloombergNEF stationary pack price). A new {chem} system costs "
                   f"€{capex:.0f}/kWh. In storage, the calendar and cycling losses each go on "
                   "from where the car left them; a second-life battery runs until it reaches "
                   f"{MIN_SOH:.0f} % capacity.")
        r1, r2, r3 = st.columns(3)
        r1.metric("Capacity leaving the car", f"{100 * q_ev[-1]:.1f} %")
        ok = all(np.isnan(got) or got >= need for need, _, got in euro7)
        r2.metric("Euro 7 durability", "met" if ok else "not met",
                  help="; ".join(f"≥{100 * need:.0f} % at day {day:,}: "
                                 + ("beyond the years in the car" if np.isnan(got)
                                    else f"{100 * got:.1f} %")
                                 for need, day, got in euro7))
        r3.metric("Second-life NPV", f"€{sl['NPV [€]']:,.0f}")
        r4, r5, r6 = st.columns(3)
        r4.metric("New system NPV, same years", f"€{new['NPV [€]']:,.0f}",
                  help=f"A new {chem} system over the second life's {second_years} years, "
                       f"starting in {sl_start}.")
        r5.metric("Second life minus new", f"€{sl['NPV [€]'] - new['NPV [€]']:,.0f}")
        r6.metric("Cell production avoided",
                  f"{pack_kwh * production_factors(chem)['gwp'] / 1000:.1f} t CO2eq",
                  help="The cells a new system would need (Degen et al. 2024, per kWh of "
                       "capacity). The repurposing itself is not counted.")
        if not math.isfinite(sl["SOH at start [%]"]):
            st.caption(f"The battery leaves the car below {MIN_SOH:.0f} % capacity, so it has "
                       "nothing left for a second life.")

    st.info(f"**{TEA_STATEMENT}.** The report documents goal and scope, technical analysis, "
            "economic analysis (cash flows by year), the LCA results, sensitivity analysis and "
            "a combined interpretation for this run, with an abstract that explains the result.")
    report_prices = None if arb is None else {
        "source": price_source, "first": daily["date"].min(), "last": daily["date"].max(),
        "days": len(daily), "days_used": arb["days_used"],
        "profitable_days": arb["profitable_days"]}
    # The TEA report includes the LCA of this run, which the Environment tab sets up, so its
    # download buttons are added to this place after that tab (see the end of the script).
    tea_report_slot = st.container()

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
with environment_tab:
    with st.expander("Assumptions", expanded=False):
        b1, b2 = st.columns(2)
        stationary = b1.radio("Use", ["Stationary storage (this simulation)",
                                      "Electric vehicle"]).startswith("Stationary")
        eol_pct = retire_pct              # the run's one end of life (Economics tab)
        if stationary:
            b1.caption(f"End of service life: **{eol_pct} %** capacity, the retirement threshold "
                       "with the highest NPV (Economics tab).")
            service_years = b1.number_input("Service life cap (years)", min_value=1,
                                            max_value=30, value=int(years))
            lifetime_km, kwh_per_km = LIFETIME_KM, KWH_PER_KM
        else:
            service_years = int(years)
            lifetime_km = b1.number_input("Vehicle lifetime (km)", value=LIFETIME_KM, step=10000)
            kwh_per_km = b1.number_input("Consumption (kWh/km)", value=KWH_PER_KM, step=0.01)
        grid = b2.number_input("Grid carbon intensity (g CO2eq/kWh)", value=GRID_G_CO2_PER_KWH,
                               step=10.0,
                               help="Assumption: set it to the grid that charges the battery.")
        rte_lca = b2.slider("Round-trip efficiency ", 0.70, 0.98,
                            round(float(np.clip(rte_cell, 0.70, 0.98)), 2), 0.01,
                            help="Default: the energy efficiency of the simulated cycles (the "
                                 "cell; the battery's own losses).")

    use_case = "stationary" if stationary else "ev"
    lca_args = {"eol_soh": eol_pct / 100, "service_years": service_years,
                "cycles_per_year": cpy_run, "round_trip_eff": rte_lca,
                "grid_g_co2_per_kwh": grid, "lifetime_km": lifetime_km,
                "kwh_per_km": kwh_per_km}
    lca = lca_results(chem, pack_kwh, soh_curve, use_case, **lca_args)
    phases, ind = lca["phases"], lca["ind"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Carbon footprint (EU scope)",
              f"{ind[CFB_KEY]:.0f} g CO2eq/kWh",
              help="Production + end of life, per kWh delivered over the service life "
                   "(Regulation (EU) 2023/1542 excludes the use phase).")
    c2.metric("Incl. battery losses", f"{ind[CFB_USE_KEY]:.0f} g CO2eq/kWh")
    c3.metric("Water consumption", f"{ind[WATER_KEY]:.2f} L/kWh",
              help="ReCiPe 2016 water consumption potential, production only (Degen et al. 2024).")
    c4.metric("Freshwater ecotoxicity (g 1,4-DCB eq/kWh)",
              f"{ind[ECOTOX_KEY]:.1f}",
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
    if stationary and eol_pct < 100 * CFB_MIN_EOL_SOH:
        st.warning(f"The end of life ({eol_pct} %) is below the {100 * CFB_MIN_EOL_SOH:.0f} % "
                   "minimum of the EU carbon-footprint rules (JRC CFB-IND), so the "
                   "regulation-scope value is not a conforming declaration. The LCA report "
                   f"shows the value at {100 * CFB_MIN_EOL_SOH:.0f} % in its sensitivity check.")
    st.info(f"**{LCA_STATEMENT}.** The report below documents goal and scope, inventory, "
            "impact assessment, interpretation (with a sensitivity check) and reporting for "
            "this run.")
    # Reports are built only when a download button is pressed (partial = a function to call)
    lca_report = partial(build_lca_report, chem, pack_kwh, soh_curve, use_case, run_info,
                         lca_args)
    r1, r2 = st.columns(2)
    r1.download_button("📄 Download screening LCA report (PDF)", lca_report,
                       f"screening_LCA_{chem}.pdf", "application/pdf", width="stretch")
    r2.download_button("📝 Download screening LCA report (Word)", partial(lca_report, fmt="docx"),
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
    compare = compare_chemistries(cc_run, cd_run, cycling_c_run, t_run, cpy_run, na_fade_run,
                                  n_run, tea_inputs, pack_kwh, use_case, lca_args)
    st.caption(f"Sodium-ion uses {100 * na_fade_run:.3f} % loss per cycle (sidebar setting when "
               f"sodium-ion was last run; {100 * SodiumIon.FADE_PER_EFC:g} % otherwise).")
    table(compare)
    st.caption("Combined interpretation (ISO/TS 14076, eTEA): cost (LCOS) and carbon footprint "
               "share the same functional unit, 1 kWh delivered, the same ageing curve and the "
               "same end of life: each chemistry is retired at its own threshold of highest NPV, "
               "and its LCA counts the energy delivered until then.")
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
    # meta already holds chemistry, model, cycles_to_80pct, h_cooling and cycling_c
    metadata = dict(meta, charge_rate_C=cc_run, discharge_rate_C=cd_run, cycles=n_run,
                    ambient_c=t_run, cooling=cool_run, final_soh_pct=soh_final,
                    sodium_fade_per_cycle=na_fade_run, retire_below_pct=retire_pct,
                    pack_kwh=pack_kwh, cells_needed=cells_needed)
    d3.download_button("Run settings (JSON)", json.dumps(metadata, indent=2, default=float),
                       f"settings_{chem}.json", "application/json", width="stretch")
    with st.expander("Preview: capacity per cycle"):
        table(cycles_df)


# ---------------------------------------------------------------------------
# TEA report (Economics tab): one LCA for the whole run, the one of the Environment tab
# ---------------------------------------------------------------------------
with tea_report_slot:
    if use_case == "stationary":
        lca_for_tea = ind
    else:            # the TEA is for stationary storage: the same inputs, stationary use
        lca_for_tea = lca_results(chem, pack_kwh, soh_curve, "stationary", **lca_args)["ind"]
    tea_report = partial(build_tea_report, chem, run_info, tea_inputs, report_prices, fee_case,
                         lca_for_tea, tea=tea, sens=sens, retirement=retire_table)
    t1, t2 = st.columns(2)
    t1.download_button("📄 Download TEA report (PDF)", tea_report,
                       f"TEA_{chem}.pdf", "application/pdf", width="stretch")
    t2.download_button("📝 Download TEA report (Word)", partial(tea_report, fmt="docx"),
                       f"TEA_{chem}.docx", DOCX_MIME, width="stretch")
    st.caption("The LCA results in this report are those of the Environment tab"
               + ("." if use_case == "stationary" else ", for stationary use."))

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
