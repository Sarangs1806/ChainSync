"""Export and deterministic executive-summary helpers."""

from __future__ import annotations

from io import BytesIO
import pandas as pd

from core import Scenario, ScenarioResult


def executive_summary(scenario: Scenario, result: ScenarioResult) -> str:
    metrics = result.metrics
    exceptions = result.depot_summary[result.depot_summary["utilisation_pct"] > 100]
    exception_text = "No active depot exceeds nominal capacity." if exceptions.empty else "Capacity review required for: " + ", ".join(exceptions["depot"].tolist()) + "."
    return (
        f"{scenario.name}: using {scenario.month.replace('Demand ', '')} demand, the model assigned "
        f"{metrics['shops_total']:,} shops across {len(scenario.active_depots)} active depot(s). Compared with the supplied baseline, "
        f"{metrics['shops_reassigned']:,} shop(s) were assigned to a different depot ({metrics['reassigned_demand_kg']:,.0f} kg demand). "
        f"Estimated one-way allocation distance is {metrics['total_distance_km']:,.1f} km. {exception_text} "
        "This is a planning simulation; a human planner must approve any operational change."
    )


def build_excel_export(scenario: Scenario, result: ScenarioResult) -> bytes:
    metadata = pd.DataFrame({"field": ["scenario_name", "demand_month", "active_depots", *result.metrics.keys()], "value": [scenario.name, scenario.month, "; ".join(scenario.active_depots), *result.metrics.values()]})
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        metadata.to_excel(writer, sheet_name="Scenario metadata", index=False)
        result.depot_summary.to_excel(writer, sheet_name="Depot summary", index=False)
        result.assignments.to_excel(writer, sheet_name="Shop assignments", index=False)
        result.reassignments.to_excel(writer, sheet_name="Reassignments", index=False)
        result.unresolved.to_excel(writer, sheet_name="Unresolved", index=False)
        for worksheet in writer.sheets.values():
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, 0, max(0, worksheet.dim_colmax))
    return buffer.getvalue()
