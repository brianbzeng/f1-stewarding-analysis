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

from f1stewards.manual import CodedAdjudication, ImpactAssessment, IndependentReviewRecord
from f1stewards.readiness import load_pilot_manual_records

METHOD_VERSION = "pilot_reconciliation_v1"
INPUT_LABELS = ("coded_adjudications", "impact_assessments", "independent_review")
OUTPUT_FILENAMES = (
    "adjudications.csv",
    "impact_assessments.csv",
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
}


@dataclass(frozen=True)
class ReconciliationBundle:
    """Validated in-memory outputs before any files are written."""

    reconciliation_id: str
    adjudications: pd.DataFrame
    impacts: pd.DataFrame
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
    record: CodedAdjudication | ImpactAssessment,
    review: IndependentReviewRecord,
) -> tuple[CodedAdjudication | ImpactAssessment, list[dict[str, Any]]]:
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
        *(('adjudication', record.adjudication_id) for record in coded),
        *(('impact_assessment', record.impact_assessment_id) for record in impacts),
    }
    if set(review_by_target) != expected_targets:
        raise ValueError("Independent review targets do not match pilot coded artifacts")

    reconciled_adjudications: list[CodedAdjudication] = []
    reconciled_impacts: list[ImpactAssessment] = []
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

    adjudication_ids = {record.adjudication_id for record in reconciled_adjudications}
    dangling_impacts = sorted(
        record.impact_assessment_id
        for record in reconciled_impacts
        if record.adjudication_id not in adjudication_ids
    )
    if dangling_impacts:
        raise ValueError(f"Reconciled impacts have unknown adjudications: {dangling_impacts}")

    adjudication_frame = pd.DataFrame(
        [record.model_dump(mode="json") for record in reconciled_adjudications],
        columns=list(CodedAdjudication.model_fields),
    )
    impact_frame = pd.DataFrame(
        [record.model_dump(mode="json") for record in reconciled_impacts],
        columns=list(ImpactAssessment.model_fields),
    )
    audit_frame = pd.DataFrame(audit_rows)
    decision_counts = Counter(review.review_status for review in reviews)
    reviewed_at = max(review.reviewed_at_utc for review in reviews)
    correction_rows = int(audit_frame.field_name.ne("review_status").sum())
    reconciliation_id = _reconciliation_id(hashes)
    manifest = {
        "schema_version": "1.0",
        "method_version": METHOD_VERSION,
        "reconciliation_id": reconciliation_id,
        "reconciled_at_utc": reviewed_at.astimezone(UTC).isoformat(),
        "input_sha256": hashes,
        "adjudication_count": len(reconciled_adjudications),
        "impact_assessment_count": len(reconciled_impacts),
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
        audit=audit_frame,
        manifest=manifest,
    )


def build_pilot_reconciliation(
    coding_path: Path,
    impact_path: Path,
    review_path: Path,
) -> ReconciliationBundle:
    """Load linked CSVs, validate them, and build a reconciled in-memory bundle."""

    coded, impacts, reviews = load_pilot_manual_records(coding_path, impact_path, review_path)
    return reconcile_pilot_records(
        coded,
        impacts,
        reviews,
        {
            "coded_adjudications": file_sha256(coding_path),
            "impact_assessments": file_sha256(impact_path),
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
