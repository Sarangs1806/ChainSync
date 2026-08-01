# Supply Chain Network Optimizer

> ⚠️ **WIP / Early Stage:** This project is currently in a very early stage and is undergoing a major structural overhaul. Expect bugs, messy code, and frequent breaking changes.

A Streamlit-based tool for spatial optimization and capacity-constrained reassignment in supply chain networks. Originally built for public distribution systems, the core logic is currently being generalized to handle broader logistics, depot-node mapping, and resource pairing.

## Current Features
- Computes distances between supply nodes (depots) and demand nodes (shops).
- Nearest-depot assignment with automatic fallback if capacity limits are breached.
- Interactive map visualization using Folium.
- Batch reassignment logic to handle overloaded depots.

## Running Locally

Make sure you have your environment set up, then install the dependencies and run the Streamlit app:

```bash
pip install -r requirements.txt
streamlit run apps.py

Core Files
apps.py - The Streamlit frontend and state management.

model4.py - Core optimization and reassignment logic.

utils.py - Math and distance computation helpers.

.xlsx files - Placeholder/sample datasets for depots, baseline clusters, and monthly demand.

Note: Documentation and structure will be updated once the current overhaul is complete.
