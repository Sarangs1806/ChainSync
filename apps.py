import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import numpy as np

from model4 import run_model

# LOAD DATA
demand_df = pd.read_excel("monthly_demand.xlsx")
depots_df = pd.read_excel("depots.xlsx")
baseline_df = pd.read_excel("baseline_clusters.xlsx")

months = [col for col in demand_df.columns if "Demand" in col and "Avg" not in col]

# SESSION STATE
if "stock" not in st.session_state:
    st.session_state.stock = {}

    for _, row in demand_df.iterrows():
        shop_id = str(row["ID"])
        initial_stock = row.get(months[0], 0)

        if pd.isna(initial_stock):
            initial_stock = 0

        st.session_state.stock[shop_id] = int(initial_stock)

col1, col2 = st.columns([1, 2])

# LEFT PANEL
with col1:

    st.title("Controls")

    selected_month = st.selectbox("Select Month", months, key="month_select")

    depot_list = depots_df["Depot Name"].tolist()

    st.subheader("Active Depots")

    active_depots = []

    for depot in depot_list:
        if st.toggle(depot, value=True):
            active_depots.append(depot)

    if st.button("Run Month End"):

        result_df, summary, reassigned_df = run_model(
            demand_df,
            depots_df,
            baseline_df,
            selected_month,
            active_depots
        )

        st.session_state["result_df"] = result_df
        st.session_state["summary"] = summary
        st.session_state["reassigned"] = reassigned_df

    if "summary" in st.session_state:

        st.subheader("Depot Summary")
        summary_display = st.session_state["summary"].copy()

        # Reset index from 1
        summary_display.index = range(1, len(summary_display) + 1)

        st.dataframe(summary_display)

        selected_depot = st.radio(
            "Select Depot",
            st.session_state["summary"]["Depot"],
            key="depot_select"
        )

        st.session_state["selected_depot"] = selected_depot

# RIGHT PANEL
with col2:

    if "result_df" in st.session_state:

        df = st.session_state["result_df"]
        depot = st.session_state.get("selected_depot", None)

        if depot:
            shops = df[df["Depot"] == depot]

            st.subheader(f"Shops in {depot}")
            # Remove monthly demand columns
            display_cols = [
                col for col in shops.columns
                if (("Demand" not in col or col == "Demand")
                and col != "Baseline Depot")
            ]

            shops_display = shops[display_cols].copy()
            shops_display = shops_display.drop(columns=["Depot"], errors="ignore")
            shops_display["Paired Shop"] = shops_display["Paired Shop"].replace(
    ["nan", np.nan, None], "None"
)

            st.dataframe(shops_display, hide_index=True)
            if "reassigned" in st.session_state:

                st.subheader("Reassigned Shops (from Baseline)")

                reassigned_display = st.session_state["reassigned"].copy()

                if len(reassigned_display) == 0:
                    st.write("No shops reassigned")
                else:
                    st.dataframe(reassigned_display, hide_index=True)

            # -------------------------------
            # CONTINUE EXISTING CODE
            # -------------------------------

            shop_id = st.selectbox(
                "Select Shop",
                shops["Shop ID"].astype(str),
                key="shop_select"
            )

            shop_row = shops[shops["Shop ID"] == shop_id].iloc[0]

            st.write("### Shop Details")
            st.write(f"Depot: {shop_row['Depot']}")
            paired = shop_row["Paired Shop"]

            if pd.isna(paired) or str(paired) == "nan":
                paired_display = "None"
            else:
                paired_display = paired

            st.write(f"Paired Shop: {paired_display}")

            shop_key = str(shop_id)

            if shop_key not in st.session_state.stock:
                st.session_state.stock[shop_key] = int(shop_row.get(selected_month, 0))

            stock = st.session_state.stock[shop_key]

            st.write(f"Stock: {int(stock)} kg")

            purchase = st.number_input("Purchase (kg)", min_value=0)

            if st.button("Update Stock"):
                shop_key = str(shop_id)

                st.session_state.stock[shop_key] = max(
                    0,
                    st.session_state.stock[shop_key] - purchase
                )

                st.rerun()

        # MAP
        st.subheader("Map")

        m = folium.Map(
            location=[df["lat"].mean(), df["lon"].mean()],
            zoom_start=10
        )

        for _, row in depots_df.iterrows():
            color = "green" if row["Depot Name"] in active_depots else "red"

            folium.Marker(
                [row["Latitude"], row["Longitude"]],
                popup=row["Depot Name"],
                icon=folium.Icon(color=color)
            ).add_to(m)

        # Use only shops from selected depot
        if depot:
            map_shops = df[df["Depot"] == depot]
        else:
            map_shops = df  # fallback

        for _, row in map_shops.iterrows():

            color = "yellow" if 'shop_id' in locals() and str(row["Shop ID"]) == str(shop_id) else "blue"

            folium.CircleMarker(
                [row["lat"], row["lon"]],
                radius=5,
                color=color,
                fill=True
            ).add_to(m)

        st_folium(m)