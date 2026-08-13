from pathlib import Path

import duckdb
import pandas as pd

from f1stewards.analysis_features import (
    ADJUDICATION_REQUIRED_COLUMNS,
    assemble_analysis_features,
    replace_analysis_feature_build,
)
from f1stewards.coding_queue import (
    FINAL_DOCUMENT_FIELDS,
    FINAL_EXCLUSION_QA_FIELDS,
)
from f1stewards.config import load_study_events
from f1stewards.nationality import (
    load_driver_nationality_registry,
    load_event_country_crosswalk,
    replace_nationality_registries,
)
from f1stewards.warehouse import initialize_database, upsert_study_events


def _frame(columns: set[str] | list[str], row: dict[str, str]) -> pd.DataFrame:
    ordered = sorted(columns) if isinstance(columns, set) else columns
    return pd.DataFrame([{column: row.get(column, "") for column in ordered}])


def _database(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    path = tmp_path / "features.duckdb"
    initialize_database(path)
    connection = duckdb.connect(str(path))
    upsert_study_events(connection, load_study_events())
    replace_nationality_registries(
        connection,
        load_driver_nationality_registry(),
        load_event_country_crosswalk(),
    )
    connection.execute(
        """
        INSERT INTO raw.fastf1_session_results (
            event_id,
            session_type,
            driver_number,
            driver_name,
            abbreviation,
            country_code,
            retrieved_at
        ) VALUES
            ('2019-gbr', 'Race', 44, 'Lewis Hamilton', 'HAM', 'GBR', now()),
            ('2019-gbr', 'Race', 33, 'Max Verstappen', 'VER', 'NED', now())
        """
    )
    connection.execute(
        """
        INSERT INTO curated.stewards (steward_id, full_name) VALUES
            ('steward-1', 'Steward One'),
            ('steward-2', 'Steward Two'),
            ('steward-3', 'Steward Three'),
            ('steward-4', 'Steward Four');
        INSERT INTO curated.panels (
            panel_id, event_id, panel_size, panel_source_document_id
        ) VALUES ('panel-test', '2019-gbr', 4, 'doc-1');
        INSERT INTO curated.panel_members (
            panel_id, steward_id, member_sequence
        ) VALUES
            ('panel-test', 'steward-1', 1),
            ('panel-test', 'steward-2', 2),
            ('panel-test', 'steward-3', 3),
            ('panel-test', 'steward-4', 4);
        INSERT INTO curated.document_panels VALUES (
            'doc-1', '2019-gbr', 'panel-test', 'document_signature_exact',
            'exact', 4, 'Steward One | Steward Two | Steward Three | Steward Four',
            'test-parser-v1'
        );
        """
    )
    return connection


def _adjudication_row() -> dict[str, str]:
    return {
        "adjudication_instance_id": "seed-1-01",
        "adjudication_seed_id": "seed-1",
        "document_id": "doc-1",
        "source_url": "https://www.fia.com/doc-1.pdf",
        "event_id": "2019-gbr",
        "season": "2019",
        "round_number": "10",
        "event_name": "British Grand Prix",
        "event_date": "2019-07-14",
        "guideline_regime": "pre_driving_guidelines",
        "eligibility_suggestion": "primary_candidate",
        "session_type_suggestion": "Race",
        "offence_family_suggestion": "causing_collision",
        "outcome_family_suggestion": "time_penalty",
        "driver_number_suggestion": "44",
        "driver_number_basis_suggestion": "parsed_decision_heading",
        "affected_driver_numbers_suggestion": "33",
        "multi_party_suggestion": "False",
        "penalty_seconds_suggestion": "10",
        "penalty_points_suggestion": "2",
        "grid_places_suggestion": "",
        "parser_review_required": "False",
        "timing_session_loaded": "True",
        "accused_driver_result_present_suggestion": "True",
    }


def _inputs(
    *, final: bool = False
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    adjudication = _adjudication_row()
    document: dict[str, str] = {}
    qa: dict[str, str] = {}
    if final:
        adjudication.update(
            {
                "adjudication_id_final": "adj-1",
                "incident_id_final": "incident-1",
                "accused_driver_number_final": "44",
                "affected_driver_numbers_final": "33",
                "session_type_final": "Race",
                "incident_family_final": "causing_collision",
                "outcome_family_final": "no_further_action",
                "penalty_seconds_final": "",
                "penalty_points_final": "",
                "grid_places_final": "",
                "fault_language_final": "no_conclusion",
                "include_primary_final": "true",
                "include_secondary_final": "false",
                "coder_id": "coder-1",
                "review_status": "adjudicated",
            }
        )
        document.update(
            {
                "version_status_final": "effective",
                "session_scope_final": "primary",
                "offence_family_final": "causing_collision",
                "eligibility_final": "include",
                "reviewer_id": "reviewer-1",
                "review_status": "adjudicated",
            }
        )
        qa.update(
            {
                "qa_disposition": "confirmed_exclusion",
                "reviewer_id": "reviewer-1",
                "review_status": "adjudicated",
            }
        )
    return (
        _frame(FINAL_DOCUMENT_FIELDS, document),
        _frame(ADJUDICATION_REQUIRED_COLUMNS, adjudication),
        _frame(FINAL_EXCLUSION_QA_FIELDS, qa),
        pd.DataFrame([{"control": "workspace", "status": "pass", "detail": "ok"}]),
    )


def test_provisional_features_preserve_driver_roles_and_block_reporting(
    tmp_path: Path,
) -> None:
    connection = _database(tmp_path)
    try:
        documents, adjudications, qa, validation = _inputs()
        build = assemble_analysis_features(
            connection,
            documents,
            adjudications,
            qa,
            workspace_id="workspace-test",
            workspace_input_sha256="a" * 64,
            workspace_validation=validation,
        )
    finally:
        connection.close()

    feature = build.features.iloc[0]
    assert build.release_status == "blocked_pending_human_review"
    assert feature["feature_label_status"] == "provisional_machine_suggestion"
    assert bool(feature["provisional_design_eligible"])
    assert not bool(feature["reporting_eligible"])
    assert bool(feature["sanction_outcome"])
    assert feature["penalty_seconds"] == 10
    assert feature["accused_driver_id"] == "ham"
    assert bool(feature["british_accused_driver"])
    assert bool(feature["home_race_accused"])
    assert feature["principal_affected_driver_id"] == "ver"
    assert feature["panel_id"] == "panel-test"
    assert feature["panel_assignment_basis"] == "document_signature_exact"
    assert feature["panel_signature_parse_status"] == "exact"
    assert feature["panel_size"] == 4
    assert bool(feature["panel_context_complete"])
    assert feature["panel_data_status"] == "source_observed"
    assert len(build.driver_roles) == 2


def test_reviewed_features_use_final_outcome_and_materialize_release(
    tmp_path: Path,
) -> None:
    connection = _database(tmp_path)
    try:
        documents, adjudications, qa, validation = _inputs(final=True)
        build = assemble_analysis_features(
            connection,
            documents,
            adjudications,
            qa,
            workspace_id="workspace-final",
            workspace_input_sha256="b" * 64,
            workspace_validation=validation,
        )
        replace_analysis_feature_build(connection, build)
        stored = connection.sql(
            """
            SELECT outcome_family, sanction_outcome, penalty_seconds, reporting_eligible,
                   panel_id, panel_context_complete
            FROM analysis.v_latest_adjudication_features
            """
        ).fetchone()
    finally:
        connection.close()

    assert build.release_status == "reportable_human_reviewed"
    assert build.controls["status"].eq("pass").all()
    assert stored == ("no_further_action", False, None, True, "panel-test", True)


def test_panel_provenance_changes_build_identity_and_missing_context_blocks_release(
    tmp_path: Path,
) -> None:
    connection = _database(tmp_path)
    try:
        documents, adjudications, qa, validation = _inputs(final=True)
        exact = assemble_analysis_features(
            connection,
            documents,
            adjudications,
            qa,
            workspace_id="workspace-panel-lineage",
            workspace_input_sha256="c" * 64,
            workspace_validation=validation,
        )
        connection.execute(
            """
            UPDATE curated.document_panels
            SET assignment_basis = 'single_event_panel_consensus',
                signature_parse_status = 'event_consensus',
                extracted_member_count = 0,
                raw_signature_lines = NULL
            WHERE document_id = 'doc-1'
            """
        )
        consensus = assemble_analysis_features(
            connection,
            documents,
            adjudications,
            qa,
            workspace_id="workspace-panel-lineage",
            workspace_input_sha256="c" * 64,
            workspace_validation=validation,
        )
        connection.execute("DELETE FROM curated.document_panels WHERE document_id = 'doc-1'")
        missing = assemble_analysis_features(
            connection,
            documents,
            adjudications,
            qa,
            workspace_id="workspace-panel-lineage",
            workspace_input_sha256="c" * 64,
            workspace_validation=validation,
        )
    finally:
        connection.close()

    assert exact.feature_build_id != consensus.feature_build_id
    assert consensus.features.iloc[0]["panel_data_status"] == "derived"
    assert consensus.features.iloc[0]["panel_assignment_basis"] == (
        "single_event_panel_consensus"
    )
    assert missing.features.iloc[0]["panel_data_status"] == "unavailable"
    assert not bool(missing.features.iloc[0]["panel_context_complete"])
    panel_control = missing.controls.set_index("control").loc[
        "selected_candidate_panel_identity_complete"
    ]
    assert panel_control["status"] == "fail"
    assert missing.release_status == "blocked_pending_human_review"
    assert not bool(missing.features.iloc[0]["reporting_eligible"])
