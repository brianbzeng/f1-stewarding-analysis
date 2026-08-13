"""Build separate conduct, consequence, sanction, and proportionality layers."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from f1stewards.config import PROJECT_ROOT
from f1stewards.study_v2_review import DEFAULT_DATABASE, MODEL_WORKSPACE

DEFAULT_CONTEXT_DIR = (
    PROJECT_ROOT / "data" / "manual" / "study_v2_incident_context" / "incident-context-a1de9ac2c8ea"
)
DEFAULT_CLOSE_CASE_DIR = (
    PROJECT_ROOT / "data" / "manual" / "study_v2_close_cases" / "close-cases-36f9bc70de82"
)
DEFAULT_DAMAGE_DIR = (
    PROJECT_ROOT / "data" / "manual" / "study_v2_damage" / "damage-screening-66381b550583"
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "manual" / "study_v2_layers"

FAULT_ESTABLISHED = {"wholly_to_blame", "predominantly_to_blame", "shared_fault"}


@dataclass(frozen=True)
class LayerBuild:
    run_id: str
    output_dir: Path
    conduct_rows: int
    consequence_rows: int
    sanction_rows: int
    pace_screen_rows: int
    proportionality_release_rows: int


def _truthy(values: pd.Series) -> pd.Series:
    return values.astype(str).str.casefold().isin({"true", "1", "yes"})


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def build_conduct_layer(adjudications: pd.DataFrame, context: pd.DataFrame) -> pd.DataFrame:
    primary = adjudications.loc[_truthy(adjudications["include_primary_final"])].copy()
    columns = [
        "adjudication_instance_id",
        "adjudication_id_final",
        "incident_id_final",
        "document_id",
        "event_id",
        "season",
        "session_type_final",
        "incident_family_final",
        "accused_driver_number_final",
        "affected_driver_numbers_final",
        "fault_language_final",
        "outcome_family_final",
        "penalty_seconds_final",
        "penalty_points_final",
        "grid_places_final",
        "guideline_regime",
        "review_status",
    ]
    layer = primary[columns].merge(
        context[
            [
                "adjudication_instance_id",
                "incident_lap_candidate",
                "incident_lap_basis",
                "first_lap_candidate",
                "wet_track_candidate",
                "safety_car_restart_candidate",
                "attacker_line_candidate",
                "overlap_candidate",
                "corner_phase_candidate",
                "control_error_candidate",
                "context_review_status",
            ]
        ],
        on="adjudication_instance_id",
        how="left",
        validate="one_to_one",
    )
    layer["sanction_outcome"] = ~layer["outcome_family_final"].isin(
        {"no_further_action", "warning", "reprimand"}
    )
    layer["fault_established_model_review"] = layer["fault_language_final"].isin(FAULT_ESTABLISHED)
    layer["conduct_release_status"] = "descriptive_model_review_pending_human"
    return layer.sort_values(["event_id", "adjudication_instance_id"]).reset_index(drop=True)


def build_sanction_layer(conduct: pd.DataFrame) -> pd.DataFrame:
    layer = conduct[
        [
            "adjudication_instance_id",
            "adjudication_id_final",
            "incident_id_final",
            "document_id",
            "event_id",
            "season",
            "session_type_final",
            "accused_driver_number_final",
            "outcome_family_final",
            "penalty_seconds_final",
            "penalty_points_final",
            "grid_places_final",
            "review_status",
        ]
    ].copy()

    def burden_status(row: pd.Series) -> str:
        family = str(row["outcome_family_final"])
        if family == "time_penalty":
            return "application_timing_required_for_realized_cost"
        if family == "grid_penalty":
            return "application_event_required_for_realized_grid_cost"
        if family in {"drive_through", "stop_go"}:
            return "served_timing_required_for_realized_cost"
        if family in {"no_further_action", "warning", "reprimand"}:
            return "no_direct_race_time_or_grid_burden"
        return "requires_sanction_specific_review"

    layer["realized_burden_status"] = layer.apply(burden_status, axis=1)
    layer["realized_seconds"] = ""
    layer["realized_positions"] = ""
    layer["realized_grid_places"] = ""
    layer["realized_points"] = ""
    layer["sanction_review_status"] = "pending_application_timing_review"
    return layer


def _clean_laps(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.loc[
        frame["is_accurate"].fillna(False).astype(bool)
        & frame["track_status"].astype(str).eq("1")
        & frame["lap_time_seconds"].notna()
        & frame["pit_in_time_seconds"].isna()
        & frame["pit_out_time_seconds"].isna()
        & frame["lap_number"].gt(1)
    ].copy()


def estimate_reference_adjusted_pace(
    participant_laps: pd.DataFrame,
    reference_laps: pd.DataFrame,
    incident_lap: int,
    *,
    window: int = 8,
    minimum_each_side: int = 5,
) -> dict[str, Any]:
    """Return a transparent teammate-relative change used only as a research screen."""

    required = {
        "lap_number",
        "lap_time_seconds",
        "track_status",
        "is_accurate",
        "pit_in_time_seconds",
        "pit_out_time_seconds",
        "compound",
        "tyre_life",
    }
    if required - set(participant_laps) or required - set(reference_laps):
        raise ValueError("Pace inputs are missing required lap fields")
    participant = _clean_laps(participant_laps).rename(
        columns={
            "lap_time_seconds": "participant_lap_time",
            "compound": "participant_compound",
            "tyre_life": "participant_tyre_life",
        }
    )
    reference = _clean_laps(reference_laps).rename(
        columns={
            "lap_time_seconds": "reference_lap_time",
            "compound": "reference_compound",
            "tyre_life": "reference_tyre_life",
        }
    )
    joined = participant[
        [
            "lap_number",
            "participant_lap_time",
            "participant_compound",
            "participant_tyre_life",
        ]
    ].merge(
        reference[
            ["lap_number", "reference_lap_time", "reference_compound", "reference_tyre_life"]
        ],
        on="lap_number",
        how="inner",
        validate="one_to_one",
    )
    joined = joined.loc[
        joined["lap_number"].between(incident_lap - window, incident_lap + window)
        & joined["lap_number"].ne(incident_lap)
    ].copy()
    joined["period"] = np.where(joined["lap_number"].lt(incident_lap), "before", "after")
    joined["relative_lap_time_seconds"] = (
        joined["participant_lap_time"] - joined["reference_lap_time"]
    )
    before = joined.loc[joined["period"].eq("before")]
    after = joined.loc[joined["period"].eq("after")]
    output: dict[str, Any] = {
        "matched_laps_before": len(before),
        "matched_laps_after": len(after),
        "pace_change_seconds_per_lap": None,
        "pace_change_standard_error": None,
        "pace_change_ci95_low": None,
        "pace_change_ci95_high": None,
        "same_compound_fraction": None,
        "pace_screen_status": "not_estimable",
    }
    if len(before) < minimum_each_side or len(after) < minimum_each_side:
        return output
    change = float(
        after["relative_lap_time_seconds"].mean() - before["relative_lap_time_seconds"].mean()
    )
    variance = float(
        before["relative_lap_time_seconds"].var(ddof=1) / len(before)
        + after["relative_lap_time_seconds"].var(ddof=1) / len(after)
    )
    standard_error = float(np.sqrt(max(0.0, variance)))
    output.update(
        {
            "pace_change_seconds_per_lap": change,
            "pace_change_standard_error": standard_error,
            "pace_change_ci95_low": change - 1.96 * standard_error,
            "pace_change_ci95_high": change + 1.96 * standard_error,
            "same_compound_fraction": float(
                joined["participant_compound"].eq(joined["reference_compound"]).mean()
            ),
            "pace_screen_status": "estimable_screen_pending_damage_and_context_review",
        }
    )
    return output


def build_pace_screen(
    consequence: pd.DataFrame, laps: pd.DataFrame, results: pd.DataFrame
) -> pd.DataFrame:
    eligible = consequence.loc[
        consequence["persistent_pace_primary_eligible"].fillna(False).astype(bool)
        & consequence["participant_lap_candidate"].astype(str).ne("")
    ].copy()
    records: list[dict[str, Any]] = []
    for _, row in eligible.iterrows():
        event = row["event_id"]
        session = row["session_type"]
        driver = int(row["participant_driver_number"])
        team = str(row["team_name"])
        teammate = results.loc[
            results["event_id"].eq(event)
            & results["session_type"].eq(session)
            & results["team_name"].eq(team)
            & results["driver_number"].ne(driver),
            "driver_number",
        ]
        if teammate.empty:
            continue
        participant_laps = laps.loc[
            laps["event_id"].eq(event)
            & laps["session_type"].eq(session)
            & laps["driver_number"].eq(driver)
        ]
        reference_number = int(teammate.iloc[0])
        reference_laps = laps.loc[
            laps["event_id"].eq(event)
            & laps["session_type"].eq(session)
            & laps["driver_number"].eq(reference_number)
        ]
        estimate = estimate_reference_adjusted_pace(
            participant_laps,
            reference_laps,
            int(float(row["participant_lap_candidate"])),
        )
        records.append(
            {
                "harm_record_id": row["harm_record_id"],
                "canonical_incident_key": row["canonical_incident_key"],
                "event_id": event,
                "session_type": session,
                "participant_driver_number": driver,
                "reference_driver_number": reference_number,
                "incident_lap": int(float(row["participant_lap_candidate"])),
                **estimate,
                "damage_confirmation_status": "pending_independent_source_review",
                "interpretation": ("teammate_relative_timing_screen_not_a_causal_damage_estimate"),
            }
        )
    return pd.DataFrame(records)


def build_proportionality_gate(
    conduct: pd.DataFrame, consequence: pd.DataFrame, evidence_review: pd.DataFrame
) -> pd.DataFrame:
    review_status = evidence_review.set_index("harm_record_id")[
        "independent_review_status"
    ].to_dict()
    fault_by_adjudication = conduct.set_index("adjudication_id_final")[
        "fault_established_model_review"
    ].to_dict()
    rows = consequence.copy()
    rows["fault_established_model_review"] = rows["adjudication_ids"].map(
        lambda values: any(
            fault_by_adjudication.get(item, False) for item in str(values).split("|")
        )
    )
    rows["independent_harm_review_status"] = (
        rows["harm_record_id"].map(review_status).fillna("not_yet_researched")
    )
    rows["independent_harm_confirmed"] = rows["independent_harm_review_status"].isin(
        {"agree", "adjudicated"}
    )
    rows["independent_conduct_review_complete"] = False
    rows["proportionality_release_eligible"] = (
        rows["fault_established_model_review"]
        & rows["independent_harm_confirmed"]
        & rows["independent_conduct_review_complete"]
    )
    rows["gate_reason"] = np.where(
        rows["proportionality_release_eligible"],
        "eligible",
        "pending_independent_conduct_and_or_harm_review",
    )
    return rows[
        [
            "harm_record_id",
            "canonical_incident_key",
            "event_id",
            "participant_driver_number",
            "participant_role",
            "adjudication_ids",
            "fault_established_model_review",
            "independent_harm_review_status",
            "independent_harm_confirmed",
            "independent_conduct_review_complete",
            "proportionality_release_eligible",
            "gate_reason",
        ]
    ]


def build_study_v2_layers(
    *,
    database_path: Path = DEFAULT_DATABASE,
    workspace: Path = MODEL_WORKSPACE,
    context_dir: Path = DEFAULT_CONTEXT_DIR,
    close_case_dir: Path = DEFAULT_CLOSE_CASE_DIR,
    damage_dir: Path = DEFAULT_DAMAGE_DIR,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> LayerBuild:
    adjudications = pd.read_csv(
        workspace / "adjudication_coding_worklist.csv", keep_default_na=False, low_memory=False
    )
    context = pd.read_csv(
        context_dir / "incident_context_candidates.csv", keep_default_na=False, low_memory=False
    )
    consequence = pd.read_csv(
        damage_dir / "harm_screening.csv", keep_default_na=False, low_memory=False
    )
    evidence_review = pd.read_csv(
        damage_dir / "damage_evidence_review_worklist.csv",
        keep_default_na=False,
        low_memory=False,
    )
    neighbor_edges = pd.read_csv(
        close_case_dir / "conduct_neighbor_edges.csv", keep_default_na=False, low_memory=False
    )
    conduct = build_conduct_layer(adjudications, context)
    sanction = build_sanction_layer(conduct)
    with duckdb.connect(str(database_path), read_only=True) as connection:
        laps = connection.execute(
            "SELECT * FROM raw.fastf1_session_laps WHERE session_type IN ('Race', 'Sprint')"
        ).fetchdf()
        results = connection.execute(
            "SELECT * FROM raw.fastf1_session_results WHERE session_type IN ('Race', 'Sprint')"
        ).fetchdf()
    pace = build_pace_screen(consequence, laps, results)
    proportionality = build_proportionality_gate(conduct, consequence, evidence_review)
    source_sanctions = conduct.set_index("adjudication_instance_id")["sanction_outcome"]
    neighbor_edges["sanction_outcome"] = neighbor_edges["adjudication_instance_id"].map(
        source_sanctions
    )
    neighbor_edges["different_sanction_outcome"] = neighbor_edges["neighbor_sanction_outcome"].ne(
        neighbor_edges["sanction_outcome"]
    )
    neighbor_edges["interpretation"] = "review_priority_only_pending_context_and_conduct_review"
    digest = hashlib.sha256(
        _csv_bytes(conduct)
        + _csv_bytes(consequence)
        + _csv_bytes(sanction)
        + _csv_bytes(pace)
        + _csv_bytes(proportionality)
    ).hexdigest()[:12]
    run_id = f"study-v2-layers-{digest}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    conduct.to_csv(output_dir / "conduct_layer.csv", index=False)
    consequence.to_csv(output_dir / "consequence_screening_layer.csv", index=False)
    sanction.to_csv(output_dir / "sanction_layer.csv", index=False)
    pace.to_csv(output_dir / "persistent_pace_screen.csv", index=False)
    proportionality.to_csv(output_dir / "proportionality_release_gate.csv", index=False)
    neighbor_edges.to_csv(output_dir / "close_case_outcome_contrasts.csv", index=False)
    manifest = {
        "schema_version": "study-v2-layers-v1",
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "conduct_rows": len(conduct),
        "consequence_rows": len(consequence),
        "sanction_rows": len(sanction),
        "pace_screen_rows": len(pace),
        "pace_screen_estimable_rows": int(
            pace["pace_screen_status"].str.startswith("estimable").sum()
        ),
        "close_case_edges": len(neighbor_edges),
        "close_case_edges_with_different_sanction": int(
            neighbor_edges["different_sanction_outcome"].sum()
        ),
        "proportionality_release_rows": int(
            proportionality["proportionality_release_eligible"].sum()
        ),
        "human_review_complete": False,
        "release_status": "descriptive_scaffolding_pending_independent_review",
        "guardrail": (
            "Conduct, consequence, and sanction stay in separate units. No composite fairness "
            "score is calculated. Pace estimates are research screens until damage and context "
            "are independently reviewed."
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return LayerBuild(
        run_id=run_id,
        output_dir=output_dir,
        conduct_rows=len(conduct),
        consequence_rows=len(consequence),
        sanction_rows=len(sanction),
        pace_screen_rows=len(pace),
        proportionality_release_rows=manifest["proportionality_release_rows"],
    )
