"""Source-explicit incident context candidates for Study v2 review and matching."""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from f1stewards.config import PROJECT_ROOT
from f1stewards.incident_clock import DEFAULT_OUTPUT_ROOT as CLOCK_OUTPUT_ROOT
from f1stewards.study_v2_review import MODEL_WORKSPACE

DEFAULT_REFERRAL_DIR = (
    PROJECT_ROOT / "data" / "manual" / "study_v2_referrals" / "referrals-5d0559ad2878"
)
DEFAULT_CLOCK_DIR = CLOCK_OUTPUT_ROOT / "incident-clock-3dc8bb350308"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "manual" / "study_v2_incident_context"


@dataclass(frozen=True)
class IncidentContextBuild:
    run_id: str
    output_dir: Path
    cases: int
    current_exact_laps: int
    new_explicit_lap_candidates: int
    new_clock_single_lap_candidates: int


def _sentences(text: str) -> list[str]:
    return [value.strip() for value in re.split(r"(?<=[.!?])\s+|\n+", text) if value.strip()]


def _evidence(text: str, patterns: list[str]) -> list[str]:
    compiled = [re.compile(pattern, re.I) for pattern in patterns]
    return [sentence for sentence in _sentences(text) if any(p.search(sentence) for p in compiled)]


def extract_context_candidates(reason_text: str, fact_text: str = "") -> dict[str, object]:
    text = " ".join(value for value in (fact_text, reason_text) if value)
    evidence: dict[str, list[str]] = {}

    first_lap = _evidence(text, [r"\bfirst lap\b", r"\blap\s*1\b"])
    if first_lap:
        evidence["first_lap"] = first_lap
    wet = _evidence(text, [r"\bwet\b", r"\bdamp\b", r"\brain(?:ing)?\b"])
    if wet:
        evidence["wet_track"] = wet
    restart = _evidence(
        text,
        [r"\bsafety car restart\b", r"\brestart after (?:the )?safety car\b", r"\bVSC restart\b"],
    )
    if restart:
        evidence["safety_car_restart"] = restart

    inside = _evidence(text, [r"\bon the inside\b", r"\binside line\b"])
    outside = _evidence(text, [r"\bon the outside\b", r"\boutside line\b"])
    if inside and outside:
        attacker_line = "ambiguous_both_lines_mentioned"
    elif inside:
        attacker_line = "inside"
    elif outside:
        attacker_line = "outside"
    else:
        attacker_line = "unknown"
    if inside or outside:
        evidence["attacker_line"] = [*inside, *outside]

    overlap_patterns = {
        "front_axle_ahead": [r"front axle.*(?:ahead|in front)", r"ahead of .*mirror"],
        "alongside": [r"\balongside\b", r"side by side"],
        "no_overlap": [r"not (?:sufficiently )?alongside", r"no (?:significant )?overlap"],
    }
    overlap_hits = {
        label: _evidence(text, patterns) for label, patterns in overlap_patterns.items()
    }
    overlap_labels = [label for label, spans in overlap_hits.items() if spans]
    overlap = (
        overlap_labels[0]
        if len(overlap_labels) == 1
        else ("ambiguous" if overlap_labels else "unknown")
    )
    if overlap_labels:
        evidence["overlap"] = [span for label in overlap_labels for span in overlap_hits[label]]

    corner_phases = {
        "entry": _evidence(text, [r"\bcorner entry\b", r"\bon entry\b"]),
        "apex": _evidence(text, [r"\bapex\b"]),
        "exit": _evidence(text, [r"\bcorner exit\b", r"\bon (?:the )?exit\b"]),
    }
    phase_labels = [label for label, spans in corner_phases.items() if spans]
    if phase_labels:
        evidence["corner_phase"] = [span for label in phase_labels for span in corner_phases[label]]

    control_hits = _evidence(
        text,
        [
            r"\blost control\b",
            r"\bnot in control\b",
            r"\blocked (?:a |the )?wheel",
            r"\bmissed the apex\b",
        ],
    )
    if control_hits:
        evidence["control_error"] = control_hits

    return {
        "first_lap_candidate": bool(first_lap),
        "wet_track_candidate": bool(wet),
        "safety_car_restart_candidate": bool(restart),
        "attacker_line_candidate": attacker_line,
        "overlap_candidate": overlap,
        "corner_phase_candidate": "|".join(phase_labels) if phase_labels else "unknown",
        "control_error_candidate": bool(control_hits),
        "context_evidence_json": json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        "context_review_status": "machine_extracted_pending_human_review",
    }


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def build_incident_context_candidates(
    *,
    workspace: Path = MODEL_WORKSPACE,
    referral_dir: Path = DEFAULT_REFERRAL_DIR,
    clock_dir: Path = DEFAULT_CLOCK_DIR,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> IncidentContextBuild:
    adjudications = pd.read_csv(
        workspace / "adjudication_coding_worklist.csv", keep_default_na=False, low_memory=False
    )
    cases = adjudications.loc[
        adjudications["include_primary_final"].astype(str).str.casefold().eq("true")
    ].copy()
    links = pd.read_csv(
        referral_dir / "adjudication_episode_links.csv", keep_default_na=False, low_memory=False
    )
    episodes = pd.read_csv(
        referral_dir / "referral_episodes.csv", keep_default_na=False, low_memory=False
    )
    episode_fields = episodes[
        [
            "referral_episode_id",
            "incident_lap_explicit",
            "message_lap_min",
            "message_lap_max",
            "process_statuses",
            "messages_json",
        ]
    ]
    link_fields = links[
        ["adjudication_instance_id", "referral_episode_id", "link_status", "link_score"]
    ].merge(episode_fields, on="referral_episode_id", how="left", validate="many_to_one")
    clock = pd.read_csv(
        clock_dir / "incident_clock_windows.csv", keep_default_na=False, low_memory=False
    )
    clock_fields = clock[
        [
            "adjudication_instance_id",
            "clock_lower_utc",
            "clock_upper_utc",
            "possible_accused_laps",
            "possible_lap_count",
            "single_lap_candidate",
            "mapping_basis",
        ]
    ].rename(columns={"mapping_basis": "clock_mapping_basis"})
    cases = cases.merge(
        link_fields, on="adjudication_instance_id", how="left", validate="one_to_one"
    )
    cases = cases.merge(
        clock_fields, on="adjudication_instance_id", how="left", validate="one_to_one"
    )

    records: list[dict[str, object]] = []
    for _, case in cases.iterrows():
        context = extract_context_candidates(str(case["reason_text"]), str(case["fact_text"]))
        current_lap = str(case["lap_number_final"])
        episode_lap = case["incident_lap_explicit"]
        link_status = str(case.get("link_status", ""))
        possible_clock_laps = [
            int(value)
            for value in str(case.get("possible_accused_laps", "")).split("|")
            if value.isdigit()
        ]
        clock_single = str(case.get("single_lap_candidate", ""))
        if current_lap.isdigit():
            lap_candidate: int | str = int(current_lap)
            lap_basis = "model_reviewed_source_or_timing"
        elif (
            pd.notna(episode_lap)
            and str(episode_lap) not in {"", "nan"}
            and (not possible_clock_laps or int(float(episode_lap)) in possible_clock_laps)
        ):
            lap_candidate = int(float(episode_lap))
            lap_basis = (
                "race_control_explicit_lap_high_confidence_link"
                if link_status == "high_confidence_algorithmic"
                else "race_control_explicit_lap_candidate_link"
            )
        elif clock_single.isdigit():
            lap_candidate = int(clock_single)
            lap_basis = "fia_incident_clock_single_lap_interval"
        else:
            lap_candidate = ""
            lap_basis = "unresolved"
        if lap_candidate == 1:
            context["first_lap_candidate"] = True
        records.append(
            {
                "adjudication_instance_id": case["adjudication_instance_id"],
                "adjudication_id": case["adjudication_id_final"],
                "incident_id": case["incident_id_final"],
                "document_id": case["document_id"],
                "event_id": case["event_id"],
                "session_type": case["session_type_final"],
                "incident_family": case["incident_family_final"],
                "accused_driver_number": case["accused_driver_number_final"],
                "affected_driver_numbers": case["affected_driver_numbers_final"],
                "location_model_reviewed": case["location_final"],
                "lap_model_reviewed": case["lap_number_final"],
                "incident_lap_candidate": lap_candidate,
                "incident_lap_basis": lap_basis,
                "incident_lap_window_min": (
                    min(possible_clock_laps) if possible_clock_laps else ""
                ),
                "incident_lap_window_max": (
                    max(possible_clock_laps) if possible_clock_laps else ""
                ),
                "possible_accused_laps": "|".join(str(value) for value in possible_clock_laps),
                "clock_lower_utc": case.get("clock_lower_utc", ""),
                "clock_upper_utc": case.get("clock_upper_utc", ""),
                "clock_mapping_basis": case.get("clock_mapping_basis", ""),
                "referral_episode_id": case.get("referral_episode_id", ""),
                "referral_link_status": link_status,
                "referral_link_score": case.get("link_score", ""),
                "message_lap_upper_bound": case.get("message_lap_min", ""),
                "message_lap_last": case.get("message_lap_max", ""),
                "race_control_process_statuses": case.get("process_statuses", ""),
                "race_control_messages_json": case.get("messages_json", ""),
                **context,
                "timing_review_status": "pending_human_review",
                "context_reviewer_id": "",
                "context_reviewed_at": "",
                "context_review_notes": "",
            }
        )
    frame = pd.DataFrame(records).sort_values(
        ["event_id", "session_type", "adjudication_instance_id"]
    )
    digest = hashlib.sha256(_csv_bytes(frame)).hexdigest()[:12]
    run_id = f"incident-context-{digest}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    frame.to_csv(output_dir / "incident_context_candidates.csv", index=False)
    current_exact = int(frame["lap_model_reviewed"].astype(str).str.fullmatch(r"\d+").sum())
    new_explicit = int(
        (
            frame["lap_model_reviewed"].eq("")
            & frame["incident_lap_basis"].str.startswith("race_control_explicit")
        ).sum()
    )
    new_clock_single = int(
        (
            frame["lap_model_reviewed"].eq("")
            & frame["incident_lap_basis"].eq("fia_incident_clock_single_lap_interval")
        ).sum()
    )
    manifest = {
        "schema_version": "study-v2-incident-context-v1",
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "parent_referral_run": referral_dir.name,
        "parent_clock_run": clock_dir.name,
        "case_count": len(frame),
        "current_exact_lap_count": current_exact,
        "new_race_control_explicit_lap_candidates": new_explicit,
        "new_clock_single_lap_candidates": new_clock_single,
        "machine_context_fields_are_final": False,
        "human_validation_complete": False,
        "sha256": hashlib.sha256(_csv_bytes(frame)).hexdigest(),
        "limitation": (
            "Context extraction preserves explicit source phrases but does not resolve "
            "actor-specific geometry. Race Control message laps are upper bounds unless the "
            "incident lap is explicit."
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return IncidentContextBuild(
        run_id=run_id,
        output_dir=output_dir,
        cases=len(frame),
        current_exact_laps=current_exact,
        new_explicit_lap_candidates=new_explicit,
        new_clock_single_lap_candidates=new_clock_single,
    )
