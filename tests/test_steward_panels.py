from __future__ import annotations

import pandas as pd

from f1stewards.steward_panels import (
    build_steward_panel_frames,
    load_steward_name_aliases,
    parse_steward_signature,
    replace_steward_panel_frames,
    steward_panel_audit,
)
from f1stewards.warehouse import connect, initialize_database

FOUR_MEMBER_SIGNATURE = """
Decision text.
Garry Connelly Mathieu Remmerie
Derek Warwick Mohammed Al Hashmi
"""

FIVE_MEMBER_SIGNATURE = """
Decision text.
Gerd Ennser Loïc Bacquelaine
Natalie Corsmit Derek Warwick
Paul Ng
"""

ALTERNATE_PANEL_SIGNATURE = """
Decision text.
Garry Connelly Mathieu Remmerie
Derek Warwick Jose Abed
"""


def test_alias_registry_is_complete_and_canonical() -> None:
    aliases = load_steward_name_aliases()

    canonical = aliases.loc[aliases["alias_status"].eq("canonical")]
    assert len(canonical) == aliases["steward_id"].nunique()
    assert len(canonical) >= 80
    assert aliases["observed_name"].is_unique


def test_signature_parser_handles_four_and_five_member_panels() -> None:
    aliases = load_steward_name_aliases()

    four = parse_steward_signature(FOUR_MEMBER_SIGNATURE, aliases)
    five = parse_steward_signature(FIVE_MEMBER_SIGNATURE, aliases)

    assert four is not None
    assert set(four.steward_ids) == {
        "garry_connelly",
        "mathieu_remmerie",
        "derek_warwick",
        "mohammed_al_hashmi",
    }
    assert five is not None
    assert set(five.steward_ids) == {
        "gerd_ennser",
        "loic_bacquelaine",
        "natalie_corsmit",
        "derek_warwick",
        "paul_ng",
    }


def test_build_preserves_substitutions_and_limits_consensus_to_one_panel_events() -> None:
    aliases = load_steward_name_aliases()
    population = pd.DataFrame(
        [
            {
                "document_id": "single-exact",
                "event_id": "2025-single-event",
                "raw_text": FOUR_MEMBER_SIGNATURE,
            },
            {
                "document_id": "single-unreadable",
                "event_id": "2025-single-event",
                "raw_text": "No readable signature",
            },
            {
                "document_id": "multi-first",
                "event_id": "2025-multi-event-with-hyphens",
                "raw_text": FOUR_MEMBER_SIGNATURE,
            },
            {
                "document_id": "multi-second",
                "event_id": "2025-multi-event-with-hyphens",
                "raw_text": ALTERNATE_PANEL_SIGNATURE,
            },
            {
                "document_id": "multi-unreadable",
                "event_id": "2025-multi-event-with-hyphens",
                "raw_text": "No readable signature",
            },
        ]
    )

    frames = build_steward_panel_frames(population, aliases)
    assignments = frames.document_panels.set_index("document_id")

    assert len(frames.panels) == 3
    assert set(frames.panels["event_id"]) == {
        "2025-single-event",
        "2025-multi-event-with-hyphens",
    }
    assert assignments.loc["single-unreadable", "assignment_basis"] == (
        "single_event_panel_consensus"
    )
    assert assignments.loc["single-unreadable", "panel_id"] == assignments.loc[
        "single-exact", "panel_id"
    ]
    assert assignments.loc["multi-unreadable", "assignment_basis"] == "unresolved"
    assert pd.isna(assignments.loc["multi-unreadable", "panel_id"])


def test_panel_identity_is_order_invariant() -> None:
    aliases = load_steward_name_aliases()
    reordered = """
    Decision text.
    Mohammed Al Hashmi Derek Warwick
    Mathieu Remmerie Garry Connelly
    """
    population = pd.DataFrame(
        [
            {"document_id": "first", "event_id": "event-1", "raw_text": FOUR_MEMBER_SIGNATURE},
            {"document_id": "second", "event_id": "event-1", "raw_text": reordered},
        ]
    )

    frames = build_steward_panel_frames(population, aliases)

    assert len(frames.panels) == 1
    assert frames.document_panels["panel_id"].nunique() == 1


def test_replacement_preserves_sourced_steward_nationality(tmp_path) -> None:
    db_path = tmp_path / "stewards.duckdb"
    initialize_database(db_path)
    aliases = load_steward_name_aliases()
    population = pd.DataFrame(
        [
            {
                "document_id": "document-1",
                "event_id": "event-1",
                "raw_text": FOUR_MEMBER_SIGNATURE,
            },
            {
                "document_id": "document-2",
                "event_id": "event-1",
                "raw_text": ALTERNATE_PANEL_SIGNATURE,
            },
        ]
    )
    frames = build_steward_panel_frames(population, aliases)

    with connect(db_path) as connection:
        replace_steward_panel_frames(connection, frames)
        connection.execute(
            """
            UPDATE curated.stewards
            SET nationality = 'British', nationality_source_url = 'https://example.test/source'
            WHERE steward_id = 'derek_warwick'
            """
        )
        replace_steward_panel_frames(connection, frames)
        nationality = connection.sql(
            """
            SELECT nationality, nationality_source_url
            FROM curated.stewards
            WHERE steward_id = 'derek_warwick'
            """
        ).fetchone()
        controls = steward_panel_audit(connection)

    assert nationality == ("British", "https://example.test/source")
    extraction = controls.loc[controls["gate_type"].eq("extraction")]
    assert extraction["status"].eq("pass").all()
    release = controls.loc[controls["gate_type"].eq("analysis_release")]
    assert release["status"].eq("fail").all()
