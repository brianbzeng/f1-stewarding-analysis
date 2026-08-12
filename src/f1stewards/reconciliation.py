"""Immutable reconciliation of independently reviewed pilot coding."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any

import pandas as pd

from f1stewards.manual import (
    CodedAdjudication,
    CrossEventSanctionEffect,
    HarmAssessment,
    ImpactAssessment,
    IncidentLocation,
    IncidentRelation,
    IndependentReviewRecord,
)
from f1stewards.readiness import load_pilot_manual_records

METHOD_VERSION = "pilot_reconciliation_v3"
INPUT_LABELS = (
    "coded_adjudications",
    "cross_event_sanction_effects",
    "harm_assessments",
    "impact_assessments",
    "incident_locations",
    "incident_relations",
    "independent_review",
)
OUTPUT_FILENAMES = (
    "adjudications.csv",
    "impact_assessments.csv",
    "harm_assessments.csv",
    "incident_locations.csv",
    "incident_relations.csv",
    "cross_event_sanction_effects.csv",
    "reconciliation_audit.csv",
    "manifest.json",
)
PROTECTED_FIELDS = {
    "adjudication": frozenset(
        {
            "adjudication_id",
            "event_id",
            "source_document_id",
            "source_url",
            "coder_id",
            "review_status",
        }
    ),
    "impact_assessment": frozenset(
        {
            "impact_assessment_id",
            "adjudication_id",
            "event_id",
            "source_document_id",
            "classification_source_document_id",
            "review_status",
        }
    ),
    "harm_assessment": frozenset(
        {
            "harm_assessment_id",
            "adjudication_id",
            "incident_id",
            "event_id",
            "source_document_id",
            "classification_source_document_id",
            "review_status",
        }
    ),
    "incident_location": frozenset(
        {
            "location_id",
            "incident_id",
            "event_id",
            "source_document_id",
            "coder_id",
            "review_status",
        }
    ),
    "incident_relation": frozenset(
        {
            "relation_id",
            "incident_id",
            "event_id",
            "source_document_id",
            "coder_id",
            "review_status",
        }
    ),
    "cross_event_sanction_effect": frozenset(
        {
            "cross_event_effect_id",
            "adjudication_id",
            "origin_event_id",
            "application_event_id",
            "source_document_id",
            "driver_number",
            "review_status",
        }
    ),
}


@dataclass(frozen=True)
class ReconciliationBundle:
    """Validated in-memory outputs before any files are written."""

    reconciliation_id: str
    adjudications: pd.DataFrame
    impacts: pd.DataFrame
    harms: pd.DataFrame
    locations: pd.DataFrame
    relations: pd.DataFrame
    cross_event_effects: pd.DataFrame
    audit: pd.DataFrame
    manifest: dict[str, Any]


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def file_sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _validate_input_hashes(input_sha256: Mapping[str, str]) -> dict[str, str]:
    if set(input_sha256) != set(INPUT_LABELS):
        raise ValueError(f"input_sha256 must contain exactly {', '.join(INPUT_LABELS)}")
    validated = dict(sorted(input_sha256.items()))
    for label, digest in validated.items():
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"Invalid SHA-256 for {label}")
    return validated


def _reconciliation_id(input_sha256: Mapping[str, str]) -> str:
    identity = json.dumps(
        {"method_version": METHOD_VERSION, "input_sha256": input_sha256},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"pilot-{_sha256_bytes(identity)[:12]}"


def _audit_row(
    review: IndependentReviewRecord,
    field_name: str,
    initial_value: Any,
    reconciled_value: Any,
) -> dict[str, Any]:
    return {
        "review_id": review.review_id,
        "target_type": review.target_type,
        "target_id": review.target_id,
        "review_decision": review.review_status,
        "field_name": field_name,
        "initial_value_json": _json_value(initial_value),
        "reconciled_value_json": _json_value(reconciled_value),
        "reviewer_id": review.reviewer_id,
        "reviewed_at_utc": review.reviewed_at_utc.astimezone(UTC).isoformat(),
        "reviewer_notes": review.reviewer_notes,
        "evidence_urls": review.evidence_urls,
    }


def _reconcile_record(
    record: (
        CodedAdjudication
        | ImpactAssessment
        | HarmAssessment
        | IncidentLocation
        | IncidentRelation
        | CrossEventSanctionEffect
    ),
    review: IndependentReviewRecord,
) -> tuple[
    CodedAdjudication
    | ImpactAssessment
    | HarmAssessment
    | IncidentLocation
    | IncidentRelation
    | CrossEventSanctionEffect,
    list[dict[str, Any]],
]:
    initial = record.model_dump(mode="json")
    corrections: dict[str, Any] = {}
    if review.review_status == "correct":
        corrections = json.loads(review.corrected_fields_json or "{}")

    known_fields = set(type(record).model_fields)
    unknown = sorted(set(corrections) - known_fields)
    if unknown:
        raise ValueError(f"{review.review_id} has unknown correction fields: {unknown}")
    protected = sorted(set(corrections) & PROTECTED_FIELDS[review.target_type])
    if protected:
        raise ValueError(f"{review.review_id} attempts to change protected fields: {protected}")

    unchanged = sorted(
        field_name
        for field_name, new_value in corrections.items()
        if _json_value(initial[field_name]) == _json_value(new_value)
    )
    if unchanged:
        raise ValueError(f"{review.review_id} marks unchanged fields as corrections: {unchanged}")

    reconciled_payload = {**initial, **corrections, "review_status": "double_coded"}
    reconciled = type(record).model_validate(reconciled_payload)
    reconciled_values = reconciled.model_dump(mode="json")
    audit = [
        _audit_row(review, field_name, initial[field_name], reconciled_values[field_name])
        for field_name in sorted(corrections)
    ]
    audit.append(
        _audit_row(
            review,
            "review_status",
            initial["review_status"],
            reconciled_values["review_status"],
        )
    )
    return reconciled, audit


def reconcile_pilot_records(
    coded: list[CodedAdjudication],
    impacts: list[ImpactAssessment],
    harms: list[HarmAssessment],
    locations: list[IncidentLocation],
    relations: list[IncidentRelation],
    cross_event_effects: list[CrossEventSanctionEffect],
    reviews: list[IndependentReviewRecord],
    input_sha256: Mapping[str, str],
) -> ReconciliationBundle:
    """Apply only completed, validated review decisions to new record versions."""

    hashes = _validate_input_hashes(input_sha256)
    unresolved = [
        review.review_id
        for review in reviews
        if review.review_status in {"pending", "needs_discussion"}
    ]
    if unresolved:
        raise ValueError(f"Cannot reconcile unresolved review records: {unresolved}")

    review_by_target = {(review.target_type, review.target_id): review for review in reviews}
    if len(review_by_target) != len(reviews):
        raise ValueError("Independent review targets must be unique")
    expected_targets = {
        *(("adjudication", record.adjudication_id) for record in coded),
        *(("impact_assessment", record.impact_assessment_id) for record in impacts),
        *(("harm_assessment", record.harm_assessment_id) for record in harms),
        *(("incident_location", record.location_id) for record in locations),
        *(("incident_relation", record.relation_id) for record in relations),
        *(
            ("cross_event_sanction_effect", record.cross_event_effect_id)
            for record in cross_event_effects
        ),
    }
    if set(review_by_target) != expected_targets:
        raise ValueError("Independent review targets do not match pilot coded artifacts")

    reconciled_adjudications: list[CodedAdjudication] = []
    reconciled_impacts: list[ImpactAssessment] = []
    reconciled_harms: list[HarmAssessment] = []
    reconciled_locations: list[IncidentLocation] = []
    reconciled_relations: list[IncidentRelation] = []
    reconciled_cross_event_effects: list[CrossEventSanctionEffect] = []
    audit_rows: list[dict[str, Any]] = []
    for record in coded:
        reconciled, audit = _reconcile_record(
            record,
            review_by_target[("adjudication", record.adjudication_id)],
        )
        reconciled_adjudications.append(reconciled)  # type: ignore[arg-type]
        audit_rows.extend(audit)
    for record in impacts:
        reconciled, audit = _reconcile_record(
            record,
            review_by_target[("impact_assessment", record.impact_assessment_id)],
        )
        reconciled_impacts.append(reconciled)  # type: ignore[arg-type]
        audit_rows.extend(audit)
    for record in harms:
        reconciled, audit = _reconcile_record(
            record,
            review_by_target[("harm_assessment", record.harm_assessment_id)],
        )
        reconciled_harms.append(reconciled)  # type: ignore[arg-type]
        audit_rows.extend(audit)
    for record in locations:
        reconciled, audit = _reconcile_record(
            record,
            review_by_target[("incident_location", record.location_id)],
        )
        reconciled_locations.append(reconciled)  # type: ignore[arg-type]
        audit_rows.extend(audit)
    for record in relations:
        reconciled, audit = _reconcile_record(
            record,
            review_by_target[("incident_relation", record.relation_id)],
        )
        reconciled_relations.append(reconciled)  # type: ignore[arg-type]
        audit_rows.extend(audit)
    for record in cross_event_effects:
        reconciled, audit = _reconcile_record(
            record,
            review_by_target[("cross_event_sanction_effect", record.cross_event_effect_id)],
        )
        reconciled_cross_event_effects.append(reconciled)  # type: ignore[arg-type]
        audit_rows.extend(audit)

    adjudication_ids = {record.adjudication_id for record in reconciled_adjudications}
    dangling_impacts = sorted(
        record.impact_assessment_id
        for record in reconciled_impacts
        if record.adjudication_id not in adjudication_ids
    )
    if dangling_impacts:
        raise ValueError(f"Reconciled impacts have unknown adjudications: {dangling_impacts}")
    dangling_harms = sorted(
        record.harm_assessment_id
        for record in reconciled_harms
        if record.adjudication_id not in adjudication_ids
    )
    if dangling_harms:
        raise ValueError(f"Reconciled harms have unknown adjudications: {dangling_harms}")

    incident_ids = {record.incident_id for record in reconciled_adjudications}
    dangling_locations = sorted(
        record.location_id
        for record in reconciled_locations
        if record.incident_id not in incident_ids
    )
    if dangling_locations:
        raise ValueError(f"Reconciled locations have unknown incidents: {dangling_locations}")
    dangling_relations = sorted(
        record.relation_id
        for record in reconciled_relations
        if record.incident_id not in incident_ids
    )
    if dangling_relations:
        raise ValueError(f"Reconciled relations have unknown incidents: {dangling_relations}")
    dangling_cross_event_effects = sorted(
        record.cross_event_effect_id
        for record in reconciled_cross_event_effects
        if record.adjudication_id not in adjudication_ids
    )
    if dangling_cross_event_effects:
        raise ValueError(
            "Reconciled cross-event effects have unknown adjudications: "
            f"{dangling_cross_event_effects}"
        )

    adjudication_frame = pd.DataFrame(
        [record.model_dump(mode="json") for record in reconciled_adjudications],
        columns=list(CodedAdjudication.model_fields),
    )
    impact_frame = pd.DataFrame(
        [record.model_dump(mode="json") for record in reconciled_impacts],
        columns=list(ImpactAssessment.model_fields),
    )
    harm_frame = pd.DataFrame(
        [record.model_dump(mode="json") for record in reconciled_harms],
        columns=list(HarmAssessment.model_fields),
    )
    location_frame = pd.DataFrame(
        [record.model_dump(mode="json") for record in reconciled_locations],
        columns=list(IncidentLocation.model_fields),
    )
    relation_frame = pd.DataFrame(
        [record.model_dump(mode="json") for record in reconciled_relations],
        columns=list(IncidentRelation.model_fields),
    )
    cross_event_frame = pd.DataFrame(
        [record.model_dump(mode="json") for record in reconciled_cross_event_effects],
        columns=list(CrossEventSanctionEffect.model_fields),
    )
    audit_frame = pd.DataFrame(audit_rows)
    decision_counts = Counter(review.review_status for review in reviews)
    reviewed_at = max(review.reviewed_at_utc for review in reviews)
    correction_rows = int(audit_frame.field_name.ne("review_status").sum())
    reconciliation_id = _reconciliation_id(hashes)
    manifest = {
        "schema_version": "2.0",
        "method_version": METHOD_VERSION,
        "reconciliation_id": reconciliation_id,
        "reconciled_at_utc": reviewed_at.astimezone(UTC).isoformat(),
        "input_sha256": hashes,
        "adjudication_count": len(reconciled_adjudications),
        "impact_assessment_count": len(reconciled_impacts),
        "harm_assessment_count": len(reconciled_harms),
        "incident_location_count": len(reconciled_locations),
        "incident_relation_count": len(reconciled_relations),
        "cross_event_sanction_effect_count": len(reconciled_cross_event_effects),
        "review_target_count": len(reviews),
        "review_decision_counts": dict(sorted(decision_counts.items())),
        "field_correction_count": correction_rows,
        "reviewer_ids": sorted({review.reviewer_id for review in reviews}),
        "release_status": "double_coded",
    }
    return ReconciliationBundle(
        reconciliation_id=reconciliation_id,
        adjudications=adjudication_frame,
        impacts=impact_frame,
        harms=harm_frame,
        locations=location_frame,
        relations=relation_frame,
        cross_event_effects=cross_event_frame,
        audit=audit_frame,
        manifest=manifest,
    )


def build_pilot_reconciliation(
    coding_path: Path,
    impact_path: Path,
    harm_path: Path,
    location_path: Path,
    relation_path: Path,
    cross_event_path: Path,
    review_path: Path,
) -> ReconciliationBundle:
    """Load linked CSVs, validate them, and build a reconciled in-memory bundle."""

    records = load_pilot_manual_records(
        coding_path,
        impact_path,
        harm_path,
        location_path,
        relation_path,
        cross_event_path,
        review_path,
    )
    return reconcile_pilot_records(
        records.adjudications,
        records.impacts,
        records.harms,
        records.locations,
        records.relations,
        records.cross_event_effects,
        records.reviews,
        {
            "coded_adjudications": file_sha256(coding_path),
            "impact_assessments": file_sha256(impact_path),
            "harm_assessments": file_sha256(harm_path),
            "incident_locations": file_sha256(location_path),
            "incident_relations": file_sha256(relation_path),
            "cross_event_sanction_effects": file_sha256(cross_event_path),
            "independent_review": file_sha256(review_path),
        },
    )


def serialize_reconciliation_bundle(bundle: ReconciliationBundle) -> dict[str, bytes]:
    """Create deterministic bytes and checksums for every reconciliation artifact."""

    outputs = {
        "adjudications.csv": bundle.adjudications.to_csv(index=False, lineterminator="\n").encode(
            "utf-8"
        ),
        "impact_assessments.csv": bundle.impacts.to_csv(index=False, lineterminator="\n").encode(
            "utf-8"
        ),
        "harm_assessments.csv": bundle.harms.to_csv(index=False, lineterminator="\n").encode(
            "utf-8"
        ),
        "incident_locations.csv": bundle.locations.to_csv(
            index=False, lineterminator="\n"
        ).encode("utf-8"),
        "incident_relations.csv": bundle.relations.to_csv(
            index=False, lineterminator="\n"
        ).encode("utf-8"),
        "cross_event_sanction_effects.csv": bundle.cross_event_effects.to_csv(
            index=False, lineterminator="\n"
        ).encode("utf-8"),
        "reconciliation_audit.csv": bundle.audit.to_csv(index=False, lineterminator="\n").encode(
            "utf-8"
        ),
    }
    manifest = {
        **bundle.manifest,
        "output_sha256": {
            filename: _sha256_bytes(content) for filename, content in sorted(outputs.items())
        },
    }
    outputs["manifest.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return outputs


def write_reconciliation_bundle(
    bundle: ReconciliationBundle,
    output_root: Path,
) -> tuple[Path, bool]:
    """Atomically create a content-addressed directory; never overwrite it."""

    outputs = serialize_reconciliation_bundle(bundle)
    output_root.mkdir(parents=True, exist_ok=True)
    final_directory = output_root / bundle.reconciliation_id
    if final_directory.exists():
        mismatches = [
            filename
            for filename, expected in outputs.items()
            if not (final_directory / filename).is_file()
            or (final_directory / filename).read_bytes() != expected
        ]
        if mismatches:
            raise FileExistsError(
                f"Existing reconciliation directory differs from validated output: {mismatches}"
            )
        return final_directory, False

    temporary_directory = Path(
        tempfile.mkdtemp(prefix=f".{bundle.reconciliation_id}-", dir=output_root)
    )
    try:
        for filename, content in outputs.items():
            (temporary_directory / filename).write_bytes(content)
        temporary_directory.replace(final_directory)
    except Exception:
        shutil.rmtree(temporary_directory, ignore_errors=True)
        raise
    return final_directory, True
