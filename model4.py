import pandas as pd
import numpy as np
from utils import compute_distance

PAIR_LIMIT = 12000

def run_model(demand_df, depots_df, baseline_df, selected_month, active_depots):

    # -------------------------------
    # DATA PREP
    # -------------------------------
    demand_df = demand_df.copy()
    baseline_df = baseline_df.copy()

    demand_df["ID"] = demand_df["ID"].astype(str)
    baseline_df["Shop ID"] = baseline_df["Shop ID"].astype(str)
    baseline_df["Paired With"] = baseline_df["Paired With"].astype(str)

    months = [col for col in demand_df.columns if "Demand" in col]
    idx = months.index(selected_month)
    next_month = months[(idx + 1) % len(months)]

    demand_map = dict(zip(demand_df["ID"], demand_df[next_month]))

    shops = demand_df.copy()
    # Store baseline depot
    baseline_map = dict(zip(baseline_df["Shop ID"], baseline_df["Depot"]))
    shops["Baseline Depot"] = shops["ID"].map(baseline_map)
    shops["ID"] = shops["ID"].astype(str)
    shops["Demand"] = shops["ID"].map(demand_map)

    depots = depots_df[depots_df["Depot Name"].isin(active_depots)].reset_index(drop=True)

    pair_map = dict(zip(baseline_df["Shop ID"], baseline_df["Paired With"]))

    # -------------------------------
    # STEP 1: NEAREST DEPOT ASSIGNMENT
    # -------------------------------
    assignment = []

    for _, shop in shops.iterrows():

        min_d = float("inf")
        nearest = None

        for _, depot in depots.iterrows():
            d = compute_distance(
                shop["Latitude"], shop["Longitude"],
                depot["Latitude"], depot["Longitude"]
            )

            if d < min_d:
                min_d = d
                nearest = depot["Depot Name"]

        assignment.append(nearest)

    shops["Depot"] = assignment

    # -------------------------------
    # STEP 2: CAPACITY-CONSTRAINED REASSIGNMENT
    # -------------------------------
    cap_map = dict(zip(depots["Depot Name"], depots["Capacity(kg)"]))

    def get_loads(df):
        return df.groupby("Depot")["Demand"].sum().to_dict()

    def reassign(shops):

        MAX_ITER = 50   # prevent infinite loop

        for _ in range(MAX_ITER):

            loads = get_loads(shops)

            overloaded = [
                d for d in loads if loads[d] > cap_map[d]
            ]

            if not overloaded:
                break

            for depot_name in overloaded:

                depot_shops = shops[shops["Depot"] == depot_name].copy()

                # -------------------------------
# BATCH REASSIGNMENT (FINAL FIX)
# -------------------------------

# compute distance to nearest alternate depot
                depot_shops["alt_depot"] = None
                depot_shops["alt_distance"] = np.inf

                for idx2, row2 in depot_shops.iterrows():

                    best_alt = None
                    best_alt_dist = float("inf")

                    for _, alt_depot in depots.iterrows():

                        alt_name = alt_depot["Depot Name"]

                        if alt_name == depot_name:
                            continue

                        d_alt = compute_distance(
                            row2["Latitude"], row2["Longitude"],
                            alt_depot["Latitude"], alt_depot["Longitude"]
                        )

                        if d_alt < best_alt_dist:
                            best_alt_dist = d_alt
                            best_alt = alt_name

                    depot_shops.at[idx2, "alt_depot"] = best_alt
                    depot_shops.at[idx2, "alt_distance"] = best_alt_dist


                # sort by closest alternate depot
                depot_shops = depot_shops.sort_values("alt_distance")

                # move shops until load is ok
                for idx2, row2 in depot_shops.iterrows():

                    if loads[depot_name] <= cap_map[depot_name]:
                        break

                    alt_name = row2["alt_depot"]

                    if alt_name is None:
                        continue

                    # distance constraint (strict)
                    d_current = compute_distance(
                        row2["Latitude"], row2["Longitude"],
                        depots[depots["Depot Name"] == depot_name].iloc[0]["Latitude"],
                        depots[depots["Depot Name"] == depot_name].iloc[0]["Longitude"]
                    )

                    d_alt = row2["alt_distance"]

                    if d_alt > d_current + 8:
                        continue

                    if d_alt > 25:
                        continue

                    # allow slight overload
                    if loads.get(alt_name, 0) + row2["Demand"] <= 1.1 * cap_map[alt_name]:

                        shops.at[idx2, "Depot"] = alt_name

                        # update loads immediately
                        loads[depot_name] -= row2["Demand"]
                        loads[alt_name] = loads.get(alt_name, 0) + row2["Demand"]

        return shops

    shops = reassign(shops)

    # -------------------------------
    # PAIR HANDLING
    # -------------------------------
    shops["Paired Shop"] = shops["ID"].map(pair_map)

    valid_pairs = set()

    for _, row in shops.iterrows():

        sid = str(row["ID"])
        paired = str(row["Paired Shop"])

        if pd.isna(paired) or paired == "nan":
            continue

        if paired not in shops["ID"].values:
            continue

        pair_row = shops[shops["ID"] == paired].iloc[0]

        if row["Demand"] + pair_row["Demand"] <= PAIR_LIMIT:
            valid_pairs.add(tuple(sorted([sid, paired])))
        else:
            shops.loc[shops["ID"] == sid, "Paired Shop"] = None

    # -------------------------------
    # DISTANCE CALCULATION
    # -------------------------------
    depot_distance = {d: 0 for d in depots["Depot Name"]}
    visited = set()

    for _, row in shops.iterrows():

        sid = str(row["ID"])

        if sid in visited:
            continue

        depot_name = row["Depot"]
        depot = depots[depots["Depot Name"] == depot_name].iloc[0]

        paired = row["Paired Shop"]

        if pd.notna(paired) and paired != "nan":
            pair_tuple = tuple(sorted([sid, str(paired)]))

            if pair_tuple in valid_pairs and paired not in visited:

                pair_row = shops[shops["ID"] == paired].iloc[0]

                d1 = compute_distance(
                    row["Latitude"], row["Longitude"],
                    depot["Latitude"], depot["Longitude"]
                )

                d2 = compute_distance(
                    row["Latitude"], row["Longitude"],
                    pair_row["Latitude"], pair_row["Longitude"]
                )

                depot_distance[depot_name] += (d1 + d2)

                visited.add(sid)
                visited.add(paired)
                continue

        d = compute_distance(
            row["Latitude"], row["Longitude"],
            depot["Latitude"], depot["Longitude"]
        )

        depot_distance[depot_name] += d
        visited.add(sid)

    # -------------------------------
    # SUMMARY
    # -------------------------------
    summary = shops.groupby("Depot").agg({
        "ID": "count",
        "Demand": "sum"
    }).reset_index()

    summary.columns = ["Depot", "No of Shops", "Total Demand"]

    summary["Utilisation %"] = summary.apply(
        lambda r: (r["Total Demand"] / cap_map[r["Depot"]]) * 100
        if cap_map[r["Depot"]] > 0 else 0,
        axis=1
    )

    summary["Total Distance"] = summary["Depot"].map(depot_distance)

    # -------------------------------
    # FINAL FORMAT
    # -------------------------------
    shops.rename(columns={
        "ID": "Shop ID",
        "Latitude": "lat",
        "Longitude": "lon"
    }, inplace=True)

    # -------------------------------
# REASSIGNMENT TRACKING
# -------------------------------
    reassigned = shops[shops["Baseline Depot"] != shops["Depot"]].copy()

    reassigned = reassigned[[
        "Shop ID",
        "Baseline Depot",
        "Depot"
    ]]

    reassigned.columns = [
        "Shop ID",
        "From Depot",
        "To Depot"
    ]

    return shops, summary, reassigned