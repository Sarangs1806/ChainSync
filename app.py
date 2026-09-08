from __future__ import annotations

import folium
import streamlit as st
from streamlit_folium import st_folium
from pathlib import Path

from core import Scenario, demand_months, load_data, run_scenario
from pdf_report import build_pdf_report
from prompting import interpret_prompt
from reporting import build_excel_export, executive_summary


st.set_page_config(page_title="PDS Resilience Platform", page_icon="🚚", layout="wide")


@st.cache_data
def get_data():
    return load_data()


try:
    demand, depots, baseline = get_data()
except Exception as error:
    st.error(f"Could not load project data: {error}")
    st.stop()

months = demand_months(demand)
depot_names = depots["Depot Name"].tolist()
st.title("PDS Supply Chain Resilience Platform")
st.caption("Scenario simulation for depot disruptions, capacity exposure, and shop reassignment. Planning tool only—not an operational control system.")

if "month_select" not in st.session_state:
    st.session_state.month_select = months[0]
if "active_depots" not in st.session_state:
    st.session_state.active_depots = depot_names.copy()
if "scenario_label" not in st.session_state:
    st.session_state.scenario_label = "Baseline - all depots active"
if "inventory_by_shop" not in st.session_state:
    st.session_state.inventory_by_shop = {}

# A prompt result is applied before widgets are rendered. This is important:
# Streamlit widgets retain their own state, so changing only a separate Python
# list would otherwise be overwritten by the old checkbox values.
if "pending_prompt_scenario" in st.session_state:
    pending = st.session_state.pop("pending_prompt_scenario")
    st.session_state.month_select = pending["month"]
    st.session_state.active_depots = pending["active_depots"]
    st.session_state.scenario_label = pending["label"]
    for depot in depot_names:
        st.session_state[f"depot_{depot}"] = depot in pending["active_depots"]
    st.session_state.run_requested = True
    st.session_state.prompt_feedback = pending["message"]
    if pending.get("shop_id"):
        st.session_state.shop_select = pending["shop_id"]

with st.sidebar:
    st.header("Scenario controls")
    scenario_name = st.text_input("Scenario label", key="scenario_label", help="A clear label for this planning run, for example: CSK closure - August.")
    selected_month = st.selectbox(
        "Planning month",
        months,
        key="month_select",
        format_func=lambda month: month.replace("Demand ", ""),
    )
    st.subheader("Test a depot disruption")
    prompt = st.text_area(
        "What would you like to test?",
        placeholder="Example: Close CSK in August and minimise extra travel distance.",
        height=100,
    )
    if st.button("Apply scenario", use_container_width=True):
        parsed = interpret_prompt(prompt, depot_names, months, demand["ID"].astype(str).tolist())
        if parsed.kind == "scenario":
            closed_short_names = ", ".join(name.split("(")[-1].rstrip(")") for name in parsed.inactive_depots)
            st.session_state.pending_prompt_scenario = {
                "month": parsed.month,
                "active_depots": [name for name in depot_names if name not in parsed.inactive_depots],
                "label": f"{closed_short_names} closure - {parsed.month.replace('Demand ', '')}",
                "message": parsed.message + " The scenario has now been run automatically.",
                "shop_id": parsed.shop_id,
            }
            st.rerun()
        elif parsed.kind == "metric_question":
            st.info(parsed.message)
        elif parsed.kind == "clarification":
            st.warning(parsed.message)
        else:
            st.error(parsed.message)
    st.subheader("Active depots")
    active = []
    for depot in depot_names:
        checkbox_key = f"depot_{depot}"
        if checkbox_key not in st.session_state:
            st.session_state[checkbox_key] = depot in st.session_state.active_depots
        if st.checkbox(depot, key=checkbox_key):
            active.append(depot)
    st.session_state.active_depots = active
    run_clicked = st.button("Run scenario", type="primary", use_container_width=True)

if "prompt_feedback" in st.session_state:
    st.success(st.session_state.pop("prompt_feedback"))

run_requested = st.session_state.pop("run_requested", False)
if run_clicked or run_requested or "result" not in st.session_state:
    try:
        scenario = Scenario(selected_month, tuple(active), scenario_name)
        st.session_state.result = run_scenario(demand, depots, baseline, scenario)
        st.session_state.scenario = scenario
    except ValueError as error:
        st.error(str(error))
        st.stop()

scenario = st.session_state.scenario
result = st.session_state.result

# The supplied files do not contain real inventory. This is a clearly labelled,
# in-session demonstration balance initialized from selected-month demand.
inventory_context = (scenario.month, tuple(scenario.active_depots))
if st.session_state.get("inventory_context") != inventory_context:
    st.session_state.inventory_by_shop = {
        str(row.shop_id): float(row.demand_kg)
        for row in result.assignments.itertuples(index=False)
    }
    st.session_state.inventory_context = inventory_context

metric_columns = st.columns(4)
metric_columns[0].metric("Total shops", f"{result.metrics['shops_total']:,}")
metric_columns[1].metric("Reassigned shops", f"{result.metrics['shops_reassigned']:,}")
metric_columns[2].metric("Highest utilisation", f"{result.metrics['max_utilisation_pct']:.1f}%")
metric_columns[3].metric("Allocation distance", f"{result.metrics['total_distance_km']:,.1f} km")
st.subheader("Planner summary")
st.info(executive_summary(scenario, result))

tab_summary, tab_map, tab_shops, tab_assignments, tab_rules = st.tabs(["Depot summary", "Network map", "Shop operations", "All shop assignments", "Model rules"])
with tab_summary:
    st.dataframe(result.depot_summary, use_container_width=True, hide_index=True)
    left, right = st.columns(2)
    with left:
        st.download_button("Download audit-ready Excel output", data=build_excel_export(scenario, result), file_name=f"pds_scenario_{scenario.month.replace(' ', '_').lower()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with right:
        st.download_button(
            "Download complete PDF report",
            data=build_pdf_report(scenario, result, st.session_state.inventory_by_shop, st.session_state.get("shop_select")),
            file_name=f"pds_scenario_{scenario.month.replace(' ', '_').lower()}_report.pdf",
            mime="application/pdf",
        )
with tab_map:
    # OpenStreetMap is a public tile source and does not require a user API key.
    map_object = folium.Map(location=[demand["Latitude"].mean(), demand["Longitude"].mean()], zoom_start=9, tiles="OpenStreetMap")
    active_set = set(scenario.active_depots)
    for _, depot in depots.iterrows():
        color = "green" if depot["Depot Name"] in active_set else "red"
        folium.Marker([depot["Latitude"], depot["Longitude"]], tooltip=depot["Depot Name"], icon=folium.Icon(color=color)).add_to(map_object)
    for shop in result.assignments.itertuples(index=False):
        color = "orange" if shop.reassigned_from_baseline else "blue"
        folium.CircleMarker([shop.latitude, shop.longitude], radius=2, color=color, fill=True, fill_opacity=0.7, tooltip=f"{shop.shop_id} → {shop.assigned_depot}").add_to(map_object)
    st.caption("Green = active depot; red = inactive depot; orange = assignment differs from supplied baseline; blue = baseline-consistent assignment.")
    st_folium(map_object, use_container_width=True, height=600)
with tab_shops:
    st.subheader("Shop operations")
    st.caption("This is a demo inventory panel. Because the source workbooks contain demand but not real stock, each shop starts with inventory equal to its selected-month demand. Sales entered here are held only for this browser session.")
    shop_ids = result.assignments["shop_id"].astype(str).tolist()
    if "shop_select" not in st.session_state or st.session_state.shop_select not in shop_ids:
        st.session_state.shop_select = shop_ids[0]
    selected_shop = st.selectbox("Select a shop", shop_ids, key="shop_select")
    shop = result.assignments[result.assignments["shop_id"].astype(str) == str(selected_shop)].iloc[0]
    inventory = float(st.session_state.inventory_by_shop.get(str(selected_shop), shop["demand_kg"]))
    shop_metrics = st.columns(4)
    shop_metrics[0].metric("Assigned depot", shop["assigned_depot"])
    shop_metrics[1].metric("Baseline depot", shop["baseline_depot"])
    shop_metrics[2].metric("Monthly demand", f"{shop['demand_kg']:,.0f} kg")
    shop_metrics[3].metric("Current demo inventory", f"{inventory:,.0f} kg")
    sale_columns = st.columns([2, 1, 2])
    with sale_columns[0]:
        sale_kg = st.number_input("Record sales (kg)", min_value=0.0, value=0.0, step=1.0, key=f"sales_{selected_shop}")
    with sale_columns[1]:
        st.write("")
        st.write("")
        if st.button("Record sale", key=f"record_{selected_shop}"):
            if sale_kg <= 0:
                st.warning("Enter a sales value greater than zero.")
            elif sale_kg > inventory:
                st.error("Sales cannot exceed the current demo inventory.")
            else:
                st.session_state.inventory_by_shop[str(selected_shop)] = inventory - sale_kg
                st.success(f"Recorded {sale_kg:,.0f} kg sale for {selected_shop}.")
                st.rerun()
    with sale_columns[2]:
        if st.button("Reset all demo inventory", key="reset_inventory"):
            st.session_state.inventory_by_shop = {str(row.shop_id): float(row.demand_kg) for row in result.assignments.itertuples(index=False)}
            st.success("Demo inventory has been reset to selected-month demand for every shop.")
            st.rerun()
    if shop["reassigned_from_baseline"]:
        st.warning(f"This shop is assigned to {shop['assigned_depot']} in this scenario, rather than its supplied baseline depot: {shop['baseline_depot']}.")
    else:
        st.success("This shop remains assigned to its supplied baseline depot in this scenario.")

with tab_assignments:
    st.dataframe(result.assignments, use_container_width=True, hide_index=True)
    st.subheader("Assignments changed from the supplied baseline")
    st.dataframe(result.reassignments, use_container_width=True, hide_index=True)
with tab_rules:
    st.warning("These are project assumptions derived from the supplied code. They are not official Government of Kerala operating policy.")
    rules_path = Path(__file__).parent / "docs" / "model_rules.md"
    st.markdown(rules_path.read_text(encoding="utf-8"))
