"""Safe offline interpretation for a natural-language scenario prompt."""

from __future__ import annotations

import re
from dataclasses import dataclass


MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december")
ACTION_WORDS = ("close", "closure", "shut", "shutdown", "deactivate", "inactive", "outage", "unavailable")
DOMAIN_WORDS = ("depot", "demand", "shop", "capacity", "utilisation", "utilization", "reassign", "scenario", "pds", "distribution")


@dataclass(frozen=True)
class PromptResult:
    kind: str  # scenario, metric_question, clarification, unsupported
    message: str
    month: str | None = None
    inactive_depots: tuple[str, ...] = ()
    shop_id: str | None = None


def interpret_prompt(
    text: str,
    depot_names: list[str],
    available_months: list[str],
    known_shop_ids: list[str] | None = None,
) -> PromptResult:
    """Accept only a narrow planning vocabulary; decline irrelevant questions."""
    clean = " ".join(text.lower().split())
    if not clean:
        return PromptResult("clarification", "Enter a PDS planning request, for example: 'Close CSK in August'.")
    if not any(word in clean for word in DOMAIN_WORDS + ACTION_WORDS):
        return PromptResult("unsupported", "I support PDS depot, capacity, demand, and reassignment scenarios only. Try: 'Close CSK in August'.")

    selected_month = _find_month(clean, available_months)
    closed_depots = tuple(name for name in depot_names if _matches_depot(clean, name))
    requested_shop = _find_shop_id(clean, known_shop_ids)
    asks_for_closure = any(word in clean for word in ACTION_WORDS)
    if asks_for_closure and not closed_depots:
        return PromptResult("clarification", "I understood a depot closure, but not the depot. Use a depot abbreviation or full name, e.g. 'Close CSK in August'.")
    if asks_for_closure and not selected_month:
        return PromptResult("clarification", "I understood the depot closure, but not the month. Add a month, e.g. 'Close CSK in August'.")
    if asks_for_closure:
        shop_note = f" I will also show the assignment for shop {requested_shop}." if requested_shop else ""
        return PromptResult(
            "scenario",
            f"Scenario understood: deactivate {', '.join(closed_depots)} for {selected_month.replace('Demand ', '')} demand.{shop_note}",
            selected_month,
            closed_depots,
            requested_shop,
        )
    if any(word in clean for word in ("utilisation", "utilization", "demand", "capacity", "reassign")):
        return PromptResult("metric_question", "This is a dashboard question. Run the selected scenario and inspect the KPI cards and depot summary below.", selected_month)
    return PromptResult("unsupported", "I can only process validated PDS planning scenarios. Try: 'Close CSK in August'.")


def _find_month(text: str, available_months: list[str]) -> str | None:
    for month in MONTHS:
        if re.search(rf"\b{month}\b", text):
            candidate = f"Demand {month.title()}"
            return candidate if candidate in available_months else None
    return None


def _matches_depot(text: str, name: str) -> bool:
    acronym_match = re.search(r"\(([A-Za-z]+)\)", name)
    if acronym_match and re.search(rf"\b{re.escape(acronym_match.group(1).lower())}\b", text):
        return True
    key_words = [word.lower() for word in re.findall(r"[A-Za-z]+", name) if len(word) > 3 and word.lower() not in {"north", "south"}]
    return len(key_words) >= 2 and all(word in text for word in key_words)


def _find_shop_id(text: str, known_shop_ids: list[str] | None) -> str | None:
    """Return a validated shop identifier when the prompt contains one."""
    match = re.search(r"\b\d{2}[a-z]{3}\d{3}\b", text, re.I)
    if not match:
        return None
    candidate = match.group(0).upper()
    if known_shop_ids is not None and candidate not in {str(shop).upper() for shop in known_shop_ids}:
        return None
    return candidate
