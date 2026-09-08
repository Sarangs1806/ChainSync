from core import Scenario, demand_months, load_data, run_scenario
from prompting import interpret_prompt


def test_data_and_baseline_scenario_load():
    demand, depots, baseline = load_data()
    month = demand_months(demand)[0]
    result = run_scenario(demand, depots, baseline, Scenario(month, tuple(depots["Depot Name"])))
    assert len(result.assignments) == len(demand)
    assert set(result.depot_summary["depot"]) == set(depots["Depot Name"])


def test_prompt_interprets_known_depot_and_month():
    demand, depots, _ = load_data()
    answer = interpret_prompt("Close CSK in August", depots["Depot Name"].tolist(), demand_months(demand))
    assert answer.kind == "scenario"
    assert answer.month == "Demand August"
    assert "CRO South Kozhikode (CSK)" in answer.inactive_depots


def test_irrelevant_prompt_is_declined():
    answer = interpret_prompt("Who won the cricket match?", ["Example Depot (EDP)"], ["Demand January"])
    assert answer.kind == "unsupported"
