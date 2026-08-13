from __future__ import annotations

import pandas as pd
import pytest

from f1stewards.steward_country import (
    load_steward_country_evidence,
    replace_steward_country_evidence,
    steward_country_evidence_audit,
)
from f1stewards.steward_panels import (
    build_steward_panel_frames,
    load_steward_name_aliases,
    replace_steward_panel_frames,
)
from f1stewards.warehouse import connect, initialize_database


def test_country_evidence_preserves_dated_source_conflicts() -> None:
    evidence = load_steward_country_evidence()

    assert len(evidence) == 92
    assert evidence["steward_id"].nunique() == 82
    loic = evidence.loc[evidence["steward_id"].eq("loic_bacquelaine")]
    assert set(loic["analysis_country_code"]) == {"BEL", "LUX"}
    assert loic["observed_date"].nunique() >= 3


def test_country_evidence_rejects_unknown_steward(tmp_path) -> None:
    evidence = pd.read_csv("config/steward_country_evidence.csv", dtype=str)
    evidence.loc[0, "steward_id"] = "unknown_steward"
    path = tmp_path / "invalid_country_evidence.csv"
    evidence.to_csv(path, index=False)

    with pytest.raises(ValueError, match="Unknown steward_id"):
        load_steward_country_evidence(path)


def test_country_evidence_audit_blocks_incomplete_and_conflicting_release(tmp_path) -> None:
    db_path = tmp_path / "country-evidence.duckdb"
    initialize_database(db_path)
    aliases = load_steward_name_aliases()
    population = pd.DataFrame(
        [
            {
                "document_id": "document-1",
                "event_id": "event-1",
                "raw_text": """
                    Decision text.
                    Garry Connelly Loïc Bacquelaine
                    Derek Warwick Mathieu Remmerie
                """,
            }
        ]
    )
    panels = build_steward_panel_frames(population, aliases)
    evidence = load_steward_country_evidence()

    with connect(db_path) as connection:
        replace_steward_panel_frames(connection, panels)
        assert replace_steward_country_evidence(connection, evidence) == 92
        controls = steward_country_evidence_audit(connection)
        conflict = connection.sql(
            """
            SELECT observed_analysis_codes, resolution_status
            FROM analysis.v_steward_country_evidence_summary
            WHERE steward_id = 'loic_bacquelaine'
            """
        ).fetchone()

    assert controls.loc[
        controls["control"].eq("country_evidence_nonempty"), "status"
    ].item() == "pass"
    assert controls.loc[
        controls["control"].eq("no_unresolved_country_code_conflicts"), "status"
    ].item() == "fail"
    assert controls.loc[
        controls["control"].eq("steward_country_analysis_release"), "status"
    ].item() == "fail"
    assert conflict == ("BEL | LUX", "source_conflict_unresolved")


def test_direct_code_worklist_prioritizes_exposed_derived_only_identity(tmp_path) -> None:
    db_path = tmp_path / "direct-code-worklist.duckdb"
    initialize_database(db_path)
    aliases = load_steward_name_aliases()
    population = pd.DataFrame(
        [
            {
                "document_id": "document-1",
                "event_id": "event-1",
                "raw_text": """
                    Decision text.
                    Garry Connelly Matteo Perini
                    Derek Warwick Mathieu Remmerie
                """,
            }
        ]
    )
    panels = build_steward_panel_frames(population, aliases)

    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO metadata.events (
                event_id,
                season,
                round_number,
                event_name,
                country,
                event_date,
                archive_url,
                guideline_regime,
                is_pilot
            ) VALUES (
                'event-1',
                2024,
                1,
                'Fixture Grand Prix',
                'Fixture',
                DATE '2024-01-01',
                'https://example.test/event',
                'fixture',
                FALSE
            )
            """
        )
        replace_steward_panel_frames(connection, panels)
        replace_steward_country_evidence(connection, load_steward_country_evidence())
        summary = connection.sql(
            """
            SELECT direct_code_records, direct_code_status
            FROM analysis.v_steward_country_evidence_summary
            WHERE steward_id = 'matteo_perini'
            """
        ).fetchone()
        worklist = connection.sql(
            """
            SELECT steward_id, decision_document_count
            FROM analysis.v_steward_direct_code_research_worklist
            """
        ).fetchall()

    assert summary == (0, "no_direct_code_evidence")
    assert worklist == [("matteo_perini", 1)]
