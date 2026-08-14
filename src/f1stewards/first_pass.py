"""Conservative machine-assisted prefill for the full-corpus review workspace."""

from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from f1stewards.coding_queue import (
    FINAL_ADJUDICATION_FIELDS,
    FINAL_DOCUMENT_FIELDS,
)
from f1stewards.coding_workspace import (
    WORKSPACE_ADJUDICATION_FILENAME,
    WORKSPACE_DOCUMENT_FILENAME,
    WORKSPACE_EXCLUSION_QA_FILENAME,
    WORKSPACE_MANIFEST_FILENAME,
)
from f1stewards.review_explorer import workspace_input_sha256

FIRST_PASS_SCHEMA_VERSION = "full-corpus-machine-assisted-first-pass-v3"
FIRST_PASS_MANIFEST_FILENAME = "first_pass_manifest.json"
FIRST_PASS_AUDIT_FILENAME = "first_pass_audit.csv"
DEFAULT_CODER_ID = "codex_assisted_prefill_v1"

SAFE_DOCUMENT_ELIGIBILITY = {
    "primary_candidate",
    "secondary_candidate",
    "out_of_scope_suggestion",
    "content_exclusion_suggestion",
    "version_exclusion_suggestion",
}
SAFE_ADJUDICATION_ACTIONS = {
    "review_primary_adjudication",
    "review_secondary_adjudication",
    "review_exclusion",
}
SAFE_PARSER_EXCLUSION_ELIGIBILITY = {"out_of_scope_suggestion"}
VERSION_STATUS_MAP = {
    "live_standalone": "effective",
    "corrected_successor": "effective",
    "recalled_linked_predecessor": "superseded",
}
SESSION_SCOPE_MAP = {
    "primary_race_sprint": "primary",
    "secondary_qualifying": "secondary",
    "out_of_scope_session": "out_of_scope",
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _is_true(value: Any) -> bool:
    return str(value).strip().casefold() == "true"


def _has_existing_edits(row: pd.Series, fields: list[str]) -> bool:
    return any(str(row.get(field, "")).strip() for field in fields)


def _document_exclusion_reason(row: pd.Series) -> str:
    eligibility = str(row["eligibility_suggestion"])
    if eligibility == "content_exclusion_suggestion":
        return "archive_label_not_steward_decision"
    if eligibility == "version_exclusion_suggestion":
        return "superseded_recalled_predecessor"
    session_scope = str(row.get("session_scope_suggestion", ""))
    family_group = str(row.get("offence_family_group_suggestion", ""))
    family = str(row.get("offence_family_suggestion", ""))
    if session_scope == "out_of_scope_session":
        return "out_of_scope_session"
    if session_scope == "secondary_qualifying" and family_group != "secondary":
        return "outside_secondary_offence_scope"
    if family_group == "excluded" and family:
        return f"excluded_offence_family:{family}"
    if family_group == "unclassified":
        return "unclassified_outside_frozen_scope"
    return "outside_frozen_primary_secondary_scope"


def _document_prefill(row: pd.Series, coder_id: str) -> tuple[dict[str, str] | None, str]:
    eligibility = str(row.get("eligibility_suggestion", ""))
    if eligibility not in SAFE_DOCUMENT_ELIGIBILITY:
        return None, f"manual eligibility path: {eligibility or 'blank'}"
    parser_review = _is_true(row.get("parser_review_required", ""))
    if parser_review and eligibility not in SAFE_PARSER_EXCLUSION_ELIGIBILITY:
        return None, "parser review required"
    if _is_true(row.get("family_conflict_suggestion", "")):
        return None, "cross-family conflict requires source review"
    if _has_existing_edits(row, FINAL_DOCUMENT_FIELDS):
        return None, "pre-existing editable values preserved"

    include = eligibility in {"primary_candidate", "secondary_candidate"}
    values = {
        "version_status_final": VERSION_STATUS_MAP.get(
            str(row.get("version_state_suggestion", "")), ""
        ),
        "session_scope_final": SESSION_SCOPE_MAP.get(
            str(row.get("session_scope_suggestion", "")), ""
        ),
        "offence_family_final": str(row.get("offence_family_suggestion", "")),
        "eligibility_final": "include" if include else "exclude",
        "exclusion_reason_final": "" if include else _document_exclusion_reason(row),
        "reviewer_id": coder_id,
        "review_status": "single_coded_pending_human",
        "review_notes": (
            "Machine-assisted deterministic prefill from protected parsed FIA evidence; "
            "independent official-source review required."
        ),
    }
    if parser_review:
        return values, f"safe deterministic exclusion with parser warning: {eligibility}"
    return values, f"safe deterministic path: {eligibility}"


def _single_number(value: Any) -> str:
    parts = [item.strip() for item in str(value).split("|") if item.strip()]
    return parts[0] if len(parts) == 1 and parts[0].isdigit() else ""


def _location(value: Any) -> str:
    turns = [int(item) for item in str(value).split("|") if item.strip().isdigit()]
    if not turns:
        return ""
    if len(turns) == 1:
        return f"Turn {turns[0]}"
    if turns == list(range(turns[0], turns[-1] + 1)):
        return f"Turns {turns[0]}-{turns[-1]}"
    return "Turns " + ", ".join(str(turn) for turn in turns)


def explicit_fault_language(reason_text: Any, *, secondary: bool = False) -> str:
    """Extract only explicit written responsibility language from the decision reason."""

    text = re.sub(r"\s+", " ", str(reason_text).casefold()).strip()
    if secondary:
        return "not_applicable"
    if re.search(r"\bracing\s+[\"'“”‘’]?incident[\"'“”‘’]?\b", text):
        return "racing_incident"
    if re.search(r"\b(?:both drivers|each driver).{0,80}\b(?:contributed|responsible)\b", text):
        return "shared_fault"
    no_fault_patterns = (
        r"\bno driver\b.{0,100}\b(?:blame|blamed|fault)\b",
        r"\bnone of the drivers\b.{0,100}\b(?:blame|blamed|fault)\b",
        r"\bno one\b.{0,100}\b(?:blame|blamed|fault)\b",
        r"\bneither (?:driver|car|was|were)\b.{0,100}\b(?:blame|blamed|fault)\b",
        r"\bnot (?:through )?the fault of either driver\b",
        r"\bnot able to identify\b.{0,140}\b(?:driver|drivers)\b.{0,140}"
        r"\b(?:blame|blamed|fault)\b",
        r"\b(?:did not|do not|cannot|could not) (?:consider|determine|find|believe)"
        r".{0,100}\b(?:either|any) driver\b.{0,100}\b(?:blame|fault)\b",
    )
    if any(re.search(pattern, text) for pattern in no_fault_patterns):
        return "no_conclusion"
    if (
        re.search(
            r"\b(?:was|is|considered|found|judged|determined|deemed) "
            r"(?:wholly|fully|solely) (?:to blame|at fault|responsible)\b",
            text,
        )
        or re.search(r"\bwholly the fault of\b", text)
        or re.search(
            r"\b(?:admitted|accepted).{0,60}\b(?:collision was his fault|it was his mistake)\b",
            text,
        )
    ):
        return "wholly_to_blame"
    if re.search(
        r"\b(?:was|is|considered|found|judged|determined|deemed) "
        r"predomin(?:antly|ately|antely|atly) (?:to blame|at fault|responsible)\b",
        text,
    ) or re.search(r"\bwhol?ly or pre?d[e]?ominantly? to blame\b", text):
        return "predominantly_to_blame"
    if re.search(
        r"\b(?:was|is|considered|found|judged|determined|deemed) mainly at fault\b",
        text,
    ):
        return "mainly_at_fault"
    return ""


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{_sha256(value.encode('utf-8'))[:16]}"


def _adjudication_exclusion_reason(row: pd.Series) -> str:
    session_scope = str(row.get("session_scope_suggestion", ""))
    family_group = str(row.get("offence_family_group_suggestion", ""))
    family = str(row.get("offence_family_suggestion", ""))
    if session_scope == "out_of_scope_session":
        return "out_of_scope_session"
    if session_scope == "secondary_qualifying" and family_group != "secondary":
        return "outside_secondary_offence_scope"
    if family_group == "excluded" and family:
        return f"excluded_offence_family:{family}"
    return "outside_frozen_primary_secondary_scope"


def _adjudication_prefill(row: pd.Series, coder_id: str) -> tuple[dict[str, str] | None, str]:
    action = str(row.get("candidate_action_suggestion", ""))
    parser_review = _is_true(row.get("parser_review_required", ""))
    eligibility = str(row.get("eligibility_suggestion", ""))
    safe_parser_exclusion = parser_review and eligibility in SAFE_PARSER_EXCLUSION_ELIGIBILITY
    if safe_parser_exclusion:
        action = "review_exclusion"
    if action not in SAFE_ADJUDICATION_ACTIONS:
        return None, f"manual adjudication path: {action or 'blank'}"
    if parser_review and not safe_parser_exclusion:
        return None, "parser review required"
    if _is_true(row.get("family_conflict_suggestion", "")):
        return None, "cross-family conflict requires source review"
    if _has_existing_edits(row, FINAL_ADJUDICATION_FIELDS):
        return None, "pre-existing editable values preserved"

    primary = action == "review_primary_adjudication"
    secondary = action == "review_secondary_adjudication"
    include = primary or secondary
    instance_id = str(row["adjudication_instance_id"])
    fault_language = explicit_fault_language(row.get("reason_text", ""), secondary=secondary)
    values = {
        "adjudication_id_final": _stable_id("adj", instance_id) if include else "",
        "incident_id_final": _stable_id("incident-src", instance_id) if include else "",
        "accused_driver_number_final": str(row.get("driver_number_suggestion", "")),
        "affected_driver_numbers_final": str(row.get("affected_driver_numbers_suggestion", "")),
        "session_type_final": str(row.get("session_type_suggestion", "")),
        "lap_number_final": _single_number(row.get("lap_numbers_suggestion", "")),
        "location_final": _location(row.get("turn_numbers_suggestion", "")),
        "incident_family_final": str(row.get("offence_family_suggestion", "")),
        "outcome_family_final": str(row.get("outcome_family_suggestion", "")),
        "penalty_seconds_final": str(row.get("penalty_seconds_suggestion", "")),
        "penalty_points_final": str(row.get("penalty_points_suggestion", "")),
        "grid_places_final": str(row.get("grid_places_suggestion", "")),
        "fault_language_final": fault_language if include else "not_applicable",
        "include_primary_final": "true" if primary else "false",
        "include_secondary_final": "true" if secondary else "false",
        "exclusion_reason_final": "" if include else _adjudication_exclusion_reason(row),
        "coder_id": coder_id,
        "review_status": "single_coded_pending_human",
        "coding_notes": (
            "Machine-assisted deterministic first pass from protected parsed FIA evidence. "
            + ("Incident ID is source-unique pending cross-document grouping. " if include else "")
            + (
                "Explicit fault language was not safely extractable. "
                if primary and not fault_language
                else ""
            )
            + "Independent official-source review required."
        ),
    }
    if safe_parser_exclusion:
        return values, f"safe deterministic exclusion with parser warning: {eligibility}"
    return values, f"safe deterministic path: {action}"


def _apply_values(frame: pd.DataFrame, index: Any, values: dict[str, str]) -> list[str]:
    populated: list[str] = []
    for field, value in values.items():
        frame.at[index, field] = value
        if value:
            populated.append(field)
    return populated


def build_first_pass_frames(
    documents: pd.DataFrame,
    adjudications: pd.DataFrame,
    exclusion_qa: pd.DataFrame,
    *,
    coder_id: str = DEFAULT_CODER_ID,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Prefill safe paths while retaining every exception for source-level review."""

    document_output = documents.copy()
    adjudication_output = adjudications.copy()
    qa_output = exclusion_qa.copy()
    audit_rows: list[dict[str, str]] = []

    for index, row in documents.iterrows():
        values, basis = _document_prefill(row, coder_id)
        populated = _apply_values(document_output, index, values) if values else []
        audit_rows.append(
            {
                "queue_name": "documents",
                "row_id": str(row["document_review_id"]),
                "event_id": str(row.get("event_id", "")),
                "source_url": str(row.get("source_url", "")),
                "first_pass_action": "prefilled" if values else "unresolved",
                "action_basis": basis,
                "fields_populated": "|".join(populated),
            }
        )

    for index, row in adjudications.iterrows():
        values, basis = _adjudication_prefill(row, coder_id)
        populated = _apply_values(adjudication_output, index, values) if values else []
        audit_rows.append(
            {
                "queue_name": "adjudications",
                "row_id": str(row["adjudication_instance_id"]),
                "event_id": str(row.get("event_id", "")),
                "source_url": str(row.get("source_url", "")),
                "first_pass_action": "prefilled" if values else "unresolved",
                "action_basis": basis,
                "fields_populated": "|".join(populated),
            }
        )

    for _, row in exclusion_qa.iterrows():
        audit_rows.append(
            {
                "queue_name": "exclusion_qa",
                "row_id": str(row["exclusion_qa_id"]),
                "event_id": str(row.get("event_id", "")),
                "source_url": str(row.get("source_url", "")),
                "first_pass_action": "unresolved",
                "action_basis": "source-level exclusion audit cannot be auto-confirmed",
                "fields_populated": "",
            }
        )

    audit = pd.DataFrame(audit_rows)
    counts = (
        audit.groupby(["queue_name", "first_pass_action"], dropna=False)
        .size()
        .unstack(fill_value=0)
    )
    summary = {
        queue: {
            "prefilled_rows": int(counts.loc[queue].get("prefilled", 0)),
            "unresolved_rows": int(counts.loc[queue].get("unresolved", 0)),
        }
        for queue in ("documents", "adjudications", "exclusion_qa")
    }
    summary["adjudications"]["explicit_fault_language_rows"] = int(
        adjudication_output["fault_language_final"]
        .isin(
            {
                "wholly_to_blame",
                "predominantly_to_blame",
                "mainly_at_fault",
                "shared_fault",
                "racing_incident",
                "no_conclusion",
            }
        )
        .sum()
    )
    return document_output, adjudication_output, qa_output, audit, summary


def _workspace_digest(payloads: dict[str, bytes]) -> str:
    names = [
        WORKSPACE_MANIFEST_FILENAME,
        WORKSPACE_DOCUMENT_FILENAME,
        WORKSPACE_ADJUDICATION_FILENAME,
        WORKSPACE_EXCLUSION_QA_FILENAME,
    ]
    return _sha256(b"\n".join(name.encode("utf-8") + b":" + payloads[name] for name in names))


def build_first_pass_payloads(
    workspace_directory: Path,
    *,
    coder_id: str = DEFAULT_CODER_ID,
) -> tuple[dict[str, bytes], dict[str, Any]]:
    """Build deterministic files and a manifest for a separate first-pass workspace."""

    manifest_path = workspace_directory / WORKSPACE_MANIFEST_FILENAME
    workspace_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if workspace_manifest.get("workspace_id") != workspace_directory.name:
        raise ValueError("Workspace ID does not match the source directory name")
    documents = _read_csv(workspace_directory / WORKSPACE_DOCUMENT_FILENAME)
    adjudications = _read_csv(workspace_directory / WORKSPACE_ADJUDICATION_FILENAME)
    exclusion_qa = _read_csv(workspace_directory / WORKSPACE_EXCLUSION_QA_FILENAME)
    frames = build_first_pass_frames(
        documents,
        adjudications,
        exclusion_qa,
        coder_id=coder_id,
    )
    document_output, adjudication_output, qa_output, audit, summary = frames
    parser_warning_inclusions = {
        "documents": int(
            (
                document_output["parser_review_required"].astype(str).str.casefold().eq("true")
                & document_output["eligibility_final"].eq("include")
            ).sum()
        ),
        "adjudications": int(
            (
                adjudication_output["parser_review_required"].astype(str).str.casefold().eq("true")
                & (
                    adjudication_output["include_primary_final"].eq("true")
                    | adjudication_output["include_secondary_final"].eq("true")
                )
            ).sum()
        ),
    }
    if any(parser_warning_inclusions.values()):
        raise ValueError("Parser-warning inclusions cannot be prefilled")
    payloads = {
        WORKSPACE_MANIFEST_FILENAME: manifest_path.read_bytes(),
        WORKSPACE_DOCUMENT_FILENAME: _csv_bytes(document_output),
        WORKSPACE_ADJUDICATION_FILENAME: _csv_bytes(adjudication_output),
        WORKSPACE_EXCLUSION_QA_FILENAME: _csv_bytes(qa_output),
        FIRST_PASS_AUDIT_FILENAME: _csv_bytes(audit),
    }
    source_digest = workspace_input_sha256(workspace_directory)
    output_digest = _workspace_digest(payloads)
    first_pass_id = (
        "first-pass-"
        + _sha256(
            (
                FIRST_PASS_SCHEMA_VERSION
                + "\n"
                + source_digest
                + "\n"
                + output_digest
                + "\n"
                + coder_id
            ).encode("utf-8")
        )[:12]
    )
    manifest = {
        "schema_version": FIRST_PASS_SCHEMA_VERSION,
        "first_pass_id": first_pass_id,
        "workspace_id": workspace_manifest["workspace_id"],
        "coder_id": coder_id,
        "source_workspace_sha256": source_digest,
        "output_workspace_sha256": output_digest,
        "summary": summary,
        "controls": {
            "parser_warning_inclusion_rows_prefilled": parser_warning_inclusions,
            "parser_warning_exclusion_rows_prefilled": {
                queue: int(
                    (
                        audit["queue_name"].eq(queue)
                        & audit["first_pass_action"].eq("prefilled")
                        & audit["action_basis"].str.startswith(
                            "safe deterministic exclusion with parser warning:"
                        )
                    ).sum()
                )
                for queue in ("documents", "adjudications")
            },
            "family_conflict_rows_prefilled": 0,
            "exclusion_qa_rows_prefilled": 0,
            "incident_id_strategy": "source_unique_pending_cross_document_grouping",
            "review_status": "single_coded_pending_human",
            "analytical_release_authorized": False,
        },
        "interpretation_boundary": (
            "This deterministic, machine-assisted first pass is a review aid. It does not count "
            "as independent review and cannot authorize analytical or report release."
        ),
        "outputs": {
            name: {
                "sha256": _sha256(payload),
                "row_count": (
                    len(document_output)
                    if name == WORKSPACE_DOCUMENT_FILENAME
                    else len(adjudication_output)
                    if name == WORKSPACE_ADJUDICATION_FILENAME
                    else len(qa_output)
                    if name == WORKSPACE_EXCLUSION_QA_FILENAME
                    else len(audit)
                    if name == FIRST_PASS_AUDIT_FILENAME
                    else 1
                ),
            }
            for name, payload in payloads.items()
        },
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return {**payloads, FIRST_PASS_MANIFEST_FILENAME: manifest_bytes}, manifest


def write_first_pass_workspace(
    workspace_directory: Path,
    output_root: Path,
    *,
    coder_id: str = DEFAULT_CODER_ID,
) -> tuple[Path, dict[str, Any], bool]:
    """Write or byte-verify the deterministic first-pass workspace."""

    payloads, manifest = build_first_pass_payloads(
        workspace_directory,
        coder_id=coder_id,
    )
    output_directory = output_root / workspace_directory.name
    created = not output_directory.exists()
    output_directory.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        path = output_directory / name
        if path.exists() and path.read_bytes() != payload:
            raise FileExistsError(f"First-pass workspace differs from rebuild: {path}")
        path.write_bytes(payload)
    return output_directory, manifest, created
