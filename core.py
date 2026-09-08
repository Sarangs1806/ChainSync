"""Deterministic allocation model for the PDS Supply Chain Resilience Platform."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DATA_DIR = Path(__file__).parent / "data"
MAX_ALTERNATE_DISTANCE_KM = 25.0
MAX_EXTRA_DISTANCE_KM = 8.0
RECEIVING_CAPACITY_TOLERANCE = 1.10
PAIR_LIMIT_KG = 12_000.0


@dataclass(frozen=True)
class Scenario:
    """Validated inputs for one reproducible planning run."""
    month: str
    active_depots: tuple[str, ...]
    name: str = "Ad-hoc scenario"


@dataclass
class ScenarioResult:
    assignments: pd.DataFrame
    depot_summary: pd.DataFrame
    reassignments: pd.DataFrame
    unresolved: pd.DataFrame
    metrics: dict[str, float | int | str]


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Fast local distance approximation, suitable for scenario comparison."""
    dlat = (lat1 - lat2) * 110.574
    dlon = (lon1 - lon2) * 111.320 * np.cos(np.radians(lat2))
    return float(np.sqrt(dlat**2 + dlon**2))


def load_data(data_dir: Path = DATA_DIR) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load and normalize the three supplied Excel workbooks."""
    demand = pd.read_excel(data_dir / "monthly_demand.xlsx")
    depots = pd.read_excel(data_dir / "depots.xlsx")
    baseline = pd.read_excel(data_dir / "baseline_clusters.xlsx")
    _require_columns(demand, {"ID", "Depot", "Latitude", "Longitude"}, "monthly_demand.xlsx")
    _require_columns(depots, {"Depot Name", "Latitude", "Longitude", "Capacity(kg)"}, "depots.xlsx")
    _require_columns(baseline, {"Shop ID", "Paired With", "Depot"}, "baseline_clusters.xlsx")
    demand["ID"] = demand["ID"].astype(str)
    baseline["Shop ID"] = baseline["Shop ID"].astype(str)
    baseline["Paired With"] = baseline["Paired With"].fillna("").astype(str)
    depots["Depot Name"] = depots["Depot Name"].astype(str)
    return demand, depots, baseline


def demand_months(demand: pd.DataFrame) -> list[str]:
    months = [column for column in demand.columns if column.startswith("Demand ")]
    if not months:
        raise ValueError("No columns beginning with 'Demand ' were found.")
    return months


def validate_scenario(scenario: Scenario, demand: pd.DataFrame, depots: pd.DataFrame) -> None:
    if scenario.month not in demand_months(demand):
        raise ValueError(f"Unknown demand month: {scenario.month}")
    known = set(depots["Depot Name"])
    invalid = set(scenario.active_depots) - known
    if invalid:
        raise ValueError(f"Unknown depot(s): {', '.join(sorted(invalid))}")
    if not scenario.active_depots:
        raise ValueError("At least one depot must remain active.")


def run_scenario(demand: pd.DataFrame, depots: pd.DataFrame, baseline: pd.DataFrame, scenario: Scenario) -> ScenarioResult:
    """Run nearest-assignment followed by capacity-constrained reassignment.

    An alternate depot must be within 25 km, add at most 8 km compared with the
    source assignment, and remain within 110% of its nominal capacity.
    """
    validate_scenario(scenario, demand, depots)
    active = depots[depots["Depot Name"].isin(scenario.active_depots)].copy()
    shops = demand[["ID", "Depot", "Latitude", "Longitude", scenario.month]].copy()
    shops.columns = ["shop_id", "baseline_depot_from_demand", "latitude", "longitude", "demand_kg"]
    shops["demand_kg"] = pd.to_numeric(shops["demand_kg"], errors="coerce").fillna(0.0)

    baseline_lookup = baseline.set_index("Shop ID")
    shops["baseline_depot"] = shops["shop_id"].map(baseline_lookup["Depot"]).fillna(shops["baseline_depot_from_demand"])
    shops["paired_shop"] = shops["shop_id"].map(baseline_lookup["Paired With"]).fillna("")

    assignments, nearest_distances = [], []
    for shop in shops.itertuples(index=False):
        distances = active.apply(lambda depot: distance_km(shop.latitude, shop.longitude, depot["Latitude"], depot["Longitude"]), axis=1)
        index = distances.idxmin()
        assignments.append(str(active.loc[index, "Depot Name"]))
        nearest_distances.append(float(distances.loc[index]))
    shops["assigned_depot"] = assignments
    shops["nearest_distance_km"] = nearest_distances

    shops = _relieve_overload(shops, active)
    shops["reassigned_from_baseline"] = shops["assigned_depot"] != shops["baseline_depot"]
    shops["valid_pair"] = shops.apply(lambda row: _is_valid_pair(row, shops), axis=1)
    summary = _build_summary(shops, active)
    unresolved = shops[shops["assigned_depot"] == "UNRESOLVED"].copy()
    reassignments = shops[shops["reassigned_from_baseline"]].copy()
    assigned = shops[shops["assigned_depot"] != "UNRESOLVED"]
    metrics: dict[str, float | int | str] = {
        "scenario_name": scenario.name,
        "shops_total": int(len(shops)),
        "shops_reassigned": int(len(reassignments)),
        "unresolved_shops": int(len(unresolved)),
        "reassigned_demand_kg": float(reassignments["demand_kg"].sum()),
        "total_distance_km": float(assigned["assigned_distance_km"].sum()),
        "max_utilisation_pct": float(summary["utilisation_pct"].max()) if len(summary) else 0.0,
    }
    return ScenarioResult(shops, summary, reassignments, unresolved, metrics)


def _relieve_overload(shops: pd.DataFrame, active: pd.DataFrame) -> pd.DataFrame:
    result = shops.copy()
    capacity = active.set_index("Depot Name")["Capacity(kg)"].to_dict()
    for _ in range(len(result)):
        loads = result.groupby("assigned_depot")["demand_kg"].sum().to_dict()
        overloaded = [depot for depot, load in loads.items() if load > capacity[depot] * RECEIVING_CAPACITY_TOLERANCE]
        if not overloaded:
            break
        moved_any = False
        for source in overloaded:
            candidates: list[tuple[float, int, str]] = []
            source_lat = active.loc[active["Depot Name"] == source, "Latitude"].iloc[0]
            source_lon = active.loc[active["Depot Name"] == source, "Longitude"].iloc[0]
            for idx, shop in result[result["assigned_depot"] == source].iterrows():
                current_distance = distance_km(shop["latitude"], shop["longitude"], source_lat, source_lon)
                for _, alternate in active.iterrows():
                    target = alternate["Depot Name"]
                    if target == source:
                        continue
                    alternate_distance = distance_km(shop["latitude"], shop["longitude"], alternate["Latitude"], alternate["Longitude"])
                    if alternate_distance <= MAX_ALTERNATE_DISTANCE_KM and alternate_distance - current_distance <= MAX_EXTRA_DISTANCE_KM:
                        candidates.append((alternate_distance, idx, target))
            for _, shop_index, target in sorted(candidates):
                if loads[source] <= capacity[source] * RECEIVING_CAPACITY_TOLERANCE:
                    break
                shop_demand = float(result.at[shop_index, "demand_kg"])
                if loads.get(target, 0.0) + shop_demand <= capacity[target] * RECEIVING_CAPACITY_TOLERANCE:
                    result.at[shop_index, "assigned_depot"] = target
                    loads[source] -= shop_demand
                    loads[target] = loads.get(target, 0.0) + shop_demand
                    moved_any = True
        if not moved_any:
            break
    coordinates = active.set_index("Depot Name")[["Latitude", "Longitude"]].to_dict("index")
    result["assigned_distance_km"] = result.apply(lambda row: distance_km(row["latitude"], row["longitude"], coordinates[row["assigned_depot"]]["Latitude"], coordinates[row["assigned_depot"]]["Longitude"]), axis=1)
    return result


def _build_summary(shops: pd.DataFrame, active: pd.DataFrame) -> pd.DataFrame:
    summary = shops.groupby("assigned_depot", as_index=False).agg(shop_count=("shop_id", "count"), total_demand_kg=("demand_kg", "sum"), total_distance_km=("assigned_distance_km", "sum")).rename(columns={"assigned_depot": "depot"})
    summary = active[["Depot Name", "Capacity(kg)"]].merge(summary, how="left", left_on="Depot Name", right_on="depot")
    summary[["shop_count", "total_demand_kg", "total_distance_km"]] = summary[["shop_count", "total_demand_kg", "total_distance_km"]].fillna(0)
    summary["shop_count"] = summary["shop_count"].astype(int)
    summary["utilisation_pct"] = 100 * summary["total_demand_kg"] / summary["Capacity(kg)"]
    summary["status"] = np.where(summary["utilisation_pct"] > 100, "Capacity exception", "Within capacity")
    summary = summary.drop(columns="depot", errors="ignore")
    summary = summary.rename(columns={"Depot Name": "depot", "Capacity(kg)": "capacity_kg"})
    return summary.sort_values("utilisation_pct", ascending=False)


def _is_valid_pair(row: pd.Series, shops: pd.DataFrame) -> bool:
    paired = str(row["paired_shop"])
    if not paired or paired.lower() == "nan":
        return False
    match = shops[shops["shop_id"] == paired]
    return bool(len(match) and float(row["demand_kg"]) + float(match.iloc[0]["demand_kg"]) <= PAIR_LIMIT_KG)


def _require_columns(frame: pd.DataFrame, expected: Iterable[str], filename: str) -> None:
    missing = set(expected) - set(frame.columns)
    if missing:
        raise ValueError(f"{filename} is missing required columns: {sorted(missing)}")
