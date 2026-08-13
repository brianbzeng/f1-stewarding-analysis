"""Deterministic, blind source packets for the Study v2 independent human audit."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from f1stewards.config import PROJECT_ROOT, load_study_v2_settings

MODEL_WORKSPACE = (
    PROJECT_ROOT
    / "data"
    / "manual"
    / "full_corpus_model_review"
    / "model-review-3dacc1268f13"
    / "full-coding-e0192ecbd9e4"
)
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "processed" / "f1_stewarding.duckdb"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "manual" / "study_v2_review_packets"

REVIEW_FIELDS = [
    "reviewer_id",
    "reviewed_at",
    "reviewed_version_status",
    "reviewed_content_class",
    "reviewed_session_type",
    "reviewed_incident_family",
    "reviewed_eligibility",
    "reviewed_accused_driver_number",
    "reviewed_affected_driver_numbers",
    "reviewed_lap_number",
    "reviewed_location",
    "reviewed_outcome_family",
    "reviewed_penalty_seconds",
    "reviewed_penalty_points",
    "reviewed_grid_places",
    "reviewed_fault_language",
    "review_confidence",
    "evidence_span",
    "review_notes",
]

PACKET_SOURCE_FIELDS = [
    "review_assignment_id",
    "reviewer_arm",
    "selection_basis",
    "document_id",
    "event_id",
    "season",
    "round_number",
    "event_name",
    "event_date",
    "title",
    "source_url",
    "published_at",
    "archive_document_class",
    "source_availability_status",
    "content_sha256",
    "page_count",
    "raw_text",
    "fact_text",
    "infringement_text",
    "decision_text",
    "reason_text",
]

MULTILINE_EVIDENCE_FIELDS = [
    "raw_text",
    "fact_text",
    "infringement_text",
    "decision_text",
    "reason_text",
]

FORBIDDEN_PACKET_FIELDS = {
    "version_status_final",
    "session_scope_final",
    "offence_family_final",
    "eligibility_final",
    "exclusion_reason_final",
    "review_status",
    "adjudication_id_final",
    "incident_id_final",
    "accused_driver_number_final",
    "affected_driver_numbers_final",
    "session_type_final",
    "lap_number_final",
    "location_final",
    "incident_family_final",
    "outcome_family_final",
    "penalty_seconds_final",
    "penalty_points_final",
    "grid_places_final",
    "fault_language_final",
    "include_primary_final",
    "include_secondary_final",
    "coding_notes",
}


@dataclass(frozen=True)
class ReviewPacketBuild:
    packet_id: str
    output_dir: Path
    reviewer_a_rows: int
    reviewer_b_rows: int
    elevated_risk_documents: int
    high_risk_inclusions: int


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype(str).str.casefold().eq("true")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def _normalize_multiline_evidence(value: object) -> str:
    """Remove PDF-extraction line padding without changing the evidence wording."""

    normalized = "\n".join(line.rstrip() for line in str(value).splitlines())
    return normalized.strip("\n")


def _stable_key(document_id: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}|{document_id}".encode()).hexdigest()


def _version_risk(documents: pd.DataFrame) -> pd.Series:
    return (
        documents["version_state_suggestion"].ne("live_standalone")
        | documents["title"].str.contains(
            r"correct|replacement|recalled", case=False, regex=True, na=False
        )
        | documents["supersedes_document_id"].ne("")
        | documents["successor_document_id"].ne("")
        | documents["version_status_final"].ne("effective")
    )


def select_review_documents(
    documents: pd.DataFrame,
    adjudications: pd.DataFrame,
) -> pd.DataFrame:
    """Return source-level risk flags without exposing final labels in the packet."""

    version_risk = _version_risk(documents)
    elevated = (
        _truthy(documents["parser_review_required"])
        | _truthy(documents["family_conflict_suggestion"])
        | version_risk
        | documents["review_status"].eq("model_reviewed_corrected")
    )
    primary_multi = adjudications.loc[
        _truthy(adjudications["include_primary_final"])
        & _truthy(adjudications["multi_party_suggestion"]),
        "document_id",
    ]
    result = documents[["document_id"]].copy()
    result["elevated_risk"] = elevated
    result["included_multi_party"] = result["document_id"].isin(set(primary_multi))
    result["risk_or_multi"] = result["elevated_risk"] | result["included_multi_party"]
    result["current_inclusion"] = documents["eligibility_final"].eq("include")
    result["clean_exclusion"] = ~result["risk_or_multi"] & ~result["current_inclusion"]
    return result


def _round_robin_stratified_sample(
    candidates: pd.DataFrame,
    size: int,
    strata: list[str],
    salt: str,
) -> pd.DataFrame:
    if size < 0 or size > len(candidates):
        raise ValueError("Requested review sample size is outside the candidate population")
    if size == 0:
        return candidates.head(0).copy()
    work = candidates.copy()
    work["_sample_key"] = work["document_id"].map(lambda value: _stable_key(value, salt))
    groups: list[pd.DataFrame] = []
    grouper: str | list[str] = strata[0] if len(strata) == 1 else strata
    for _, group in work.groupby(grouper, dropna=False, sort=True):
        groups.append(group.sort_values(["_sample_key", "document_id"]).reset_index(drop=True))
    selected: list[pd.Series] = []
    offset = 0
    while len(selected) < size:
        added = False
        for group in groups:
            if offset < len(group):
                selected.append(group.iloc[offset])
                added = True
                if len(selected) == size:
                    break
        if not added:
            break
        offset += 1
    return pd.DataFrame(selected).drop(columns="_sample_key").reset_index(drop=True)


def _source_evidence(database_path: Path) -> pd.DataFrame:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        return connection.execute(
            """
            SELECT
                s.document_id,
                s.content_sha256,
                t.page_count,
                t.raw_text,
                t.fact_text,
                t.infringement_text,
                t.decision_text,
                t.reason_text
            FROM raw.source_documents AS s
            LEFT JOIN raw.document_text AS t USING (document_id)
            """
        ).fetchdf()


def _selection_basis(row: pd.Series) -> str:
    reasons: list[str] = []

    def is_selected(field: str) -> bool:
        return row.get(field) is True or row.get(field) == "True"

    if is_selected("elevated_risk"):
        reasons.append("elevated_risk")
    if is_selected("included_multi_party"):
        reasons.append("included_multi_party")
    if is_selected("clean_exclusion_sample"):
        reasons.append("clean_exclusion_sample")
    if is_selected("stratified_exclusion_sample"):
        reasons.append("stratified_exclusion_sample")
    if is_selected("published_case_study"):
        reasons.append("published_case_study")
    return "|".join(reasons)


def _packet_frame(
    selected: pd.DataFrame,
    documents: pd.DataFrame,
    evidence: pd.DataFrame,
    reviewer_arm: str,
) -> pd.DataFrame:
    source_columns = [
        "document_id",
        "event_id",
        "season",
        "round_number",
        "event_name",
        "event_date",
        "title",
        "source_url",
        "published_at",
        "archive_document_class",
        "source_availability_status",
    ]
    selection_fields = [
        field
        for field in (
            "document_id",
            "elevated_risk",
            "included_multi_party",
            "risk_or_multi",
            "current_inclusion",
            "clean_exclusion",
            "clean_exclusion_sample",
            "stratified_exclusion_sample",
            "published_case_study",
        )
        if field in selected
    ]
    frame = selected[selection_fields].merge(
        documents[source_columns], on="document_id", validate="one_to_one"
    )
    frame = frame.merge(evidence, on="document_id", how="left", validate="one_to_one")
    frame.insert(0, "selection_basis", frame.apply(_selection_basis, axis=1))
    frame.insert(0, "reviewer_arm", reviewer_arm)
    frame.insert(
        0,
        "review_assignment_id",
        frame["document_id"].map(lambda value: f"{reviewer_arm}-{value}"),
    )
    for field in REVIEW_FIELDS:
        frame[field] = ""
    for field in PACKET_SOURCE_FIELDS:
        if field not in frame:
            frame[field] = ""
    for field in MULTILINE_EVIDENCE_FIELDS:
        frame[field] = frame[field].map(_normalize_multiline_evidence)
    packet = frame[PACKET_SOURCE_FIELDS + REVIEW_FIELDS].astype(object)
    return packet.where(pd.notna(packet), "")


def build_review_packet(
    *,
    workspace: Path = MODEL_WORKSPACE,
    database_path: Path = DEFAULT_DATABASE,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> ReviewPacketBuild:
    settings = load_study_v2_settings()
    review = settings["human_review"]
    documents = pd.read_csv(
        workspace / "document_review_worklist.csv", keep_default_na=False, low_memory=False
    )
    adjudications = pd.read_csv(
        workspace / "adjudication_coding_worklist.csv", keep_default_na=False, low_memory=False
    )
    flags = select_review_documents(documents, adjudications)
    selection = documents[
        [
            "document_id",
            "event_id",
            "season",
            "archive_document_class",
            "offence_family_group_suggestion",
        ]
    ].merge(flags, on="document_id", validate="one_to_one")
    salt = str(review["sample_hash_salt"])

    clean_a = _round_robin_stratified_sample(
        selection.loc[selection["clean_exclusion"]],
        int(review["reviewer_a"]["clean_exclusion_sample_size"]),
        ["season", "archive_document_class"],
        f"{salt}|reviewer-a-clean",
    )
    clean_a["clean_exclusion_sample"] = True
    risk_a = selection.loc[selection["risk_or_multi"]].copy()
    risk_a["clean_exclusion_sample"] = False
    reviewer_a = pd.concat([risk_a, clean_a], ignore_index=True).drop_duplicates("document_id")

    exclusions_b = _round_robin_stratified_sample(
        selection.loc[~selection["current_inclusion"]],
        int(review["reviewer_b"]["stratified_exclusion_sample_size"]),
        ["season", "offence_family_group_suggestion"],
        f"{salt}|reviewer-b-exclusions",
    )
    exclusions_b["stratified_exclusion_sample"] = True
    high_risk_inclusions = selection.loc[
        selection["risk_or_multi"] & selection["current_inclusion"]
    ].copy()
    high_risk_inclusions["stratified_exclusion_sample"] = False
    case_studies = selection.loc[
        selection["current_inclusion"]
        & selection["event_id"].isin({"2019-aut", "2023-abu", "2025-aut"})
    ].copy()
    case_studies["published_case_study"] = True
    reviewer_b = pd.concat(
        [high_risk_inclusions, exclusions_b, case_studies], ignore_index=True
    ).drop_duplicates("document_id")
    if "published_case_study" not in reviewer_b:
        reviewer_b["published_case_study"] = False
    reviewer_b["published_case_study"] = reviewer_b["published_case_study"].eq(True)

    evidence = _source_evidence(database_path)
    packet_a = _packet_frame(reviewer_a, documents, evidence, "reviewer_a")
    packet_b = _packet_frame(reviewer_b, documents, evidence, "reviewer_b")
    packet_a = packet_a.sort_values(["season", "event_id", "document_id"]).reset_index(drop=True)
    packet_b = packet_b.sort_values(["season", "event_id", "document_id"]).reset_index(drop=True)

    payload_hash = _sha256_bytes(_csv_bytes(packet_a) + _csv_bytes(packet_b))
    packet_id = f"study-v2-review-{payload_hash[:12]}"
    output_dir = output_root / packet_id
    output_dir.mkdir(parents=True, exist_ok=False)
    packet_a.to_csv(output_dir / "reviewer_a_source_reviews.csv", index=False, lineterminator="\n")
    packet_b.to_csv(output_dir / "reviewer_b_source_reviews.csv", index=False, lineterminator="\n")
    reconciliation = pd.DataFrame(
        columns=[
            "document_id",
            "field_name",
            "reviewer_a_value",
            "reviewer_b_value",
            "reconciled_value",
            "adjudicator_id",
            "adjudicated_at",
            "evidence_span",
            "adjudication_notes",
        ]
    )
    reconciliation.to_csv(output_dir / "reconciliation_queue.csv", index=False, lineterminator="\n")

    manifest: dict[str, Any] = {
        "schema_version": "study-v2-human-review-packet-v1",
        "packet_id": packet_id,
        "created_at": datetime.now(UTC).isoformat(),
        "protocol_frozen_at": str(settings["protocol_frozen_at"]),
        "parent_model_review_run": settings["parent_model_review_run"],
        "parent_feature_build": settings["parent_feature_build"],
        "blind_to_model_final_fields": True,
        "reviewer_a_rows": len(packet_a),
        "reviewer_b_rows": len(packet_b),
        "elevated_risk_documents": int(selection["risk_or_multi"].sum()),
        "high_risk_inclusions": len(high_risk_inclusions),
        "reviewer_a_clean_exclusion_sample": len(clean_a),
        "reviewer_b_exclusion_sample": len(exclusions_b),
        "missing_source_text_rows_a": int(packet_a["raw_text"].eq("").sum()),
        "missing_source_text_rows_b": int(packet_b["raw_text"].eq("").sum()),
        "reviewer_a_sha256": _sha256_bytes(_csv_bytes(packet_a)),
        "reviewer_b_sha256": _sha256_bytes(_csv_bytes(packet_b)),
        "reconciliation_sha256": _sha256_bytes(_csv_bytes(reconciliation)),
        "instructions": "docs/study_v2_human_review_guide.md",
        "release_note": (
            "Reviewing sampled records validates those records and audit error rates; it does not "
            "upgrade the unreviewed corpus to human_reviewed_final."
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    validate_review_packet(output_dir)
    return ReviewPacketBuild(
        packet_id=packet_id,
        output_dir=output_dir,
        reviewer_a_rows=len(packet_a),
        reviewer_b_rows=len(packet_b),
        elevated_risk_documents=int(selection["risk_or_multi"].sum()),
        high_risk_inclusions=len(high_risk_inclusions),
    )


def validate_review_packet(packet_dir: Path, *, require_blank: bool = True) -> dict[str, Any]:
    manifest = json.loads((packet_dir / "manifest.json").read_text(encoding="utf-8"))
    controls: list[dict[str, Any]] = []
    for reviewer in ("a", "b"):
        path = packet_dir / f"reviewer_{reviewer}_source_reviews.csv"
        frame = pd.read_csv(path, keep_default_na=False, low_memory=False)
        forbidden = sorted(FORBIDDEN_PACKET_FIELDS & set(frame.columns))
        duplicate_count = int(frame["document_id"].duplicated().sum())
        populated = int(frame[REVIEW_FIELDS].ne("").sum().sum()) if require_blank else 0
        expected_hash = manifest[f"reviewer_{reviewer}_sha256"]
        controls.extend(
            [
                {
                    "control": f"reviewer_{reviewer}_forbidden_fields_absent",
                    "status": "pass" if not forbidden else "fail",
                    "observed": "|".join(forbidden),
                },
                {
                    "control": f"reviewer_{reviewer}_document_ids_unique",
                    "status": "pass" if duplicate_count == 0 else "fail",
                    "observed": duplicate_count,
                },
                {
                    "control": f"reviewer_{reviewer}_initial_fields_blank",
                    "status": "pass" if populated == 0 else "fail",
                    "observed": populated,
                },
                {
                    "control": f"reviewer_{reviewer}_hash",
                    "status": (
                        "pass" if _sha256_bytes(_csv_bytes(frame)) == expected_hash else "fail"
                    ),
                    "observed": expected_hash,
                },
            ]
        )
    failed = [control for control in controls if control["status"] == "fail"]
    if failed:
        names = ", ".join(str(control["control"]) for control in failed)
        raise ValueError(f"Review packet failed controls: {names}")
    return {"status": "pass", "controls": controls}
