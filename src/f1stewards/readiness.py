"""Measured pilot scale gates that preserve human go/no-go authority."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from f1stewards.manual import (
    CodedAdjudication,
    HarmAssessment,
    ImpactAssessment,
    IndependentReviewRecord,
)


def _load_records(path: Path, model: type[Any]) -> list[Any]:
    frame = pd.read_csv(path)
    records = []
    for row in frame.to_dict(orient="records"):
        payload = {key: None if pd.isna(value) else value for key, value in row.items()}
        records.append(model.model_validate(payload))
    return records


def load_pilot_manual_records(
    coding_path: Path,
    impact_path: Path,
    harm_path: Path,
    review_path: Path,
) -> tuple[
    list[CodedAdjudication],
    list[ImpactAssessment],
    list[HarmAssessment],
    list[IndependentReviewRecord],
]:
    """Load and validate the four linked pilot manual artifacts."""

    coded = _load_records(coding_path, CodedAdjudication)
    impacts = _load_records(impact_path, ImpactAssessment)
    harms = _load_records(harm_path, HarmAssessment)
    reviews = _load_records(review_path, IndependentReviewRecord)
    expected_targets = {
        *(("adjudication", record.adjudication_id) for record in coded),
        *(("impact_assessment", record.impact_assessment_id) for record in impacts),
        *(("harm_assessment", record.harm_assessment_id) for record in harms),
    }
    actual_targets = {(record.target_type, record.target_id) for record in reviews}
    if len(actual_targets) != len(reviews):
        raise ValueError("Independent review targets must be unique")
    if actual_targets != expected_targets:
        raise ValueError("Independent review targets do not match pilot coded artifacts")
    adjudication_ids = {record.adjudication_id for record in coded}
    dangling_harms = sorted(
        record.harm_assessment_id
        for record in harms
        if record.adjudication_id not in adjudication_ids
    )
    if dangling_harms:
        raise ValueError(f"Harm assessments have unknown adjudications: {dangling_harms}")
    return coded, impacts, harms, reviews


def review_gate(
    reviews: list[IndependentReviewRecord],
    *,
    maximum_unresolved: int,
) -> dict[str, str]:
    """Summarize completion without treating a discussion as agreement."""

    counts = Counter(record.review_status for record in reviews)
    completed = len(reviews) - counts["pending"]
    unresolved = counts["pending"] + counts["needs_discussion"]
    minutes = [record.review_minutes for record in reviews if record.review_minutes is not None]
    median_minutes = float(pd.Series(minutes).median()) if minutes else 0.0
    status = "pass" if unresolved <= maximum_unresolved and completed == len(reviews) else "pending"
    return {
        "gate": "independent_review",
        "status": status,
        "metric": (
            f"{completed}/{len(reviews)} complete; {counts['agree']} agree; "
            f"{counts['correct']} correct; {counts['needs_discussion']} discussion; "
            f"median {median_minutes:.1f} min"
        ),
        "note": "All targets and discussion items must be resolved before scale collection.",
    }


def evaluate_pilot_readiness(
    connection: duckdb.DuckDBPyConnection,
    coded: list[CodedAdjudication],
    impacts: list[ImpactAssessment],
    harms: list[HarmAssessment],
    reviews: list[IndependentReviewRecord],
    thresholds: dict[str, Any],
) -> pd.DataFrame:
    """Evaluate objective pilot gates and expose the remaining judgment calls."""

    scale = thresholds["pilot_scale"]
    source_records, recalled_records, active_failures = connection.sql(
        """
        SELECT
            count(*) AS source_records,
            count(*) FILTER (WHERE is_recalled) AS recalled_records,
            count(*) FILTER (
                WHERE retrieval_error IS NOT NULL AND NOT is_recalled
            ) AS active_failures
        FROM raw.source_documents
        """
    ).fetchone()

    decision_documents, decision_sections, complete_core_sections = connection.sql(
        """
        SELECT
            count(*) AS decision_documents,
            count(t.document_id) FILTER (
                WHERE t.decision_text IS NOT NULL
            ) AS decision_sections,
            count(t.document_id) FILTER (
                WHERE t.fact_text IS NOT NULL
                  AND t.infringement_text IS NOT NULL
                  AND t.decision_text IS NOT NULL
                  AND t.reason_text IS NOT NULL
            ) AS complete_core_sections
        FROM raw.source_documents AS d
        LEFT JOIN raw.document_text AS t USING (document_id)
        WHERE d.document_class = 'steward_decision'
          AND NOT d.is_recalled
        """
    ).fetchone()
    core_fraction = (
        complete_core_sections / decision_documents if decision_documents else 0.0
    )

    pilot_events, verified_sporting, verified_code = connection.sql(
        """
        SELECT
            count(*) AS pilot_events,
            count(r.source_id) FILTER (
                WHERE r.resolution_status = 'verified_official_binary'
                  AND r.selection_status = 'event_verified'
            ) AS verified_sporting_selections,
            count(c.source_id) FILTER (
                WHERE c.document_url IS NOT NULL
                  AND c.resolution_status LIKE 'verified_official_binary%'
                  AND c.selection_status = 'effective_date_verified'
            ) AS verified_code_selections
        FROM metadata.events AS e
        LEFT JOIN analysis.v_event_sporting_regulation_selection AS r USING (event_id)
        LEFT JOIN analysis.v_event_international_sporting_code_selection AS c USING (event_id)
        WHERE e.is_pilot
        """
    ).fetchone()
    metadata_only_sources = connection.sql(
        """
        SELECT count(*)
        FROM metadata.event_regulatory_sources AS l
        JOIN metadata.regulatory_sources AS s USING (source_id)
        WHERE s.applicability_status LIKE '%metadata_only%'
        """
    ).fetchone()[0]

    enriched_events = connection.sql(
        "SELECT count(DISTINCT event_id) FROM raw.fastf1_results"
    ).fetchone()[0]
    classified_events = connection.sql(
        """
        SELECT count(DISTINCT event_id)
        FROM raw.source_documents
        WHERE document_class = 'final_classification'
          AND content_sha256 IS NOT NULL
        """
    ).fetchone()[0]

    incident_count = len({record.incident_id for record in coded})
    mechanical_count = sum(record.impact_level == "mechanical" for record in impacts)
    review = review_gate(
        reviews,
        maximum_unresolved=scale["maximum_unresolved_review_targets"],
    )
    incidents_per_event = incident_count / pilot_events if pilot_events else 0.0
    rows = [
        {
            "gate": "discovery_and_retrieval",
            "status": "pass" if source_records and active_failures == 0 else "fail",
            "metric": (
                f"{source_records} source records; {recalled_records} recalled represented; "
                f"{active_failures} active retrieval failures"
            ),
            "note": "Archive-visible recalls remain in lineage even without a binary.",
        },
        {
            "gate": "decision_parsing",
            "status": (
                "pass"
                if decision_documents
                and core_fraction >= scale["minimum_core_text_fraction"]
                else "fail"
            ),
            "metric": (
                f"{decision_sections}/{decision_documents} Decision sections; "
                f"{complete_core_sections}/{decision_documents} complete core "
                f"({core_fraction:.1%})"
            ),
            "note": "The incomplete record remains visible for manual handling.",
        },
        {
            "gate": "source_lineage",
            "status": "conditional_pass" if metadata_only_sources else "pass",
            "metric": f"{recalled_records} recalled records retained; version gaps registered",
            "note": (
                "Conditional while an event-date regulatory binary remains unresolved."
                if metadata_only_sources
                else "Recalled and corrected records remain explicit in document lineage."
            ),
        },
        {
            "gate": "event_date_law_and_guidance",
            "status": (
                "conditional_pass"
                if verified_sporting == pilot_events
                and verified_code == pilot_events
                and metadata_only_sources
                else "pass"
                if verified_sporting == pilot_events and verified_code == pilot_events
                else "fail"
            ),
            "metric": (
                f"{verified_sporting}/{pilot_events} Sporting Regulation selections verified; "
                f"{verified_code}/{pilot_events} Code selections verified; "
                f"{metadata_only_sources} metadata-only linked sources"
            ),
            "note": "A later binary is never substituted for an unresolved historical source.",
        },
        {
            "gate": "timing_and_classification",
            "status": (
                "pass"
                if enriched_events == pilot_events and classified_events == pilot_events
                else "fail"
            ),
            "metric": (
                f"{enriched_events}/{pilot_events} FastF1 events; "
                f"{classified_events}/{pilot_events} official final classifications"
            ),
            "note": "Classification arithmetic is separately validated for mechanical impacts.",
        },
        {
            "gate": "coding_validity",
            "status": "pass" if coded and impacts and harms else "fail",
            "metric": (
                f"{len(coded)} adjudications / {incident_count} incidents; "
                f"{len(impacts)} sanction-impact records / {mechanical_count} mechanical; "
                f"{len(harms)} victim-harm records"
            ),
            "note": "All rows passed controlled-field and impossible-combination contracts.",
        },
        review,
        {
            "gate": "review_burden",
            "status": "requires_decision" if review["status"] == "pass" else "pending",
            "metric": "Measured after all independent reviews are complete",
            "note": "A person must decide whether measured minutes per target fit the schedule.",
        },
        {
            "gate": "analytical_yield",
            "status": "requires_decision",
            "metric": (
                f"{incident_count} candidate incidents across {pilot_events} pilot events "
                f"({incidents_per_event:.2f} per event)"
            ),
            "note": "The purposive three-event pilot is not a power estimate for the full corpus.",
        },
    ]
    return pd.DataFrame(rows, columns=["gate", "status", "metric", "note"])


def readiness_decision(gates: pd.DataFrame) -> str:
    """Return a bounded status without automating the final human scope decision."""

    statuses = set(gates["status"])
    if "fail" in statuses:
        return "stop_or_revise"
    if "pending" in statuses:
        return "blocked_pending_review"
    return "human_go_no_go_required"
