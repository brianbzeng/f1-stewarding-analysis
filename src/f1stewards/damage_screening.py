"""Incident-participant harm screening and source-research queues for Study v2."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from f1stewards.config import PROJECT_ROOT, load_yaml
from f1stewards.incident_context import DEFAULT_OUTPUT_ROOT as CONTEXT_OUTPUT_ROOT
from f1stewards.referral_funnel import DEFAULT_OUTPUT_ROOT as REFERRAL_OUTPUT_ROOT
from f1stewards.study_v2_review import DEFAULT_DATABASE

DEFAULT_REFERRAL_DIR = REFERRAL_OUTPUT_ROOT / "referrals-5d0559ad2878"
DEFAULT_CONTEXT_DIR = CONTEXT_OUTPUT_ROOT / "incident-context-a1de9ac2c8ea"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "manual" / "study_v2_damage"
DEFAULT_EVIDENCE_SEED = PROJECT_ROOT / "config" / "damage_evidence_seed.yml"

NON_FINISH_DAMAGE_STATUSES = {
    "Accident",
    "Collision",
    "Collision damage",
    "Damage",
    "Front wing",
    "Puncture",
    "Rear wing",
    "Retired",
    "Spun off",
    "Suspension",
    "Tyre",
    "Undertray",
    "Wheel",
}

EVIDENCE_REVIEW_FIELDS = [
    "independent_reviewer_id",
    "independent_reviewed_at",
    "reviewed_damage_state",
    "reviewed_damaged_components",
    "reviewed_incident_causality",
    "reviewed_repair_action",
    "reviewed_incident_responsive_stop",
    "reviewed_incident_caused_retirement",
    "reviewed_attributed_pace_loss_seconds_per_lap",
    "reviewed_evidence_grade",
    "independent_review_status",
    "independent_review_notes",
]


@dataclass(frozen=True)
class DamageScreeningBuild:
    run_id: str
    output_dir: Path
    collision_decision_rows: int
    candidate_incidents: int
    participant_rows: int
    timing_eligible_rows: int


def _pipe_numbers(value: object) -> set[int]:
    return {int(part) for part in str(value).split("|") if part.isdigit()}


def _canonical_incident_key(row: pd.Series) -> str:
    episode = str(row.get("referral_episode_id", ""))
    status = str(row.get("link_status", ""))
    if episode and status not in {"ambiguous_pending_review", "unmatched"}:
        return episode
    return str(row["incident_id"])


def build_incident_participants(links: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    collisions = links.loc[links["incident_family"].eq("causing_collision")].copy()
    collisions["canonical_incident_key"] = collisions.apply(_canonical_incident_key, axis=1)
    context_fields = context[
        [
            "adjudication_instance_id",
            "incident_lap_candidate",
            "incident_lap_basis",
            "first_lap_candidate",
            "clock_lower_utc",
            "clock_upper_utc",
        ]
    ]
    collisions = collisions.merge(
        context_fields, on="adjudication_instance_id", how="left", validate="one_to_one"
    )
    records: list[dict[str, Any]] = []
    for incident_key, group in collisions.groupby("canonical_incident_key", sort=True):
        participants = set()
        for _, row in group.iterrows():
            participants.update(_pipe_numbers(row["adjudication_car_numbers"]))
            if "episode_car_numbers" in row and row["link_status"] not in {
                "ambiguous_pending_review",
                "unmatched",
            }:
                participants.update(_pipe_numbers(row["episode_car_numbers"]))
        lap_values = {
            int(float(value))
            for value in group["incident_lap_candidate"]
            if str(value) not in {"", "nan"}
        }
        clock_pairs = {
            (str(row["clock_lower_utc"]), str(row["clock_upper_utc"]))
            for _, row in group.iterrows()
            if str(row["clock_lower_utc"]) and str(row["clock_upper_utc"])
        }
        clock_lower_utc, clock_upper_utc = (
            next(iter(clock_pairs)) if len(clock_pairs) == 1 else ("", "")
        )
        incident_lap = next(iter(lap_values)) if len(lap_values) == 1 else None
        for participant in sorted(participants):
            accused_rows = group.loc[
                group["accused_driver_number"].astype(str).eq(str(participant))
            ]
            affected_rows = group.loc[
                group["affected_driver_numbers"].map(
                    lambda value, number=participant: number in _pipe_numbers(value)
                )
            ]
            role = (
                "accused_and_affected"
                if not accused_rows.empty and not affected_rows.empty
                else "accused"
                if not accused_rows.empty
                else "affected"
            )
            records.append(
                {
                    "harm_record_id": hashlib.sha256(
                        f"{incident_key}|{participant}".encode()
                    ).hexdigest()[:20],
                    "canonical_incident_key": incident_key,
                    "incident_grouping_status": (
                        "race_control_episode_candidate_pending_review"
                        if str(incident_key).startswith("referral-")
                        else "existing_incident_id"
                    ),
                    "event_id": group.iloc[0]["event_id"],
                    "session_type": group.iloc[0]["session_type"],
                    "participant_driver_number": participant,
                    "participant_role": role,
                    "all_participant_driver_numbers": "|".join(
                        str(number) for number in sorted(participants)
                    ),
                    "participant_count": len(participants),
                    "adjudication_ids": "|".join(sorted(set(group["adjudication_id"]))),
                    "document_ids": "|".join(sorted(set(group["document_id"]))),
                    "outcome_families": "|".join(sorted(set(group["outcome_family"]))),
                    "incident_lap_candidate": incident_lap if incident_lap is not None else "",
                    "incident_lap_conflict": len(lap_values) > 1,
                    "incident_lap_bases": "|".join(
                        sorted(set(str(value) for value in group["incident_lap_basis"] if value))
                    ),
                    "clock_lower_utc": clock_lower_utc,
                    "clock_upper_utc": clock_upper_utc,
                    "clock_window_conflict": len(clock_pairs) > 1,
                    "referral_link_statuses": "|".join(
                        sorted(set(str(value) for value in group["link_status"]))
                    ),
                }
            )
    return pd.DataFrame(records)


def _is_clean_lap(row: pd.Series) -> bool:
    return bool(row.get("is_accurate")) and (
        str(row.get("track_status", "")) == "1"
        and pd.notna(row.get("lap_time_seconds"))
        and pd.isna(row.get("pit_in_time_seconds"))
        and pd.isna(row.get("pit_out_time_seconds"))
        and float(row.get("lap_number", 0)) > 1
    )


def summarize_participant_timing(
    participant_laps: pd.DataFrame,
    incident_lap: int | None,
    teammate_laps: pd.DataFrame | None = None,
) -> dict[str, Any]:
    empty = {
        "position_before": None,
        "position_after": None,
        "observed_position_change": None,
        "pit_signal_lap": None,
        "clean_laps_before": 0,
        "clean_laps_after": 0,
        "matched_reference_laps_before": 0,
        "matched_reference_laps_after": 0,
        "persistent_pace_primary_eligible": False,
    }
    if incident_lap is None or participant_laps.empty:
        return empty
    laps = participant_laps.sort_values("lap_number").copy()
    clean = laps.loc[laps.apply(_is_clean_lap, axis=1)]
    before = clean.loc[clean["lap_number"].lt(incident_lap)].tail(8)
    after = clean.loc[clean["lap_number"].gt(incident_lap)].head(8)
    pre_position = laps.loc[laps["lap_number"].lt(incident_lap), "position"].dropna()
    post_position = laps.loc[laps["lap_number"].ge(incident_lap), "position"].dropna()
    pit_rows = laps.loc[
        laps["lap_number"].between(incident_lap, incident_lap + 2)
        & laps["pit_in_time_seconds"].notna()
    ]
    reference_before = 0
    reference_after = 0
    if teammate_laps is not None and not teammate_laps.empty:
        reference_clean_numbers = set(
            teammate_laps.loc[teammate_laps.apply(_is_clean_lap, axis=1), "lap_number"]
        )
        reference_before = int(before["lap_number"].isin(reference_clean_numbers).sum())
        reference_after = int(after["lap_number"].isin(reference_clean_numbers).sum())
    position_before = float(pre_position.iloc[-1]) if not pre_position.empty else None
    position_after = float(post_position.iloc[0]) if not post_position.empty else None
    return {
        "position_before": position_before,
        "position_after": position_after,
        "observed_position_change": (
            position_after - position_before
            if position_before is not None and position_after is not None
            else None
        ),
        "pit_signal_lap": int(pit_rows.iloc[0]["lap_number"]) if not pit_rows.empty else None,
        "clean_laps_before": len(before),
        "clean_laps_after": len(after),
        "matched_reference_laps_before": reference_before,
        "matched_reference_laps_after": reference_after,
        "persistent_pace_primary_eligible": (
            len(before) >= 5 and len(after) >= 5 and reference_before >= 5 and reference_after >= 5
        ),
    }


def map_utc_window_to_participant_laps(
    laps: pd.DataFrame,
    clock_lower_utc: str,
    clock_upper_utc: str,
    *,
    pre_start_tolerance_seconds: int = 300,
) -> tuple[int, ...]:
    if laps.empty or not clock_lower_utc or not clock_upper_utc:
        return ()
    lower = pd.Timestamp(clock_lower_utc)
    upper = pd.Timestamp(clock_upper_utc)
    work = laps.sort_values("lap_number").copy()
    work["start"] = pd.to_datetime(work["lap_start_timestamp"], utc=True, errors="coerce")
    work = work.loc[work["start"].notna()].copy()
    if work.empty:
        return ()
    work["end"] = work["start"].shift(-1)
    last_index = work.index[-1]
    fallback_seconds = work.loc[last_index, "lap_time_seconds"]
    if pd.isna(fallback_seconds):
        fallback_seconds = 120
    final_end = work.loc[last_index, "start"] + timedelta(seconds=float(fallback_seconds))
    work["end"] = work["end"].astype("datetime64[ns, UTC]")
    work.at[last_index, "end"] = final_end
    overlap = work.loc[work["start"].lt(upper) & work["end"].gt(lower)]
    if overlap.empty:
        first = work.iloc[0]
        if (
            first["start"] - pd.Timedelta(seconds=pre_start_tolerance_seconds)
            <= lower
            < first["start"]
            and int(first["lap_number"]) == 1
        ):
            overlap = work.iloc[[0]]
    return tuple(sorted({int(value) for value in overlap["lap_number"]}))


def _load_seed(path: Path) -> pd.DataFrame:
    payload = load_yaml(path).get("damage_evidence_seed")
    if not isinstance(payload, dict) or payload.get("schema_version") != "damage_evidence_seed_v1":
        raise ValueError("Damage evidence seed must use damage_evidence_seed_v1")
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("Damage evidence seed records must be a list")
    return pd.json_normalize(records)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def build_damage_screening(
    *,
    database_path: Path = DEFAULT_DATABASE,
    referral_dir: Path = DEFAULT_REFERRAL_DIR,
    context_dir: Path = DEFAULT_CONTEXT_DIR,
    evidence_seed: Path = DEFAULT_EVIDENCE_SEED,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> DamageScreeningBuild:
    links = pd.read_csv(
        referral_dir / "adjudication_episode_links.csv", keep_default_na=False, low_memory=False
    )
    episodes = pd.read_csv(
        referral_dir / "referral_episodes.csv", keep_default_na=False, low_memory=False
    )
    links = links.merge(
        episodes[["referral_episode_id", "car_numbers"]].rename(
            columns={"car_numbers": "episode_car_numbers"}
        ),
        on="referral_episode_id",
        how="left",
        validate="many_to_one",
    )
    context = pd.read_csv(
        context_dir / "incident_context_candidates.csv", keep_default_na=False, low_memory=False
    )
    participants = build_incident_participants(links, context)
    with duckdb.connect(str(database_path), read_only=True) as connection:
        results = connection.execute(
            "SELECT * FROM raw.fastf1_session_results WHERE session_type IN ('Race', 'Sprint')"
        ).fetchdf()
        laps = connection.execute(
            "SELECT * FROM raw.fastf1_session_laps WHERE session_type IN ('Race', 'Sprint')"
        ).fetchdf()
    results_keyed = results.set_index(["event_id", "session_type", "driver_number"])
    timing_records: list[dict[str, Any]] = []
    for _, participant in participants.iterrows():
        key = (
            participant["event_id"],
            participant["session_type"],
            int(participant["participant_driver_number"]),
        )
        result = results_keyed.loc[key] if key in results_keyed.index else None
        driver_laps = laps.loc[
            laps["event_id"].eq(participant["event_id"])
            & laps["session_type"].eq(participant["session_type"])
            & laps["driver_number"].eq(participant["participant_driver_number"])
        ]
        teammate_laps = pd.DataFrame()
        team_name = str(result["team_name"]) if result is not None else ""
        if team_name:
            teammate_numbers = results.loc[
                results["event_id"].eq(participant["event_id"])
                & results["session_type"].eq(participant["session_type"])
                & results["team_name"].eq(team_name)
                & results["driver_number"].ne(participant["participant_driver_number"]),
                "driver_number",
            ]
            if not teammate_numbers.empty:
                teammate_laps = laps.loc[
                    laps["event_id"].eq(participant["event_id"])
                    & laps["session_type"].eq(participant["session_type"])
                    & laps["driver_number"].eq(int(teammate_numbers.iloc[0]))
                ]
        raw_lap = str(participant["incident_lap_candidate"])
        adjudication_lap = int(float(raw_lap)) if raw_lap not in {"", "nan"} else None
        participant_laps = map_utc_window_to_participant_laps(
            driver_laps,
            str(participant["clock_lower_utc"]),
            str(participant["clock_upper_utc"]),
        )
        if len(participant_laps) == 1:
            incident_lap = participant_laps[0]
            participant_lap_basis = "fia_clock_participant_single_lap_interval"
        elif not participant_laps and adjudication_lap is not None:
            incident_lap = adjudication_lap
            participant_lap_basis = "adjudication_lap_candidate"
        else:
            incident_lap = None
            participant_lap_basis = (
                "fia_clock_participant_multi_lap_window" if participant_laps else "unresolved"
            )
        timing = summarize_participant_timing(driver_laps, incident_lap, teammate_laps)
        status = str(result["status"]) if result is not None else ""
        screening_score = 0
        screening_reasons: list[str] = []
        if status in NON_FINISH_DAMAGE_STATUSES:
            screening_score += 5
            screening_reasons.append("damage_or_incident_retirement_status")
        if timing["pit_signal_lap"] is not None:
            screening_score += 3
            screening_reasons.append("pit_within_two_laps_of_candidate_incident")
        if incident_lap is not None:
            screening_score += 2
            screening_reasons.append("incident_lap_available")
        if participant["participant_count"] > 2:
            screening_score += 2
            screening_reasons.append("multi_car_incident")
        position_change = timing["observed_position_change"]
        if position_change is not None and position_change >= 3:
            screening_score += 2
            screening_reasons.append("observed_drop_of_three_or_more_positions")
        timing_records.append(
            {
                **participant.to_dict(),
                "driver_name": str(result["driver_name"]) if result is not None else "",
                "abbreviation": str(result["abbreviation"]) if result is not None else "",
                "team_name": team_name,
                "grid_position": result["grid_position"] if result is not None else None,
                "finish_position": result["finish_position"] if result is not None else None,
                "classification_status": status,
                "classification_damage_signal": status in NON_FINISH_DAMAGE_STATUSES,
                "laps_completed": result["laps_completed"] if result is not None else None,
                "participant_lap_candidate": incident_lap if incident_lap is not None else "",
                "possible_participant_laps": "|".join(str(value) for value in participant_laps),
                "participant_lap_basis": participant_lap_basis,
                **timing,
                "screening_score": screening_score,
                "screening_priority": (
                    "high" if screening_score >= 6 else "medium" if screening_score >= 3 else "low"
                ),
                "screening_reasons": "|".join(screening_reasons),
                "damage_state": "unknown",
                "damage_inference_status": "timing_screen_only_not_damage_evidence",
                "timing_review_status": "pending_human_review",
            }
        )
    screening = pd.DataFrame(timing_records).sort_values(
        ["screening_score", "event_id", "canonical_incident_key", "participant_driver_number"],
        ascending=[False, True, True, True],
    )
    screening["team_source_search_terms"] = screening.apply(
        lambda row: (
            f"{row['event_id']} {row['driver_name']} {row['team_name']} race report "
            "damage collision puncture front wing floor retirement"
        ),
        axis=1,
    )
    screening["formula1_source_search_terms"] = screening.apply(
        lambda row: (
            f"site:formula1.com/en/latest {row['event_id']} {row['driver_name']} "
            "damage collision puncture pit stop retirement"
        ),
        axis=1,
    )
    research_queue = screening[
        [
            "harm_record_id",
            "canonical_incident_key",
            "event_id",
            "session_type",
            "participant_driver_number",
            "driver_name",
            "team_name",
            "participant_role",
            "all_participant_driver_numbers",
            "incident_lap_candidate",
            "participant_lap_candidate",
            "possible_participant_laps",
            "participant_lap_basis",
            "classification_status",
            "pit_signal_lap",
            "observed_position_change",
            "screening_score",
            "screening_priority",
            "screening_reasons",
            "team_source_search_terms",
            "formula1_source_search_terms",
        ]
    ].copy()
    for field in (
        "source_url",
        "source_owner",
        "source_grade",
        "evidence_summary",
        "researcher_id",
        "researched_at",
        "research_notes",
    ):
        research_queue[field] = ""

    seed = _load_seed(evidence_seed)
    seed["participant_driver_number"] = seed["participant_driver_number"].astype(int)
    mapping = screening[
        [
            "harm_record_id",
            "canonical_incident_key",
            "event_id",
            "participant_driver_number",
            "all_participant_driver_numbers",
        ]
    ]
    resolved_seed_records: list[dict[str, Any]] = []
    for _, evidence in seed.iterrows():
        counterparts = {int(value) for value in evidence["counterpart_driver_numbers"]}
        candidates = mapping.loc[
            mapping["event_id"].eq(evidence["event_id"])
            & mapping["participant_driver_number"].eq(evidence["participant_driver_number"])
        ]
        candidates = candidates.loc[
            candidates["all_participant_driver_numbers"].map(
                lambda value, expected=counterparts: expected <= _pipe_numbers(value)
            )
        ]
        if len(candidates) != 1:
            raise ValueError(
                f"Seed evidence {evidence['evidence_id']} resolved to {len(candidates)} records"
            )
        resolved_seed_records.append({**evidence.to_dict(), **candidates.iloc[0].to_dict()})
    seed = pd.DataFrame(resolved_seed_records)
    for field in EVIDENCE_REVIEW_FIELDS:
        seed[field] = ""
    seed["independent_review_status"] = "pending"

    digest = hashlib.sha256(
        _csv_bytes(screening) + _csv_bytes(research_queue) + _csv_bytes(seed)
    ).hexdigest()[:12]
    run_id = f"damage-screening-{digest}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    screening.to_csv(output_dir / "harm_screening.csv", index=False)
    research_queue.to_csv(output_dir / "source_research_queue.csv", index=False)
    seed.to_csv(output_dir / "model_researched_evidence_seed.csv", index=False)
    evidence_review = seed.copy()
    evidence_review.to_csv(output_dir / "damage_evidence_review_worklist.csv", index=False)
    manifest = {
        "schema_version": "study-v2-damage-screening-v1",
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "parent_referral_run": referral_dir.name,
        "parent_context_run": context_dir.name,
        "collision_decision_rows": int(links["incident_family"].eq("causing_collision").sum()),
        "candidate_incident_count": screening["canonical_incident_key"].nunique(),
        "participant_record_count": len(screening),
        "participant_count_by_priority": screening["screening_priority"].value_counts().to_dict(),
        "participant_rows_with_incident_lap": int(
            screening["participant_lap_candidate"].astype(str).ne("").sum()
        ),
        "persistent_pace_primary_eligible_rows": int(
            screening["persistent_pace_primary_eligible"].sum()
        ),
        "model_researched_evidence_rows": len(seed),
        "independent_damage_review_complete": False,
        "screening_sha256": hashlib.sha256(_csv_bytes(screening)).hexdigest(),
        "research_queue_sha256": hashlib.sha256(_csv_bytes(research_queue)).hexdigest(),
        "evidence_seed_sha256": hashlib.sha256(_csv_bytes(seed)).hexdigest(),
        "release_status": "descriptive_screening_pending_independent_review",
        "limitation": (
            "Retirement status, pit timing, and pace patterns prioritize source research. They do "
            "not confirm damage, causality, a forced stop, or a no-incident counterfactual."
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return DamageScreeningBuild(
        run_id=run_id,
        output_dir=output_dir,
        collision_decision_rows=manifest["collision_decision_rows"],
        candidate_incidents=manifest["candidate_incident_count"],
        participant_rows=len(screening),
        timing_eligible_rows=manifest["persistent_pace_primary_eligible_rows"],
    )
