# Model Rules and Evidence Register

## Purpose and boundary

This document explains the assumptions used by the **PDS Supply Chain Resilience Platform**. It is project documentation, not an official operating procedure, legal interpretation, or approval to change a real distribution network. A human planner must review every result.

The supplied workbooks provide the model's data. The public sources below provide PDS context only; they do **not** define the numerical optimization thresholds in this prototype.

## Data lineage

| Workbook | Role in the model | Key fields used |
|---|---|---|
| `monthly_demand.xlsx` | Shop-level demand and geospatial input | ID, Latitude, Longitude, Demand January–December |
| `depots.xlsx` | Available depot locations and capacity | Depot Name, Latitude, Longitude, Capacity(kg) |
| `baseline_clusters.xlsx` | Original allocation and paired-shop reference | Shop ID, Paired With, Depot |

## Project rules implemented in code

| Rule | Configured value | Reason and scope |
|---|---:|---|
| Initial allocation | Nearest active depot | Establishes a transparent geographic baseline. |
| Alternate-depot distance | At most 25 km | Prototype feasibility threshold inherited from the supplied model logic. |
| Extra distance versus source depot | At most 8 km | Prevents a reassignment that materially worsens local access. |
| Receiving-depot tolerance | At most 110% of nominal capacity | Prototype emergency-planning tolerance; requires human capacity approval in real use. |
| Paired-shop demand limit | 12,000 kg | A pair is marked valid when combined selected-month demand is within this value. |
| Assignment objective | Relieve overload with the closest feasible alternate | This is a deterministic greedy heuristic, not a globally optimal mixed-integer solution. |
| Distance measurement | Local latitude/longitude approximation | Suitable for relative planning comparison; not actual road distance or route time. |

## Scenario acceptance rules

The prompt interface supports PDS logistics queries only. A request must specify:

1. A supported action such as **close**, **deactivate**, or **outage**;
2. An existing depot name or abbreviation, for example `CSK`;
3. A month that exists in the demand workbook.

If a prompt is ambiguous, refers to an unknown depot, or is unrelated to PDS planning, the application asks for clarification or declines it. It does not invent data or run an arbitrary scenario.

## Interpretation rules

- **Within capacity** means modeled demand is at or below nominal capacity.
- **Capacity exception** means modeled demand exceeds nominal capacity. It is visible even if it remains below the 110% prototype tolerance.
- **Reassigned from baseline** means the simulated assignment differs from the depot in `baseline_clusters.xlsx`; it does not necessarily mean that a user explicitly caused that move.
- **Total allocation distance** is the sum of straight-line approximations between assigned depots and shops. It is not a vehicle-routing distance, fuel cost, or travel time.

## Public context sources

1. Government of Kerala AePDS portal: it exposes operationally relevant report categories such as FPS stock register, transactions, and shop status. This supports the general relevance of data-based PDS monitoring, but is not used to modify project outputs. <https://epos.kerala.gov.in/>
2. Government of India, Department of Food and Public Distribution: describes reforms including end-to-end computerisation, transparent transaction recording, and improvements to fair-price-shop operations. <https://dfpd.gov.in/faqs/en>
3. Kerala Civil Supplies, *Kerala Targeted Public Distribution System (Control) Order, 2021* page: an official entry point for state rules. This prototype does not claim compliance with that order. <https://civilsupplieskerala.gov.in/index.php/content/index/acts-and-rules>

## Known limitations and next improvements

- Replace straight-line distance with road-network distance and vehicle routes.
- Add a global optimization model, such as MILP, to compare the heuristic against an optimal solution.
- Add actual operating costs, fleet capacity, delivery windows, and stock-on-hand.
- Validate all thresholds with authorized operations stakeholders before using the model for real decisions.
- Add document retrieval only when approved documents are available; cite them separately from model assumptions.
