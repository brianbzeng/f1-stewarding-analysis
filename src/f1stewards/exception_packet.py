"""Document-level investigation packet for unresolved full-corpus review work."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd

from f1stewards.coding_workspace import (
    WORKSPACE_ADJUDICATION_FILENAME,
    WORKSPACE_DOCUMENT_FILENAME,
    WORKSPACE_EXCLUSION_QA_FILENAME,
    WORKSPACE_MANIFEST_FILENAME,
)
from f1stewards.first_pass import FIRST_PASS_AUDIT_FILENAME, FIRST_PASS_MANIFEST_FILENAME
from f1stewards.review_explorer import (
    REVIEW_CHAIN_MANIFEST_FILENAME,
    REVIEW_CHAIN_SCHEMA_VERSION,
    workspace_input_sha256,
)

EXCEPTION_PACKET_SCHEMA_VERSION = "full-corpus-exception-packet-v1"
INVESTIGATION_FILENAME = "investigation_queue.csv"
LINKAGE_FILENAME = "queue_linkage.csv"
EXCEPTION_MANIFEST_FILENAME = "exception_manifest.json"

QUEUE_ORDER = {"documents": 1, "adjudications": 2, "exclusion_qa": 3}
EVIDENCE_TEXT_FIELDS = ["fact_text", "infringement_text", "decision_text", "reason_text"]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _verify_first_pass_file(
    workspace_directory: Path,
    manifest: dict[str, Any],
    filename: str,
) -> None:
    path = workspace_directory / filename
    if not path.exists():
        raise ValueError(f"First-pass workspace is missing {filename}")
    expected = manifest["outputs"][filename]
    if _sha256(path.read_bytes()) != expected["sha256"]:
        raise ValueError(f"First-pass input hash mismatch: {filename}")


def _verified_workspace_sha256(
    workspace_directory: Path,
    first_pass: dict[str, Any],
) -> str:
    """Verify an original first pass or a content-addressed descendant review chain."""

    chain_path = workspace_directory / REVIEW_CHAIN_MANIFEST_FILENAME
    if not chain_path.exists():
        for filename in (
            WORKSPACE_DOCUMENT_FILENAME,
            WORKSPACE_ADJUDICATION_FILENAME,
            WORKSPACE_EXCLUSION_QA_FILENAME,
        ):
            _verify_first_pass_file(workspace_directory, first_pass, filename)
        return str(first_pass["output_workspace_sha256"])

    chain = json.loads(chain_path.read_text(encoding="utf-8"))
    if chain.get("schema_version") != REVIEW_CHAIN_SCHEMA_VERSION:
        raise ValueError("Unexpected review-chain schema version")
    if chain.get("workspace_id") != first_pass.get("workspace_id"):
        raise ValueError("Review-chain and first-pass workspace IDs disagree")
    if chain.get("first_pass_id") != first_pass.get("first_pass_id"):
        raise ValueError("Review-chain and first-pass IDs disagree")
    if chain.get("base_workspace_sha256") != first_pass.get("output_workspace_sha256"):
        raise ValueError("Review-chain base does not match the first-pass workspace")
    steps = chain.get("steps", [])
    expected_parent = chain.get("base_workspace_sha256")
    for step in steps:
        if step.get("parent_workspace_sha256") != expected_parent:
            raise ValueError("Review-chain parent/output continuity is broken")
        expected_parent = step.get("output_workspace_sha256")
    current_digest = workspace_input_sha256(workspace_directory)
    if not steps or expected_parent != current_digest:
        raise ValueError("Review chain is stale for the current workspace")
    if chain.get("current_workspace_sha256") != current_digest:
        raise ValueError("Review-chain current workspace digest is stale")
    return current_digest


def _root_cause(action_basis: str) -> str:
    basis = action_basis.casefold()
    if "version_resolution" in basis or "recalled" in basis:
        return "version_resolution"
    if "cross-family conflict" in basis:
        return "family_conflict"
    if "parser review" in basis or "manual_split_or_scope_review" in basis:
        return "parser_or_multi_decision"
    if "manual_offence_review" in basis:
        return "manual_offence_scope"
    if "manual_session_review" in basis:
        return "manual_session_scope"
    if "manual_scope_review" in basis:
        return "manual_scope"
    if "exclusion audit" in basis:
        return "exclusion_qa"
    return "other_unresolved"


def _priority(root_causes: set[str]) -> tuple[int, str]:
    ordered = (
        (1, "version_resolution", "unresolved_version"),
        (2, "family_conflict", "analytical_scope_conflict"),
        (3, "parser_or_multi_decision", "parser_or_multi_decision"),
        (4, "manual_offence_scope", "manual_scope"),
        (4, "manual_session_scope", "manual_scope"),
        (4, "manual_scope", "manual_scope"),
        (5, "exclusion_qa", "exclusion_quality_control"),
    )
    for number, cause, label in ordered:
        if cause in root_causes:
            return number, label
    return 6, "other_unresolved"


def _questions(root_causes: set[str]) -> str:
    questions: list[str] = []
    if "version_resolution" in root_causes:
        questions.append(
            "Can the recalled label be recovered or linked, and what final version disposition "
            "is supported?"
        )
    if "parser_or_multi_decision" in root_causes:
        questions.append(
            "Is this an adjudicative decision, how many accused-driver decisions does it "
            "contain, and what do the source sections state?"
        )
    if "family_conflict" in root_causes:
        questions.append(
            "Which single incident family and analytical scope are supported by the allegation "
            "and finding?"
        )
    if "manual_offence_scope" in root_causes or "manual_scope" in root_causes:
        questions.append(
            "Does the alleged conduct belong to a primary, secondary, or excluded offence family?"
        )
    if "manual_session_scope" in root_causes:
        questions.append("Which event session does the source decision actually adjudicate?")
    if "exclusion_qa" in root_causes:
        questions.append(
            "Does the source independently confirm the proposed exclusion; if not, which "
            "classifier rule must be audited?"
        )
    return " | ".join(questions)


def _next_action(root_causes: set[str]) -> str:
    if "version_resolution" in root_causes:
        return "recover_or_disposition_recalled_source"
    if "parser_or_multi_decision" in root_causes:
        return "inspect_pdf_structure_and_split_if_needed"
    if root_causes & {
        "family_conflict",
        "manual_offence_scope",
        "manual_session_scope",
        "manual_scope",
    }:
        return "resolve_session_family_and_inclusion"
    if "exclusion_qa" in root_causes:
        return "perform_independent_exclusion_check"
    return "manual_source_review"


def _evidence_status(row: pd.Series) -> tuple[str, str]:
    present = [field for field in EVIDENCE_TEXT_FIELDS if str(row.get(field, "")).strip()]
    missing = [field for field in EVIDENCE_TEXT_FIELDS if field not in present]
    if len(present) == len(EVIDENCE_TEXT_FIELDS):
        status = "full_standard_sections"
    elif present:
        status = "partial_sections"
    elif str(row.get("adjudication_instance_id", "")):
        status = "linked_source_without_core_sections"
    else:
        status = "archive_label_only"
    return status, "|".join(missing)


def _pipe(values: pd.Series) -> str:
    cleaned = [str(value) for value in values if str(value)]
    return "|".join(dict.fromkeys(cleaned))


def build_exception_frames(
    documents: pd.DataFrame,
    adjudications: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
    audit: pd.DataFrame,
    *,
    first_pass_id: str,
    workspace_sha256: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Collapse unresolved queue rows into source-document investigations."""

    unresolved = audit.loc[audit["first_pass_action"].eq("unresolved")].copy()
    unresolved["root_cause"] = unresolved["action_basis"].map(_root_cause)

    id_fields = {
        "documents": "document_review_id",
        "adjudications": "adjudication_instance_id",
        "exclusion_qa": "exclusion_qa_id",
    }
    source_frames = {
        "documents": documents,
        "adjudications": adjudications,
        "exclusion_qa": exclusion_qa,
    }
    link_rows: list[dict[str, str]] = []
    for queue_name, group in unresolved.groupby("queue_name", sort=False):
        if queue_name not in source_frames:
            raise ValueError(f"Unknown first-pass audit queue: {queue_name}")
        source = source_frames[queue_name]
        key = id_fields[queue_name]
        context = source.set_index(key)
        for _, row in group.iterrows():
            row_id = str(row["row_id"])
            if row_id not in context.index:
                raise ValueError(f"Audit row is absent from {queue_name}: {row_id}")
            source_row = context.loc[row_id]
            if isinstance(source_row, pd.DataFrame):
                raise ValueError(f"Duplicate source row ID in {queue_name}: {row_id}")
            document_id = str(source_row["document_id"])
            link_rows.append(
                {
                    "investigation_id": f"investigation-{document_id}",
                    "document_id": document_id,
                    "queue_name": queue_name,
                    "queue_order": str(QUEUE_ORDER[queue_name]),
                    "row_id": row_id,
                    "workspace_review_order": str(
                        source_row.get("workspace_review_order", "")
                    ),
                    "root_cause": str(row["root_cause"]),
                    "action_basis": str(row["action_basis"]),
                    "source_url": str(source_row.get("source_url", "")),
                    "review_status": str(source_row.get("review_status", "")),
                }
            )
    linkage = pd.DataFrame(link_rows).sort_values(
        ["document_id", "queue_order", "row_id"], kind="stable"
    ).reset_index(drop=True)

    document_lookup = documents.set_index("document_id")
    evidence = adjudications.sort_values(
        "adjudication_instance_id", kind="stable"
    ).drop_duplicates("document_id", keep="first")
    evidence_lookup = evidence.set_index("document_id")
    investigation_rows: list[dict[str, Any]] = []
    for document_id, group in linkage.groupby("document_id", sort=False):
        if document_id not in document_lookup.index:
            raise ValueError(f"Investigation document is absent from document queue: {document_id}")
        document = document_lookup.loc[document_id]
        if isinstance(document, pd.DataFrame):
            raise ValueError(f"Duplicate document queue ID: {document_id}")
        evidence_row = (
            evidence_lookup.loc[document_id]
            if document_id in evidence_lookup.index
            else pd.Series(dtype=str)
        )
        if isinstance(evidence_row, pd.DataFrame):
            raise ValueError(f"Duplicate protected evidence for document: {document_id}")
        causes = set(group["root_cause"])
        priority_number, priority_bucket = _priority(causes)
        status, missing_sections = _evidence_status(evidence_row)
        queue_memberships = sorted(set(group["queue_name"]), key=QUEUE_ORDER.get)
        investigation_rows.append(
            {
                "investigation_id": f"investigation-{document_id}",
                "document_id": document_id,
                "review_priority": priority_number,
                "priority_bucket": priority_bucket,
                "queue_memberships": "|".join(queue_memberships),
                "linked_queue_rows": len(group),
                "root_causes": "|".join(sorted(causes)),
                "event_id": str(document.get("event_id", "")),
                "season": str(document.get("season", "")),
                "round_number": str(document.get("round_number", "")),
                "event_name": str(document.get("event_name", "")),
                "title": str(document.get("title", "")),
                "source_url": str(document.get("source_url", "")),
                "version_state_suggestion": str(
                    document.get("version_state_suggestion", "")
                ),
                "parser_review_required": str(
                    document.get("parser_review_required", "")
                ),
                "family_conflict_suggestion": str(
                    document.get("family_conflict_suggestion", "")
                ),
                "session_type_suggestion": str(
                    document.get("session_type_suggestion", "")
                ),
                "session_scope_suggestion": str(
                    document.get("session_scope_suggestion", "")
                ),
                "offence_family_suggestion": str(
                    document.get("offence_family_suggestion", "")
                ),
                "eligibility_suggestion": str(
                    document.get("eligibility_suggestion", "")
                ),
                "adjudication_instance_id": str(
                    evidence_row.get("adjudication_instance_id", "")
                ),
                "driver_number_suggestion": str(
                    evidence_row.get("driver_number_suggestion", "")
                ),
                "driver_name_suggestion": str(
                    evidence_row.get("driver_name_suggestion", "")
                ),
                "participant_driver_numbers_suggestion": str(
                    evidence_row.get("participant_driver_numbers_suggestion", "")
                ),
                "outcome_family_suggestion": str(
                    evidence_row.get("outcome_family_suggestion", "")
                ),
                "evidence_status": status,
                "missing_evidence_sections": missing_sections,
                "fact_text": str(evidence_row.get("fact_text", "")),
                "infringement_text": str(evidence_row.get("infringement_text", "")),
                "decision_text": str(evidence_row.get("decision_text", "")),
                "reason_text": str(evidence_row.get("reason_text", "")),
                "review_questions": _questions(causes),
                "suggested_next_action": _next_action(causes),
                "first_pass_id": first_pass_id,
                "workspace_sha256": workspace_sha256,
            }
        )
    investigations = pd.DataFrame(investigation_rows).sort_values(
        ["review_priority", "season", "round_number", "event_id", "document_id"],
        kind="stable",
    ).reset_index(drop=True)
    investigations["investigation_order"] = investigations.index + 1
    order = ["investigation_order", *[c for c in investigations if c != "investigation_order"]]
    investigations = investigations[order]

    membership_counts = investigations["queue_memberships"].value_counts().sort_index()
    evidence_counts = investigations["evidence_status"].value_counts().sort_index()
    priority_counts = investigations["priority_bucket"].value_counts().sort_index()
    summary = {
        "unresolved_queue_rows": int(len(linkage)),
        "unique_document_investigations": int(len(investigations)),
        "duplicate_queue_rows_eliminated": int(len(linkage) - len(investigations)),
        "all_three_queue_documents": int(
            investigations["queue_memberships"].eq(
                "documents|adjudications|exclusion_qa"
            ).sum()
        ),
        "queue_membership_counts": {
            str(key): int(value) for key, value in membership_counts.items()
        },
        "evidence_status_counts": {
            str(key): int(value) for key, value in evidence_counts.items()
        },
        "priority_counts": {str(key): int(value) for key, value in priority_counts.items()},
    }
    return investigations, linkage, summary


def build_exception_packet_payloads(
    workspace_directory: Path,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Build deterministic exception packet files from a verified first-pass workspace."""

    first_pass_path = workspace_directory / FIRST_PASS_MANIFEST_FILENAME
    if not first_pass_path.exists():
        raise ValueError(f"Missing first-pass manifest: {first_pass_path}")
    first_pass = json.loads(first_pass_path.read_text(encoding="utf-8"))
    _verify_first_pass_file(workspace_directory, first_pass, FIRST_PASS_AUDIT_FILENAME)
    current_workspace_sha256 = _verified_workspace_sha256(
        workspace_directory, first_pass
    )
    workspace_manifest = json.loads(
        (workspace_directory / WORKSPACE_MANIFEST_FILENAME).read_text(encoding="utf-8")
    )
    if workspace_manifest.get("workspace_id") != first_pass.get("workspace_id"):
        raise ValueError("First-pass and protected workspace IDs disagree")

    documents = _read_csv(workspace_directory / WORKSPACE_DOCUMENT_FILENAME)
    adjudications = _read_csv(workspace_directory / WORKSPACE_ADJUDICATION_FILENAME)
    exclusion_qa = _read_csv(workspace_directory / WORKSPACE_EXCLUSION_QA_FILENAME)
    audit = _read_csv(workspace_directory / FIRST_PASS_AUDIT_FILENAME)
    investigations, linkage, summary = build_exception_frames(
        documents,
        adjudications,
        exclusion_qa,
        audit,
        first_pass_id=first_pass["first_pass_id"],
        workspace_sha256=current_workspace_sha256,
    )
    payloads = {
        INVESTIGATION_FILENAME: _csv_bytes(investigations),
        LINKAGE_FILENAME: _csv_bytes(linkage),
    }
    packet_id = "exception-packet-" + _sha256(
        (
            EXCEPTION_PACKET_SCHEMA_VERSION
            + "\n"
            + first_pass["first_pass_id"]
            + "\n"
            + "\n".join(
                f"{name}:{_sha256(payload)}" for name, payload in sorted(payloads.items())
            )
        ).encode("utf-8")
    )[:12]
    manifest = {
        "schema_version": EXCEPTION_PACKET_SCHEMA_VERSION,
        "exception_packet_id": packet_id,
        "first_pass_id": first_pass["first_pass_id"],
        "workspace_id": first_pass["workspace_id"],
        "workspace_sha256": current_workspace_sha256,
        "summary": summary,
        "outputs": {
            name: {
                "sha256": _sha256(payload),
                "row_count": (
                    len(investigations)
                    if name == INVESTIGATION_FILENAME
                    else len(linkage)
                ),
            }
            for name, payload in payloads.items()
        },
        "interpretation_boundary": (
            "The packet de-duplicates source investigations and supplies review context. It does "
            "not resolve an exception, confirm an exclusion, or count as independent review."
        ),
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return {**payloads, EXCEPTION_MANIFEST_FILENAME: manifest_bytes}, manifest


def write_exception_packet(
    workspace_directory: Path,
    output_root: Path,
) -> tuple[Path, dict[str, Any], bool]:
    """Write or byte-verify a content-addressed exception packet."""

    payloads, manifest = build_exception_packet_payloads(workspace_directory)
    output_directory = output_root / manifest["exception_packet_id"]
    created = not output_directory.exists()
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        path = output_directory / name
        if path.exists() and path.read_bytes() != payload:
            raise FileExistsError(f"Exception packet differs from rebuild: {path}")
        path.write_bytes(payload)
    return output_directory, manifest, created
