import pandas as pd
import pytest

from f1stewards.close_case_matching import (
    PRIMARY_DISTANCE_FIELDS,
    PRIMARY_EXACT_FIELDS,
    build_neighbor_graph,
    validate_match_fields,
)


def _case(index: int, outcome: bool) -> dict[str, object]:
    return {
        "adjudication_instance_id": f"case-{index}",
        "adjudication_id": f"adj-{index}",
        "incident_id": f"incident-{index}",
        "match_incident_key": f"incident-{index}",
        "incident_family": "causing_collision",
        "session_type": "Race",
        "guideline_regime": "internal_driving_guidelines",
        "attacker_line_candidate": "inside" if index < 5 else "outside",
        "overlap_candidate": "alongside",
        "first_lap_candidate": False,
        "wet_track_candidate": False,
        "safety_car_restart_candidate": False,
        "sanction_outcome": outcome,
        "outcome_family": "time_penalty" if outcome else "no_further_action",
        "penalty_seconds": 5 if outcome else "",
        "penalty_points": 1 if outcome else "",
        "grid_places": "",
    }


def test_primary_match_fields_reject_outcome_leakage() -> None:
    validate_match_fields(PRIMARY_EXACT_FIELDS, PRIMARY_DISTANCE_FIELDS)
    with pytest.raises(ValueError, match="post-decision"):
        validate_match_fields(PRIMARY_EXACT_FIELDS, ["penalty_seconds"])
    with pytest.raises(ValueError, match="post-decision"):
        validate_match_fields(PRIMARY_EXACT_FIELDS, ["fault_language"])


def test_neighbor_selection_does_not_change_when_outcomes_change() -> None:
    cases = pd.DataFrame([_case(index, index % 2 == 0) for index in range(8)])
    first = build_neighbor_graph(cases, minimum_neighbors=3)
    flipped = cases.copy()
    flipped["sanction_outcome"] = ~flipped["sanction_outcome"]
    flipped["outcome_family"] = "grid_penalty"
    flipped["penalty_seconds"] = 99
    second = build_neighbor_graph(flipped, minimum_neighbors=3)

    keys = [
        "adjudication_instance_id",
        "neighbor_rank",
        "neighbor_adjudication_instance_id",
        "distance",
    ]
    pd.testing.assert_frame_equal(first[keys], second[keys])
