import pandas as pd

from f1stewards.damage_screening import (
    build_incident_participants,
    map_utc_window_to_participant_laps,
    summarize_participant_timing,
)


def test_multi_document_collision_becomes_one_participant_set() -> None:
    links = pd.DataFrame(
        [
            {
                "adjudication_instance_id": "a",
                "adjudication_id": "a",
                "incident_id": "i-a",
                "document_id": "d-a",
                "event_id": "2019-bhr",
                "session_type": "Race",
                "adjudication_car_numbers": "33|55",
                "accused_driver_number": "33",
                "affected_driver_numbers": "55",
                "incident_family": "causing_collision",
                "outcome_family": "no_further_action",
                "referral_episode_id": "referral-shared",
                "link_status": "high_confidence_algorithmic",
            },
            {
                "adjudication_instance_id": "b",
                "adjudication_id": "b",
                "incident_id": "i-b",
                "document_id": "d-b",
                "event_id": "2019-bhr",
                "session_type": "Race",
                "adjudication_car_numbers": "33|55",
                "accused_driver_number": "55",
                "affected_driver_numbers": "33",
                "incident_family": "causing_collision",
                "outcome_family": "no_further_action",
                "referral_episode_id": "referral-shared",
                "link_status": "high_confidence_algorithmic",
            },
        ]
    )
    context = pd.DataFrame(
        [
            {
                "adjudication_instance_id": "a",
                "incident_lap_candidate": 4,
                "incident_lap_basis": "source",
                "first_lap_candidate": False,
                "clock_lower_utc": "2019-03-31T15:00:00Z",
                "clock_upper_utc": "2019-03-31T15:01:00Z",
            },
            {
                "adjudication_instance_id": "b",
                "incident_lap_candidate": 4,
                "incident_lap_basis": "source",
                "first_lap_candidate": False,
                "clock_lower_utc": "2019-03-31T15:00:00Z",
                "clock_upper_utc": "2019-03-31T15:01:00Z",
            },
        ]
    )

    participants = build_incident_participants(links, context)

    assert len(participants) == 2
    assert set(participants["participant_driver_number"]) == {33, 55}
    assert set(participants["participant_role"]) == {"accused_and_affected"}
    assert participants["canonical_incident_key"].nunique() == 1


def test_timing_screen_requires_clean_reference_laps() -> None:
    laps = pd.DataFrame(
        {
            "lap_number": list(range(2, 14)),
            "lap_time_seconds": [90.0] * 12,
            "track_status": ["1"] * 12,
            "is_accurate": [True] * 12,
            "pit_in_time_seconds": [None] * 12,
            "pit_out_time_seconds": [None] * 12,
            "position": [5.0] * 12,
        }
    )
    teammate = laps.copy()
    summary = summarize_participant_timing(laps, 7, teammate)

    assert summary["clean_laps_before"] == 5
    assert summary["clean_laps_after"] == 6
    assert summary["persistent_pace_primary_eligible"] is True

    teammate.loc[teammate["lap_number"].gt(7), "track_status"] = "4"
    insufficient = summarize_participant_timing(laps, 7, teammate)
    assert insufficient["persistent_pace_primary_eligible"] is False


def test_participant_clock_mapping_preserves_two_lap_window() -> None:
    laps = pd.DataFrame(
        {
            "lap_number": [1, 2],
            "lap_start_timestamp": ["2024-05-05T13:00:00Z", "2024-05-05T13:01:30Z"],
            "lap_time_seconds": [90.0, 90.0],
        }
    )

    mapped = map_utc_window_to_participant_laps(
        laps, "2024-05-05T13:01:00Z", "2024-05-05T13:02:00Z"
    )

    assert mapped == (1, 2)
