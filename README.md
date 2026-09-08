# PDS Supply Chain Resilience Platform

An interactive scenario-planning application for a Public Distribution System depot network. It uses the supplied monthly shop demand, depot capacity, and baseline clustering workbooks to simulate depot closures and produce auditable shop reassignments.

## What it does

- Loads 964-shop monthly-demand data, six-depot capacity data, and baseline cluster data.
- Accepts a constrained natural-language request such as **“Close CSK in August.”**
- Validates the month and depot against the supplied Excel data.
- Assigns shops to the nearest active depot, then reassigns shops from overloaded depots when the configured rules permit it.
- Displays depot capacity, utilization, shop assignments, reassignments, and an interactive map.
- Exports scenario metadata and detailed results to an Excel workbook.

## Run locally

1. Install Python 3.11 or later.
2. In this directory, create and activate a virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies and start the app:

   ```powershell
   pip install -r requirements.txt
   streamlit run app.py
   ```

## Scope boundary

This is a planning simulation, not an operational control system. It uses deterministic Python calculations; no LLM calculates allocations or capacity. The prompt interface is deliberately constrained and declines irrelevant questions. The project rules are documented in `docs/model_rules.md`; they are not official government policy.

## Resume-safe description

> Built a Python and Streamlit PDS network-resilience simulator using monthly demand, depot capacities, and baseline clusters. Implemented capacity-constrained shop reassignment, geospatial scenario visualization, utilization analysis, and auditable Excel scenario exports for depot-disruption planning.
