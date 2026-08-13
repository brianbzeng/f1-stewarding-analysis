"""Outcome-blind close-case matching for Study v2 feasibility and reviewed release."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from f1stewards.config import PROJECT_ROOT, load_study_v2_settings
from f1stewards.study_v2_review import MODEL_WORKSPACE

DEFAULT_CONTEXT_DIR = (
    PROJECT_ROOT / "data" / "manual" / "study_v2_incident_context" / "incident-context-a1de9ac2c8ea"
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "manual" / "study_v2_close_cases"

PRIMARY_EXACT_FIELDS = ["incident_family", "session_type", "guideline_regime"]
PRIMARY_DISTANCE_FIELDS = [
    "attacker_line_candidate",
    "overlap_candidate",
    "first_lap_candidate",
    "wet_track_candidate",
    "safety_car_restart_candidate",
]
OUTCOME_FIELDS = {
    "fault_language",
    "outcome_family",
    "sanction_outcome",
    "penalty_seconds",
    "penalty_points",
    "grid_places",
    "damage",
    "retirement",
    "finish_position",
}


@dataclass(frozen=True)
class CloseCaseBuild:
    run_id: str
    output_dir: Path
    cases: int
    neighbor_edges: int
    minimum_support_cases: int


def validate_match_fields(
    exact_fields: list[str],
    distance_fields: list[str],
    *,
    allow_fault_conditioning: bool = False,
) -> None:
    fields = set(exact_fields) | set(distance_fields)
    forbidden = OUTCOME_FIELDS - ({"fault_language"} if allow_fault_conditioning else set())
    if overlap := fields & forbidden:
        names = ", ".join(sorted(overlap))
        raise ValueError(f"Match fields contain post-decision outcomes: {names}")


def _known(value: object) -> bool:
    return str(value) not in {"", "unknown", "nan", "None", "<NA>"}


def _distance(left: pd.Series, right: pd.Series) -> tuple[float, int, list[str]]:
    penalties: list[float] = []
    compared: list[str] = []
    for field in PRIMARY_DISTANCE_FIELDS:
        left_value = left[field]
        right_value = right[field]
        if _known(left_value) and _known(right_value):
            penalties.append(0.0 if str(left_value) == str(right_value) else 1.0)
            compared.append(field)
        elif _known(left_value) or _known(right_value):
            penalties.append(0.5)
    return (sum(penalties) / len(penalties) if penalties else 0.5, len(compared), compared)


def build_neighbor_graph(cases: pd.DataFrame, minimum_neighbors: int = 5) -> pd.DataFrame:
    validate_match_fields(PRIMARY_EXACT_FIELDS, PRIMARY_DISTANCE_FIELDS)
    records: list[dict[str, object]] = []
    for _, target in cases.iterrows():
        candidates = cases.copy()
        for field in PRIMARY_EXACT_FIELDS:
            candidates = candidates.loc[candidates[field].eq(target[field])]
        candidates = candidates.loc[
            candidates["adjudication_instance_id"].ne(target["adjudication_instance_id"])
            & candidates["match_incident_key"].ne(target["match_incident_key"])
        ]
        scored: list[tuple[float, int, str, pd.Series, list[str]]] = []
        for _, candidate in candidates.iterrows():
            distance, comparable_fields, compared = _distance(target, candidate)
            scored.append(
                (
                    distance,
                    -comparable_fields,
                    str(candidate["adjudication_instance_id"]),
                    candidate,
                    compared,
                )
            )
        scored.sort(key=lambda item: (item[0], item[1], item[2]))
        for rank, (distance, neg_count, _, neighbor, compared) in enumerate(
            scored[:minimum_neighbors], start=1
        ):
            records.append(
                {
                    "adjudication_instance_id": target["adjudication_instance_id"],
                    "adjudication_id": target["adjudication_id"],
                    "incident_id": target["incident_id"],
                    "neighbor_rank": rank,
                    "neighbor_adjudication_instance_id": neighbor["adjudication_instance_id"],
                    "neighbor_adjudication_id": neighbor["adjudication_id"],
                    "neighbor_incident_id": neighbor["incident_id"],
                    "distance": distance,
                    "fully_compared_context_fields": -neg_count,
                    "compared_fields": "|".join(compared),
                    "neighbor_sanction_outcome": neighbor["sanction_outcome"],
                    "neighbor_outcome_family": neighbor["outcome_family"],
                    "neighbor_penalty_seconds": neighbor["penalty_seconds"],
                    "neighbor_penalty_points": neighbor["penalty_points"],
                    "neighbor_grid_places": neighbor["grid_places"],
                    "match_stage": "pre_review_feasibility",
                }
            )
    return pd.DataFrame(records)


def summarize_neighbors(
    cases: pd.DataFrame,
    edges: pd.DataFrame,
    minimum_neighbors: int,
) -> pd.DataFrame:
    if edges.empty:
        summary = cases.copy()
        summary["neighbor_count"] = 0
        summary["neighbor_sanction_rate"] = pd.NA
    else:
        rates = edges.groupby("adjudication_instance_id", as_index=False).agg(
            neighbor_count=("neighbor_adjudication_instance_id", "count"),
            neighbor_sanction_rate=("neighbor_sanction_outcome", "mean"),
            median_neighbor_distance=("distance", "median"),
            minimum_context_fields=("fully_compared_context_fields", "min"),
        )
        summary = cases.merge(rates, on="adjudication_instance_id", how="left")
        summary["neighbor_count"] = summary["neighbor_count"].fillna(0).astype(int)
    summary["pre_review_minimum_support"] = summary["neighbor_count"].ge(minimum_neighbors)
    summary["sanction_rate_difference"] = (
        summary["sanction_outcome"].astype(float) - summary["neighbor_sanction_rate"]
    )
    summary["matching_release_status"] = "withheld_pending_reviewed_context"
    return summary


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    stream = io.StringIO(newline="")
    frame.to_csv(stream, index=False, lineterminator="\n")
    return stream.getvalue().encode("utf-8")


def build_close_case_matches(
    *,
    workspace: Path = MODEL_WORKSPACE,
    context_dir: Path = DEFAULT_CONTEXT_DIR,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> CloseCaseBuild:
    matching = load_study_v2_settings()["close_case_matching"]
    validate_match_fields(matching["exact_match_fields"], matching["distance_fields"])
    validate_match_fields(
        [*matching["exact_match_fields"], *matching["conditional_sanction_exact_fields"]],
        matching["distance_fields"],
        allow_fault_conditioning=True,
    )
    context = pd.read_csv(
        context_dir / "incident_context_candidates.csv", keep_default_na=False, low_memory=False
    )
    adjudications = pd.read_csv(
        workspace / "adjudication_coding_worklist.csv", keep_default_na=False, low_memory=False
    )
    primary = adjudications.loc[
        adjudications["include_primary_final"].astype(str).str.casefold().eq("true")
    ].copy()
    outcome = primary[
        [
            "adjudication_instance_id",
            "guideline_regime",
            "outcome_family_final",
            "penalty_seconds_final",
            "penalty_points_final",
            "grid_places_final",
            "fault_language_final",
        ]
    ].rename(
        columns={
            "outcome_family_final": "outcome_family",
            "penalty_seconds_final": "penalty_seconds",
            "penalty_points_final": "penalty_points",
            "grid_places_final": "grid_places",
            "fault_language_final": "fault_language",
        }
    )
    cases = context.merge(outcome, on="adjudication_instance_id", validate="one_to_one")
    cases["match_incident_key"] = cases.apply(
        lambda row: (
            row["referral_episode_id"]
            if row["referral_episode_id"]
            and row["referral_link_status"] not in {"ambiguous_pending_review", "unmatched"}
            else row["incident_id"]
        ),
        axis=1,
    )
    cases["sanction_outcome"] = ~cases["outcome_family"].isin(
        {"no_further_action", "racing_incident"}
    )
    minimum_neighbors = int(matching["minimum_neighbors"])
    edges = build_neighbor_graph(cases, minimum_neighbors)
    summary = summarize_neighbors(cases, edges, minimum_neighbors)

    conditional = cases.loc[
        cases["fault_language"].isin(
            {"wholly_to_blame", "predominantly_to_blame", "mainly_at_fault", "shared_fault"}
        )
    ].copy()
    conditional_groups = (
        conditional.groupby([*PRIMARY_EXACT_FIELDS, "fault_language"], dropna=False)
        .size()
        .reset_index(name="fault_conditioned_group_size")
    )
    conditional = conditional.merge(
        conditional_groups,
        on=[*PRIMARY_EXACT_FIELDS, "fault_language"],
        how="left",
        validate="many_to_one",
    )
    conditional["conditional_analysis_status"] = "descriptive_pending_human_review"

    digest = hashlib.sha256(
        _csv_bytes(edges) + _csv_bytes(summary) + _csv_bytes(conditional)
    ).hexdigest()[:12]
    run_id = f"close-cases-{digest}"
    output_dir = output_root / run_id
    output_dir.mkdir(parents=True, exist_ok=False)
    edges.to_csv(output_dir / "conduct_neighbor_edges.csv", index=False)
    summary.to_csv(output_dir / "conduct_neighbor_summary.csv", index=False)
    conditional.to_csv(output_dir / "fault_conditioned_sanction_population.csv", index=False)
    manifest = {
        "schema_version": "study-v2-close-case-matching-v1",
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "parent_context_run": context_dir.name,
        "case_count": len(cases),
        "neighbor_edge_count": len(edges),
        "minimum_neighbors": minimum_neighbors,
        "pre_review_minimum_support_count": int(summary["pre_review_minimum_support"].sum()),
        "primary_exact_fields": PRIMARY_EXACT_FIELDS,
        "primary_distance_fields": PRIMARY_DISTANCE_FIELDS,
        "outcome_fields_excluded_from_primary_match": sorted(OUTCOME_FIELDS),
        "human_context_review_complete": False,
        "release_status": "withheld_pending_reviewed_context",
        "edges_sha256": hashlib.sha256(_csv_bytes(edges)).hexdigest(),
        "summary_sha256": hashlib.sha256(_csv_bytes(summary)).hexdigest(),
        "limitation": (
            "Neighbor outcomes are attached only after outcome-blind matching. Current context "
            "fields are machine-extracted candidates, so these outputs demonstrate feasibility "
            "and cannot support inconsistency claims."
        ),
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return CloseCaseBuild(
        run_id=run_id,
        output_dir=output_dir,
        cases=len(cases),
        neighbor_edges=len(edges),
        minimum_support_cases=manifest["pre_review_minimum_support_count"],
    )
