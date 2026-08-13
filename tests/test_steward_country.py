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

    assert len(evidence) == 45
    assert evidence["steward_id"].nunique() == 38
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
        assert replace_steward_country_evidence(connection, evidence) == 45
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
