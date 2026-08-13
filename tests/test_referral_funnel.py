import pandas as pd

from f1stewards.referral_funnel import (
    build_referral_episodes,
    extract_car_numbers,
    extract_incident_lap,
    extract_location,
    link_adjudications_to_episodes,
    parse_referral_messages,
    parse_status,
)


def test_race_control_parser_preserves_multi_car_roles() -> None:
    message = (
        "LAP 1 TURN 3 INCIDENT INVOLVING CARS 27 (HUL), 14 (ALO), "
        "81 (PIA) AND 4 (NOR) UNDER INVESTIGATION - CAUSING A COLLISION"
    )

    assert parse_status(message) == "investigation"
    assert extract_car_numbers(message) == (4, 14, 27, 81)
    assert extract_location(message) == "Turn 3"
    assert extract_incident_lap(message) == 1


def test_terminal_status_takes_precedence_over_noted() -> None:
    messages = pd.DataFrame(
        [
            {
                "event_id": "2024-mia",
                "session_type": "Race",
                "message_timestamp": "2024-05-05T20:00:00Z",
                "lap_number": 40,
                "message": "TURN 17 INCIDENT INVOLVING CARS 55 (SAI) AND 81 (PIA) NOTED",
            },
            {
                "event_id": "2024-mia",
                "session_type": "Race",
                "message_timestamp": "2024-05-05T20:03:00Z",
                "lap_number": 43,
                "message": (
                    "TURN 17 INCIDENT INVOLVING CARS 55 (SAI) AND 81 (PIA) "
                    "UNDER INVESTIGATION - CAUSING A COLLISION"
                ),
            },
            {
                "event_id": "2024-mia",
                "session_type": "Race",
                "message_timestamp": "2024-05-05T20:05:00Z",
                "lap_number": 45,
                "message": "5 SECOND TIME PENALTY FOR CAR 55 (SAI) - CAUSING A COLLISION",
            },
        ]
    )

    parsed = parse_referral_messages(messages)
    episodes = build_referral_episodes(parsed)

    assert len(episodes) == 1
    assert episodes.iloc[0]["terminal_status"] == "sanction_announced"
    assert episodes.iloc[0]["car_numbers"] == "55|81"
    assert episodes.iloc[0]["message_count"] == 3


def test_conservative_link_requires_shared_case_evidence() -> None:
    cases = pd.DataFrame(
        [
            {
                "adjudication_instance_id": "adj-1",
                "adjudication_id": "adj-1",
                "incident_id": "incident-1",
                "document_id": "doc-1",
                "event_id": "2024-mia",
                "session_type": "Race",
                "adjudication_car_numbers": "55|81",
                "accused_driver_number": "55",
                "affected_driver_numbers": "81",
                "lap_number": "39",
                "location": "Turn 17",
                "incident_family": "causing_collision",
                "outcome_family": "time_penalty",
            }
        ]
    )
    episodes = pd.DataFrame(
        [
            {
                "referral_episode_id": "referral-1",
                "event_id": "2024-mia",
                "session_type": "Race",
                "car_numbers": "55|81",
                "location": "Turn 17",
                "incident_family": "causing_collision",
                "incident_lap_explicit": 39,
                "terminal_status": "sanction_announced",
            }
        ]
    )

    links = link_adjudications_to_episodes(cases, episodes)

    assert links.iloc[0]["link_status"] == "high_confidence_algorithmic"
    assert links.iloc[0]["link_score"] == 18
    assert "exact_car_set" in links.iloc[0]["link_basis_json"]
