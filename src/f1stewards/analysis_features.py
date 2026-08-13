"""Gated, role-preserving analytical features from the full-corpus coding workspace."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from f1stewards.coding_queue import (
    FINAL_ADJUDICATION_FIELDS,
    FINAL_DOCUMENT_FIELDS,
    FINAL_EXCLUSION_QA_FIELDS,
)
from f1stewards.coding_workspace import (
    WORKSPACE_ADJUDICATION_FILENAME,
    WORKSPACE_DOCUMENT_FILENAME,
    WORKSPACE_EXCLUSION_QA_FILENAME,
    WORKSPACE_MANIFEST_FILENAME,
    load_timing_review_context,
    validate_edited_full_corpus_coding_workspace,
)

FEATURE_SCHEMA_VERSION = "adjudication-analysis-features-v2"
COMPLETE_REVIEW_STATUSES = {"double_coded", "adjudicated"}
SANCTION_OUTCOMES = {
    "warning",
    "reprimand",
    "black_white_flag",
    "fine",
    "time_penalty",
    "drive_through",
    "stop_go",
    "grid_penalty",
    "disqualification",
}
NON_SANCTION_OUTCOMES = {"no_further_action"}
MODEL_OUTCOMES = SANCTION_OUTCOMES | NON_SANCTION_OUTCOMES
INTERPRETATION_BOUNDARY = (
    "Machine suggestions may be used for pipeline and overlap diagnostics only. Reporting and "
    "inference remain blocked until the denominator, inclusions, exclusions, and QA sample are "
    "independently reviewed and every release control passes."
)

ADJUDICATION_REQUIRED_COLUMNS = {
    "adjudication_instance_id",
    "adjudication_seed_id",
    "document_id",
    "source_url",
    "event_id",
    "season",
    "round_number",
    "event_name",
    "event_date",
    "guideline_regime",
    "eligibility_suggestion",
    "session_type_suggestion",
    "offence_family_suggestion",
    "outcome_family_suggestion",
    "driver_number_suggestion",
    "driver_number_basis_suggestion",
    "affected_driver_numbers_suggestion",
    "multi_party_suggestion",
    "penalty_seconds_suggestion",
    "penalty_points_suggestion",
    "grid_places_suggestion",
    "parser_review_required",
    "timing_session_loaded",
    "accused_driver_result_present_suggestion",
    *FINAL_ADJUDICATION_FIELDS,
}


@dataclass(frozen=True)
class AnalysisFeatureBuild:
    feature_build_id: str
    workspace_id: str
    workspace_input_sha256: str
    nationality_registry_sha256: str
    panel_assignments_sha256: str
    built_at_utc: datetime
    release_status: str
    features: pd.DataFrame
    driver_roles: pd.DataFrame
    controls: pd.DataFrame


def _canonical_csv(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, lineterminator="\n").encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _clean(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _bool(value: Any) -> bool:
    return _clean(value).casefold() == "true"


def _integer(value: Any) -> int | None:
    cleaned = _clean(value)
    if not cleaned:
        return None
    number = float(cleaned)
    return int(number) if number.is_integer() else None


def _number(value: Any) -> float | None:
    cleaned = _clean(value)
    return float(cleaned) if cleaned else None


def _pipe_numbers(value: Any) -> list[int]:
    numbers: list[int] = []
    for item in _clean(value).split("|"):
        number = _integer(item)
        if number is not None and number not in numbers:
            numbers.append(number)
    return numbers


def _review_complete(value: Any) -> bool:
    return _clean(value) in COMPLETE_REVIEW_STATUSES


def _adjudication_final_complete(row: pd.Series) -> bool:
    if not _review_complete(row["review_status"]):
        return False
    primary = _clean(row["include_primary_final"]).casefold()
    secondary = _clean(row["include_secondary_final"]).casefold()
    if primary not in {"true", "false"} or secondary not in {"true", "false"}:
        return False
    if primary == "true" and secondary == "true":
        return False
    if primary == "true" or secondary == "true":
        required = (
            "adjudication_id_final",
            "incident_id_final",
            "accused_driver_number_final",
            "session_type_final",
            "incident_family_final",
            "outcome_family_final",
            "fault_language_final",
            "coder_id",
        )
        if not all(_clean(row[column]) for column in required):
            return False
        outcome = _clean(row["outcome_family_final"])
        if outcome == "time_penalty" and not _clean(row["penalty_seconds_final"]):
            return False
        return not (outcome == "grid_penalty" and not _clean(row["grid_places_final"]))
    return bool(_clean(row["exclusion_reason_final"]) and _clean(row["coder_id"]))


def _document_final_complete(row: pd.Series) -> bool:
    if not _review_complete(row["review_status"]):
        return False
    required = ("version_status_final", "eligibility_final", "reviewer_id")
    if not all(_clean(row[column]) for column in required):
        return False
    if "excl" in _clean(row["eligibility_final"]).casefold():
        return bool(_clean(row["exclusion_reason_final"]))
    return bool(
        _clean(row["session_scope_final"]) and _clean(row["offence_family_final"])
    )


def _qa_final_complete(row: pd.Series) -> bool:
    return bool(
        _review_complete(row["review_status"])
        and _clean(row["qa_disposition"])
        and _clean(row["reviewer_id"])
    )


def _validate_input_columns(
    documents: pd.DataFrame,
    adjudications: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
) -> None:
    missing_adjudications = ADJUDICATION_REQUIRED_COLUMNS - set(adjudications.columns)
    missing_documents = set(FINAL_DOCUMENT_FIELDS) - set(documents.columns)
    missing_qa = set(FINAL_EXCLUSION_QA_FIELDS) - set(exclusion_qa.columns)
    if missing_adjudications or missing_documents or missing_qa:
        raise ValueError(
            "Analysis feature inputs are missing required columns: "
            f"adjudications={sorted(missing_adjudications)}, "
            f"documents={sorted(missing_documents)}, qa={sorted(missing_qa)}"
        )
    if adjudications["adjudication_instance_id"].duplicated().any():
        raise ValueError("adjudication_instance_id must be unique before feature assembly")


def _identity_frame(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return connection.sql(
        """
        SELECT
            event_id,
            session_type,
            driver_number,
            driver_id,
            registry_driver_name AS driver_name,
            abbreviation,
            registry_f1_country_code AS f1_country_code,
            nationality,
            is_british,
            home_race_driver,
            nationality_match_status
        FROM analysis.v_fastf1_driver_identity
        ORDER BY event_id, session_type, driver_number
        """
    ).df()


def _identity_registry_digest(connection: duckdb.DuckDBPyConnection) -> str:
    registry = connection.sql(
        """
        SELECT *
        FROM metadata.driver_nationality_registry
        ORDER BY driver_id
        """
    ).df()
    countries = connection.sql(
        """
        SELECT *
        FROM metadata.event_country_crosswalk
        ORDER BY event_country_label
        """
    ).df()
    if registry.empty or countries.empty:
        raise ValueError("Nationality and event-country registries must be loaded first")
    return _sha256(_canonical_csv(registry) + b"\n" + _canonical_csv(countries))


def _panel_context_frame(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    panels = connection.sql(
        """
        SELECT
            document_id,
            event_id,
            panel_id,
            assignment_basis,
            signature_parse_status,
            extracted_member_count,
            panel_size
        FROM analysis.v_document_panel_composition
        ORDER BY document_id
        """
    ).df()
    if panels["document_id"].duplicated().any():
        raise ValueError("Document-panel context must be unique by document_id")
    return panels


def _panel_context_digest(panels: pd.DataFrame) -> str:
    return _sha256(_canonical_csv(panels))


def _panel_lookup(panels: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {
        str(row.document_id): row._asdict()
        for row in panels.itertuples(index=False)
    }


def _identity_lookup(identities: pd.DataFrame) -> dict[tuple[str, str, int], dict[str, Any]]:
    if identities.duplicated(["event_id", "session_type", "driver_number"]).any():
        raise ValueError("FastF1 identity grain is not unique by event, session, and car number")
    return {
        (str(row.event_id), str(row.session_type), int(row.driver_number)): row._asdict()
        for row in identities.itertuples(index=False)
    }


def _role_payload(
    *,
    feature_build_id: str,
    workspace_id: str,
    instance_id: str,
    event_id: str,
    session_type: str,
    driver_role: str,
    role_sequence: int,
    driver_number: int,
    role_number_basis: str,
    lookup: dict[tuple[str, str, int], dict[str, Any]],
) -> dict[str, Any]:
    identity = lookup.get((event_id, session_type, driver_number))
    return {
        "feature_build_id": feature_build_id,
        "workspace_id": workspace_id,
        "adjudication_instance_id": instance_id,
        "event_id": event_id,
        "session_type": session_type or None,
        "driver_role": driver_role,
        "role_sequence": role_sequence,
        "driver_number": driver_number,
        "driver_id": identity["driver_id"] if identity else None,
        "driver_name": identity["driver_name"] if identity else None,
        "abbreviation": identity["abbreviation"] if identity else None,
        "f1_country_code": identity["f1_country_code"] if identity else None,
        "nationality": identity["nationality"] if identity else None,
        "is_british": identity["is_british"] if identity else None,
        "home_race_driver": identity["home_race_driver"] if identity else None,
        "identity_match_status": (
            f"matched:{identity['nationality_match_status']}"
            if identity
            else "missing_classification_identity"
        ),
        "role_number_basis": role_number_basis,
    }


def _release_controls(
    documents: pd.DataFrame,
    adjudications: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
    workspace_validation: pd.DataFrame,
    features: pd.DataFrame,
) -> pd.DataFrame:
    document_complete = int(documents.apply(_document_final_complete, axis=1).sum())
    adjudication_complete = int(adjudications.apply(_adjudication_final_complete, axis=1).sum())
    qa_complete = int(exclusion_qa.apply(_qa_final_complete, axis=1).sum())
    final_primary = features[features["population_status"].eq("human_reviewed_primary")]
    panel_context_missing = int((~features["panel_context_complete"].astype(bool)).sum())
    identity_missing = int(
        final_primary["accused_identity_match_status"].ne("matched").sum()
    )
    outcome_unmapped = int((~final_primary["outcome_model_eligible"].astype(bool)).sum())
    rows = [
        (
            "workspace_integrity",
            bool(workspace_validation["status"].eq("pass").all()),
            int(workspace_validation["status"].eq("pass").sum()),
            len(workspace_validation),
            "Protected lineage and editable-workspace controls must all pass.",
        ),
        (
            "document_dispositions_complete",
            document_complete == len(documents),
            document_complete,
            len(documents),
            "Every archive outcome label needs an independently reviewed final disposition.",
        ),
        (
            "selected_candidate_panel_identity_complete",
            panel_context_missing == 0,
            panel_context_missing,
            0,
            "Every selected adjudication must join one evidence-based document panel identity.",
        ),
        (
            "adjudication_coding_complete",
            adjudication_complete == len(adjudications),
            adjudication_complete,
            len(adjudications),
            "Every live decision seed needs reviewed inclusion or a controlled exclusion.",
        ),
        (
            "exclusion_qa_complete",
            qa_complete == len(exclusion_qa),
            qa_complete,
            len(exclusion_qa),
            "Every frozen exclusion-QA row needs independent review.",
        ),
        (
            "final_primary_population_nonempty",
            len(final_primary) > 0,
            len(final_primary),
            "> 0",
            "A reviewed primary population is required before outcome modeling.",
        ),
        (
            "final_primary_accused_identity_complete",
            identity_missing == 0,
            identity_missing,
            0,
            "Every reviewed primary adjudication must join one sourced accused-driver identity.",
        ),
        (
            "final_primary_binary_outcome_complete",
            outcome_unmapped == 0,
            outcome_unmapped,
            0,
            "Every modeled final outcome must map to sanction or no further action.",
        ),
    ]
    controls = pd.DataFrame(
        [
            {
                "control_order": order,
                "control": name,
                "status": "pass" if passed else "fail",
                "observed": str(observed),
                "expected": str(expected),
                "detail": detail,
            }
            for order, (name, passed, observed, expected, detail) in enumerate(rows, start=1)
        ]
    )
    release_passed = controls["status"].eq("pass").all()
    controls.loc[len(controls)] = {
        "control_order": len(controls) + 1,
        "control": "analytical_release",
        "status": "pass" if release_passed else "fail",
        "observed": "all prerequisite controls pass" if release_passed else "one or more fail",
        "expected": "all prerequisite controls pass",
        "detail": INTERPRETATION_BOUNDARY,
    }
    return controls


def assemble_analysis_features(
    connection: duckdb.DuckDBPyConnection,
    documents: pd.DataFrame,
    adjudications: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
    *,
    workspace_id: str,
    workspace_input_sha256: str,
    workspace_validation: pd.DataFrame,
) -> AnalysisFeatureBuild:
    """Assemble provisional diagnostics or final reviewed features without mixing labels."""

    _validate_input_columns(documents, adjudications, exclusion_qa)
    identities = _identity_frame(connection)
    identity_lookup = _identity_lookup(identities)
    registry_digest = _identity_registry_digest(connection)
    panels = _panel_context_frame(connection)
    panel_lookup = _panel_lookup(panels)
    panel_digest = _panel_context_digest(panels)
    feature_build_id = "features-" + _sha256(
        (
            FEATURE_SCHEMA_VERSION
            + "\n"
            + workspace_input_sha256
            + "\n"
            + registry_digest
            + "\n"
            + panel_digest
        ).encode("utf-8")
    )[:12]

    any_final = adjudications[FINAL_ADJUDICATION_FIELDS].ne("").any(axis=1)
    final_complete = adjudications.apply(_adjudication_final_complete, axis=1)
    final_primary = adjudications["include_primary_final"].str.casefold().eq("true")
    suggested_primary = adjudications["eligibility_suggestion"].eq("primary_candidate")
    selected = adjudications.loc[suggested_primary | (final_complete & final_primary)].copy()
    selected["_any_final"] = any_final.loc[selected.index]
    selected["_final_complete"] = final_complete.loc[selected.index]
    selected["_final_primary"] = final_primary.loc[selected.index]

    feature_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    for _, row in selected.iterrows():
        is_final_primary = bool(row["_final_complete"] and row["_final_primary"])
        is_final_excluded = bool(row["_final_complete"] and not row["_final_primary"])
        if is_final_primary:
            label_status = "human_reviewed_final"
            population_status = "human_reviewed_primary"
        elif is_final_excluded:
            label_status = "human_reviewed_excluded"
            population_status = "human_reviewed_excluded"
        elif row["_any_final"]:
            label_status = "incomplete_human_coding"
            population_status = "incomplete_human_coding"
        else:
            label_status = "provisional_machine_suggestion"
            population_status = "provisional_primary_candidate"

        use_final = is_final_primary
        session_type = _clean(
            row["session_type_final"] if use_final else row["session_type_suggestion"]
        )
        incident_family = _clean(
            row["incident_family_final"] if use_final else row["offence_family_suggestion"]
        )
        outcome_family = _clean(
            row["outcome_family_final"] if use_final else row["outcome_family_suggestion"]
        )
        accused_number = _integer(
            row["accused_driver_number_final"]
            if use_final
            else row["driver_number_suggestion"]
        )
        affected_numbers = _pipe_numbers(
            row["affected_driver_numbers_final"]
            if use_final
            else row["affected_driver_numbers_suggestion"]
        )
        sanction_outcome = (
            True
            if outcome_family in SANCTION_OUTCOMES
            else False
            if outcome_family in NON_SANCTION_OUTCOMES
            else None
        )
        outcome_model_eligible = outcome_family in MODEL_OUTCOMES
        instance_id = _clean(row["adjudication_instance_id"])
        event_id = _clean(row["event_id"])
        document_id = _clean(row["document_id"])
        panel = panel_lookup.get(document_id)
        if panel and _clean(panel["event_id"]) != event_id:
            raise ValueError(
                "Document-panel event mismatch: "
                f"document_id={document_id}, feature_event={event_id}, "
                f"panel_event={_clean(panel['event_id'])}"
            )
        panel_id = _clean(panel["panel_id"]) if panel else ""
        panel_assignment_basis = _clean(panel["assignment_basis"]) if panel else ""
        panel_signature_status = (
            _clean(panel["signature_parse_status"]) if panel else ""
        )
        panel_size = _integer(panel["panel_size"]) if panel else None
        panel_context_complete = bool(
            panel_id
            and panel_size is not None
            and panel_assignment_basis
            in {"document_signature_exact", "single_event_panel_consensus"}
            and panel_signature_status in {"exact", "event_consensus"}
        )
        panel_data_status = (
            "source_observed"
            if panel_assignment_basis == "document_signature_exact"
            else "derived"
            if panel_assignment_basis == "single_event_panel_consensus"
            else "unavailable"
        )
        accused_role = None
        if accused_number is not None:
            accused_role = _role_payload(
                feature_build_id=feature_build_id,
                workspace_id=workspace_id,
                instance_id=instance_id,
                event_id=event_id,
                session_type=session_type,
                driver_role="accused",
                role_sequence=1,
                driver_number=accused_number,
                role_number_basis=(
                    "human_reviewed_final"
                    if use_final
                    else _clean(row["driver_number_basis_suggestion"])
                ),
                lookup=identity_lookup,
            )
            role_rows.append(accused_role)

        affected_roles = []
        for sequence, number in enumerate(affected_numbers, start=1):
            role = _role_payload(
                feature_build_id=feature_build_id,
                workspace_id=workspace_id,
                instance_id=instance_id,
                event_id=event_id,
                session_type=session_type,
                driver_role="affected",
                role_sequence=sequence,
                driver_number=number,
                role_number_basis=(
                    "human_reviewed_final"
                    if use_final
                    else "machine_extracted_affected_number"
                ),
                lookup=identity_lookup,
            )
            affected_roles.append(role)
            role_rows.append(role)
        affected_complete = all(
            role["identity_match_status"].startswith("matched:") for role in affected_roles
        )
        affected_british: bool | None
        if not affected_roles:
            affected_british = None
        elif any(role["is_british"] is True for role in affected_roles):
            affected_british = True
        elif affected_complete:
            affected_british = False
        else:
            affected_british = None
        principal_affected = (
            affected_roles[0]["driver_id"]
            if len(affected_roles) == 1
            and affected_roles[0]["identity_match_status"].startswith("matched:")
            else None
        )
        accused_match = (
            "matched"
            if accused_role and accused_role["identity_match_status"].startswith("matched:")
            else "missing"
        )
        provisional_eligible = bool(
            label_status == "provisional_machine_suggestion"
            and outcome_model_eligible
            and accused_match == "matched"
        )
        model_eligible = bool(
            label_status == "human_reviewed_final"
            and outcome_model_eligible
            and accused_match == "matched"
        )
        feature_rows.append(
            {
                "feature_build_id": feature_build_id,
                "workspace_id": workspace_id,
                "adjudication_instance_id": instance_id,
                "adjudication_seed_id": _clean(row["adjudication_seed_id"]),
                "adjudication_id": _clean(row["adjudication_id_final"]) or None,
                "incident_id": _clean(row["incident_id_final"]) or None,
                "document_id": document_id,
                "source_url": _clean(row["source_url"]),
                "event_id": event_id,
                "season": _integer(row["season"]),
                "round_number": _integer(row["round_number"]),
                "event_name": _clean(row["event_name"]),
                "event_date": _clean(row["event_date"]) or None,
                "guideline_regime": _clean(row["guideline_regime"]),
                "feature_label_status": label_status,
                "population_status": population_status,
                "review_status": _clean(row["review_status"]) or None,
                "reporting_eligible": False,
                "provisional_design_eligible": provisional_eligible,
                "model_eligible": model_eligible,
                "session_type": session_type or None,
                "incident_family": incident_family or None,
                "outcome_family": outcome_family or None,
                "sanction_outcome": sanction_outcome,
                "outcome_model_eligible": outcome_model_eligible,
                "penalty_seconds": _number(
                    row["penalty_seconds_final"]
                    if use_final
                    else row["penalty_seconds_suggestion"]
                ),
                "penalty_points": _integer(
                    row["penalty_points_final"]
                    if use_final
                    else row["penalty_points_suggestion"]
                ),
                "grid_places": _integer(
                    row["grid_places_final"]
                    if use_final
                    else row["grid_places_suggestion"]
                ),
                "fault_language": (
                    _clean(row["fault_language_final"]) or None if use_final else None
                ),
                "accused_driver_number": accused_number,
                "accused_driver_id": accused_role["driver_id"] if accused_role else None,
                "accused_driver_name": accused_role["driver_name"] if accused_role else None,
                "accused_driver_abbreviation": (
                    accused_role["abbreviation"] if accused_role else None
                ),
                "accused_f1_country_code": (
                    accused_role["f1_country_code"] if accused_role else None
                ),
                "accused_nationality": accused_role["nationality"] if accused_role else None,
                "british_accused_driver": accused_role["is_british"] if accused_role else None,
                "home_race_accused": (
                    accused_role["home_race_driver"] if accused_role else None
                ),
                "accused_identity_match_status": accused_match,
                "affected_driver_count": len(affected_roles),
                "principal_affected_driver_id": principal_affected,
                "british_affected_driver": affected_british,
                "affected_identity_complete": affected_complete,
                "multi_party": bool(
                    len(affected_roles) > 1
                    or (not use_final and _bool(row["multi_party_suggestion"]))
                ),
                "parser_review_required": _bool(row["parser_review_required"]),
                "timing_session_loaded": _bool(row["timing_session_loaded"]),
                "accused_driver_result_present": _bool(
                    row["accused_driver_result_present_suggestion"]
                ),
                "panel_id": panel_id or None,
                "panel_assignment_basis": panel_assignment_basis or None,
                "panel_signature_parse_status": panel_signature_status or None,
                "panel_size": panel_size,
                "panel_context_complete": panel_context_complete,
                "panel_data_status": panel_data_status,
                "feature_provenance": json.dumps(
                    {
                        "label_basis": (
                            "human_reviewed_final" if use_final else "machine_suggestion"
                        ),
                        "identity_basis": "FastF1 classification plus sourced registry",
                        "affected_role_basis": (
                            "human_reviewed_final"
                            if use_final
                            else "machine_extracted_review_aid"
                        ),
                        "panel_basis": panel_assignment_basis or "not_available",
                        "panel_identity_basis": (
                            "official_decision_signature"
                            if panel_data_status == "source_observed"
                            else "single_panel_event_consensus"
                            if panel_data_status == "derived"
                            else "not_available"
                        ),
                    },
                    sort_keys=True,
                ),
            }
        )

    features = pd.DataFrame(feature_rows)
    roles = pd.DataFrame(role_rows)
    controls = _release_controls(
        documents, adjudications, exclusion_qa, workspace_validation, features
    )
    release_status = (
        "reportable_human_reviewed"
        if controls.set_index("control").loc["analytical_release", "status"] == "pass"
        else "blocked_pending_human_review"
    )
    if release_status == "reportable_human_reviewed":
        features["reporting_eligible"] = features["model_eligible"]
    controls.insert(0, "feature_build_id", feature_build_id)
    built_at = datetime.now(UTC)
    return AnalysisFeatureBuild(
        feature_build_id=feature_build_id,
        workspace_id=workspace_id,
        workspace_input_sha256=workspace_input_sha256,
        nationality_registry_sha256=registry_digest,
        panel_assignments_sha256=panel_digest,
        built_at_utc=built_at,
        release_status=release_status,
        features=features,
        driver_roles=roles,
        controls=controls,
    )


def build_analysis_features_from_workspace(
    connection: duckdb.DuckDBPyConnection,
    seed_directory: Path,
    workspace_directory: Path,
) -> AnalysisFeatureBuild:
    """Validate an editable workspace and build content-addressed analytical features."""

    session_context, driver_context = load_timing_review_context(connection)
    validation = validate_edited_full_corpus_coding_workspace(
        seed_directory,
        workspace_directory,
        session_context,
        driver_context,
    )
    if not validation["status"].eq("pass").all():
        failed = ", ".join(validation.loc[validation["status"].eq("fail"), "control"])
        raise ValueError(f"Workspace validation failed: {failed}")
    manifest_path = workspace_directory / WORKSPACE_MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    inputs = [manifest_path]
    inputs.extend(
        workspace_directory / name
        for name in (
            WORKSPACE_DOCUMENT_FILENAME,
            WORKSPACE_ADJUDICATION_FILENAME,
            WORKSPACE_EXCLUSION_QA_FILENAME,
        )
    )
    workspace_digest = _sha256(
        b"\n".join(path.name.encode("utf-8") + b":" + path.read_bytes() for path in inputs)
    )
    return assemble_analysis_features(
        connection,
        pd.read_csv(
            workspace_directory / WORKSPACE_DOCUMENT_FILENAME,
            dtype=str,
            keep_default_na=False,
        ),
        pd.read_csv(
            workspace_directory / WORKSPACE_ADJUDICATION_FILENAME,
            dtype=str,
            keep_default_na=False,
        ),
        pd.read_csv(
            workspace_directory / WORKSPACE_EXCLUSION_QA_FILENAME,
            dtype=str,
            keep_default_na=False,
        ),
        workspace_id=manifest["workspace_id"],
        workspace_input_sha256=workspace_digest,
        workspace_validation=validation,
    )


def replace_analysis_feature_build(
    connection: duckdb.DuckDBPyConnection,
    build: AnalysisFeatureBuild,
) -> None:
    """Transactionally materialize one immutable feature build in DuckDB."""

    metadata = pd.DataFrame(
        [
            {
                "feature_build_id": build.feature_build_id,
                "schema_version": FEATURE_SCHEMA_VERSION,
                "workspace_id": build.workspace_id,
                "workspace_input_sha256": build.workspace_input_sha256,
                "nationality_registry_sha256": build.nationality_registry_sha256,
                "panel_assignments_sha256": build.panel_assignments_sha256,
                "built_at_utc": build.built_at_utc,
                "release_status": build.release_status,
                "adjudication_rows": len(build.features),
                "driver_role_rows": len(build.driver_roles),
                "interpretation_boundary": INTERPRETATION_BOUNDARY,
            }
        ]
    )
    batches = {
        "analysis_feature_build_batch": metadata,
        "adjudication_feature_batch": build.features,
        "adjudication_role_batch": build.driver_roles,
        "feature_control_batch": build.controls,
    }
    for name, frame in batches.items():
        connection.register(name, frame)
    try:
        connection.execute("BEGIN TRANSACTION")
        for table in (
            "analysis.feature_release_controls",
            "analysis.adjudication_driver_roles",
            "analysis.adjudication_features",
            "metadata.analysis_feature_builds",
        ):
            connection.execute(
                f"DELETE FROM {table} WHERE feature_build_id = ?",  # noqa: S608
                [build.feature_build_id],
            )
        connection.execute(
            "INSERT INTO metadata.analysis_feature_builds BY NAME "
            "SELECT * FROM analysis_feature_build_batch"
        )
        connection.execute(
            "INSERT INTO analysis.adjudication_features BY NAME "
            "SELECT * FROM adjudication_feature_batch"
        )
        connection.execute(
            "INSERT INTO analysis.adjudication_driver_roles BY NAME "
            "SELECT * FROM adjudication_role_batch"
        )
        connection.execute(
            "INSERT INTO analysis.feature_release_controls BY NAME "
            "SELECT * FROM feature_control_batch"
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        for name in batches:
            connection.unregister(name)
