"""Battery Digital Twin dashboard. Start it with:  python -m streamlit run app.py"""
import json
import math
import sys

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from battery_twin.ageing import predict_capacity
from battery_twin.chemistry import (CALIBRATED_H_COOLING, CHEMISTRIES, DETAILED_CYCLES,
                                    PROJECTION_CYCLES, fit_sqrt_fade, run_battery_test,
                                    standard_profile)
from battery_twin.economics import calculate_tea, second_life, sensitivity
from battery_twin.environment import calculate_lca

# Started with "python app.py" or the editor's Run button: explain and stop.
if not st.runtime.exists():
    sys.exit("This is a Streamlit dashboard. Start it from the project folder with:\n"
             "    python -m streamlit run app.py")

st.set_page_config(page_title="Battery Digital Twin", page_icon="🔋", layout="wide")


@st.cache_data(show_spinner=False)
def simulate(chemistry, model_type, c_charge, c_discharge, n_cycles, ambient_c, h_cooling):
    return run_battery_test(chemistry, model_type, c_charge, c_discharge, n_cycles, ambient_c, h_cooling)


def table(df):
    st.dataframe(df.round(3), width="stretch", hide_index=True)


def fmt_number(x, decimals=0):
    return "—" if x is None or not math.isfinite(x) else f"{x:,.{decimals}f}"


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
c_charge = st.sidebar.select_slider("Charge rate (C)", [0.3, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0], value=0.5,
                                    help="1C = full charge in about one hour.")
c_discharge = st.sidebar.select_slider("Discharge rate (C)", [0.3, 0.5, 1.0, 1.5, 2.0, 3.0], value=1.0)
ambient_c = st.sidebar.slider("Ambient temperature (°C)", 5, 45, 25, 5)
pack_kwh = st.sidebar.number_input("Pack size (kWh)", min_value=0.1, value=60.0, step=5.0,
                                   help="Used for the cell count, economics and environment.")

with st.sidebar.expander("Advanced"):
    detailed = st.checkbox("Detailed physics (DFN, slower)",
                           help="Charging above 2C always uses the detailed model.")
    h_cooling = st.slider("Cooling coefficient h (W/m²K)", 5, 100, int(CALIBRATED_H_COOLING), 1,
                          help="13 W/m²K matches the measured self-heating in Kirkaldy et al. (2024).")

is_sodium = CHEMISTRIES[chemistry]["family"] == "sodium_ion"
model_type = "DFN" if (detailed or c_charge > 2.0 or is_sodium) else "SPMe"
if c_charge > 2.0 and not detailed and not is_sodium:
    st.sidebar.caption("Charging above 2C: the detailed model is used automatically.")

inputs = (chemistry, model_type, c_charge, c_discharge, n_cycles, ambient_c, h_cooling)
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
chem, model_run, cc_run, cd_run, n_run, t_run, h_run = st.session_state["inputs"]
cycles_df, series_df, eff_df, meta = result["cycles"], result["series"], result["efficiency"], result["meta"]
if st.session_state["inputs"] != inputs:
    st.warning("The settings have changed. Press **▶ Run** to update the results.")

# Values shared by all tabs
label = CHEMISTRIES[chem]["label"]
soh_final = float(cycles_df["SOH [%]"].iloc[-1])
soh_text = f"{soh_final:.1f} %" if math.isfinite(soh_final) else "below 50 %"
projection = result["projection"]
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

    years_80 = life_80 / 365
    st.write(
        f"Charging at **{cc_run:g}C** and discharging at **{cd_run:g}C** at **{t_run} °C**, "
        f"the battery keeps **{soh_text}** of its capacity after **{n_run:,} cycles**. "
        + (f"It reaches 80 % after about **{life_80:,.0f} cycles** "
           f"(≈ {years_80:.1f} years at one cycle per day)." if math.isfinite(life_80) else ""))

    fig = px.line(cycles_df, x="Cycle", y="SOH [%]", title="Capacity over cycles")
    fig.add_hline(y=80, line_dash="dot", annotation_text="80 % (typical end of life)")
    st.plotly_chart(fig, width="stretch")

    # Where the numbers come from, in one place
    st.info(f"**Ageing data:** {CHEMISTRIES[chem]['ageing_source']}. Curves stop at 50 % capacity, where the data end.")
    if meta["ageing_warnings"]:
        st.warning("Outside the conditions of the ageing data, so treat the lifetime as an "
                   "extrapolation: " + "; ".join(meta["ageing_warnings"]) + ".")
    if CHEMISTRIES[chem]["calibration"]:
        st.caption(f"Physics model: {CHEMISTRIES[chem]['calibration']}.")
    if not meta["has_ageing_physics"]:
        st.caption("Physics model: PyBaMM's sodium-ion model is isothermal, so the cell "
                   "temperature equals the ambient temperature.")
    if max_temp > 60:
        st.warning("The cell goes above 60 °C, beyond typical test and safety limits.")
    st.caption(f"Cycles 1–{DETAILED_CYCLES} are simulated with the physics model ({model_run}). "
               f"Their state-of-charge swing and cell temperature (mean "
               f"{meta['mean_cell_temperature_c']:.1f} °C) drive the empirical ageing model.")

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
        cycles_per_year = a2.number_input("Cycles per year", min_value=1, value=365)
        years = a2.number_input("Project lifetime (years)", min_value=1, max_value=30, value=15)
        wacc = a3.number_input("Discount rate", min_value=0.0, max_value=0.3, value=0.07, step=0.01)
        manual_fade = a3.number_input("Fade coefficient override (0 = simulated)", min_value=0.0,
                                      value=0.0, step=0.01,
                                      help="Capacity loss [%] = a·√cycles. Useful for sodium-ion.")

    # Fade coefficient fitted over the cycles the project will actually run
    horizon = int(cycles_per_year) * int(years)
    fade = fit_sqrt_fade(projection[projection["Cycle"] <= max(horizon, DETAILED_CYCLES)])
    tea_inputs = {"capex_eur_kwh": capex, "capacity_kwh": pack_kwh, "electricity_price": price,
                  "spread": spread, "round_trip_eff": rte,
                  "sqrt_fade_pct": manual_fade if manual_fade > 0 else fade,
                  "cycles_per_year": int(cycles_per_year), "years": int(years), "wacc": wacc}
    tea = calculate_tea(**tea_inputs)

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Net present value", f"€{fmt_number(tea['NPV [€]'])}")
    e2.metric("Internal rate of return", f"{fmt_number(tea['IRR [%]'], 1)} %")
    e3.metric("Payback", f"{fmt_number(tea['Discounted payback [years]'])} years")
    e4.metric("Cost of stored energy (LCOS)", f"€{fmt_number(tea['LCOS [€/kWh]'], 3)}/kWh")
    st.caption(f"Investment €{tea['CAPEX [€]']:,.0f}; capacity left at the end: "
               f"{tea['SOH at end [%]']:.1f} %.")

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
        r1.metric("Capacity at start of second life", f"{sl['SOH at start [%]']:.1f} %")
        r2.metric("Second-life NPV", f"€{fmt_number(sl['NPV [€]'])}")

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
               f"discharge, full depth, {t_run} °C), each with its own empirical ageing model. "
               "Economics and environment use the assumptions in their tabs.")
    t_std, soc_std = standard_profile(cc_run, cd_run)
    rows = []
    for name in CHEMISTRIES:
        q = predict_capacity(name, t_std, soc_std, [t_run] * len(t_std), PROJECTION_CYCLES)
        soh_curve = pd.DataFrame({"Cycle": range(1, PROJECTION_CYCLES + 1), "SOH [%]": 100 * q})
        horizon_rows = soh_curve[soh_curve["Cycle"] <= int(cycles_per_year) * int(years)]
        chem_tea = calculate_tea(**dict(tea_inputs, capex_eur_kwh=CHEMISTRIES[name]["capex_eur_kwh"],
                                        sqrt_fade_pct=fit_sqrt_fade(horizon_rows)))
        _, chem_lca = calculate_lca(name, pack_kwh, **lca_inputs)
        below = soh_curve.loc[soh_curve["SOH [%]"] < 80, "Cycle"]
        rows.append({"Chemistry": name,
                     f"Capacity after {n_run:,} cycles [%]": 100 * q[n_run - 1] if q[n_run - 1] >= 0.5 else None,
                     "Cycles until 80 %": int(below.iloc[0]) if len(below) else None,
                     "Pack cost [€]": chem_tea["CAPEX [€]"], "NPV [€]": chem_tea["NPV [€]"],
                     "LCOS [€/kWh]": chem_tea["LCOS [€/kWh]"],
                     "Carbon [kg CO2eq/MWh]": chem_lca["Levelised carbon [kg CO2eq/MWh delivered]"]})
    compare = pd.DataFrame(rows)
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
                    final_soh_pct=soh_final, fade_coefficient=fade, cycles_to_80pct=life_80,
                    pack_kwh=pack_kwh, cells_needed=cells_needed)
    d3.download_button("Run settings (JSON)", json.dumps(metadata, indent=2, default=float),
                       f"settings_{chem}.json", "application/json", width="stretch")
    with st.expander("Preview: capacity per cycle"):
        table(cycles_df)
