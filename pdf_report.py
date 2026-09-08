"""Generate a complete, printable PDS scenario report without an API key."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core import Scenario, ScenarioResult
from reporting import executive_summary


def build_pdf_report(
    scenario: Scenario,
    result: ScenarioResult,
    inventory_by_shop: dict[str, float],
    selected_shop_id: str | None = None,
) -> bytes:
    """Create a full audit report, including every shop assignment as an appendix."""
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
        title=f"PDS scenario report - {scenario.name}",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", parent=styles["Title"], textColor=colors.HexColor("#163A5F"), spaceAfter=8))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=7, leading=9))
    story: list[Any] = [
        Paragraph("PDS Supply Chain Resilience Platform", styles["ReportTitle"]),
        Paragraph("Scenario planning report - generated from the supplied project data", styles["Heading3"]),
        Spacer(1, 5 * mm),
        Paragraph(f"<b>Scenario:</b> {scenario.name}<br/><b>Planning month:</b> {scenario.month.replace('Demand ', '')}<br/><b>Active depots:</b> {', '.join(scenario.active_depots)}", styles["BodyText"]),
        Spacer(1, 4 * mm),
        Paragraph(executive_summary(scenario, result), styles["BodyText"]),
        Spacer(1, 5 * mm),
        Paragraph("Key metrics", styles["Heading2"]),
        _table(
            [["Total shops", "Reassigned shops", "Reassigned demand (kg)", "Highest utilisation", "Allocation distance (km)", "Unresolved shops"], [
                f"{result.metrics['shops_total']:,}",
                f"{result.metrics['shops_reassigned']:,}",
                f"{result.metrics['reassigned_demand_kg']:,.0f}",
                f"{result.metrics['max_utilisation_pct']:.1f}%",
                f"{result.metrics['total_distance_km']:,.1f}",
                f"{result.metrics['unresolved_shops']}",
            ]],
            [30 * mm, 30 * mm, 40 * mm, 38 * mm, 45 * mm, 30 * mm],
        ),
        Spacer(1, 5 * mm),
        Paragraph("Depot capacity summary", styles["Heading2"]),
        _frame_to_table(result.depot_summary, ["depot", "capacity_kg", "shop_count", "total_demand_kg", "total_distance_km", "utilisation_pct", "status"], styles),
    ]

    if selected_shop_id:
        selected = result.assignments[result.assignments["shop_id"].str.upper() == selected_shop_id.upper()]
        if not selected.empty:
            row = selected.iloc[0]
            inventory = inventory_by_shop.get(str(row["shop_id"]), float(row["demand_kg"]))
            story.extend([
                Spacer(1, 5 * mm),
                Paragraph("Requested shop assignment", styles["Heading2"]),
                _table(
                    [["Shop ID", "Assigned depot", "Baseline depot", "Monthly demand (kg)", "Demo inventory (kg)", "Distance (km)"], [
                        str(row["shop_id"]), str(row["assigned_depot"]), str(row["baseline_depot"]),
                        f"{row['demand_kg']:,.0f}", f"{inventory:,.0f}", f"{row['assigned_distance_km']:.2f}",
                    ]],
                    [30 * mm, 48 * mm, 48 * mm, 36 * mm, 36 * mm, 28 * mm],
                ),
            ])

    report_assignments = result.assignments.copy()
    report_assignments["demo_inventory_kg"] = report_assignments["shop_id"].map(lambda shop: inventory_by_shop.get(str(shop), 0.0))
    report_assignments["reassigned_from_baseline"] = report_assignments["reassigned_from_baseline"].map({True: "Yes", False: "No"})
    story.extend([
        PageBreak(),
        Paragraph("Complete shop-assignment appendix", styles["Heading2"]),
        Paragraph("Demo inventory is an in-session value entered in the web application. It is not a source-system stock balance.", styles["Small"]),
        Spacer(1, 3 * mm),
        _frame_to_table(report_assignments, ["shop_id", "assigned_depot", "baseline_depot", "demand_kg", "demo_inventory_kg", "assigned_distance_km", "reassigned_from_baseline"], styles),
        Spacer(1, 4 * mm),
        Paragraph("Model boundary: this report is a scenario-planning artifact. All capacity and distance thresholds are project assumptions documented in model_rules.md, not official operating policy.", styles["Small"]),
    ])
    document.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return output.getvalue()


def _frame_to_table(frame: pd.DataFrame, columns: list[str], styles: Any) -> Table:
    labels = [column.replace("_", " ").title() for column in columns]
    rows = [labels]
    for _, row in frame[columns].iterrows():
        formatted = []
        for column in columns:
            value = row[column]
            if isinstance(value, float):
                formatted.append(f"{value:,.2f}")
            else:
                formatted.append(str(value))
        rows.append(formatted)
    widths = [48 * mm, 50 * mm, 48 * mm, 27 * mm, 32 * mm, 28 * mm, 31 * mm][: len(columns)]
    return _table(rows, widths, font_size=6.2)


def _table(rows: list[list[str]], widths: list[float], font_size: float = 7.5) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#163A5F")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("LEADING", (0, 0), (-1, -1), font_size + 1.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C8D4E0")),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F7FAFC")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _page_number(canvas: Any, document: Any) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#536273"))
    canvas.drawRightString(285 * mm, 8 * mm, f"PDS scenario report | Page {document.page}")
    canvas.restoreState()
