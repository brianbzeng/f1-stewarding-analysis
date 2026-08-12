import json
import re

import duckdb
import pandas as pd
import pytest

from f1stewards.explorer import (
    apply_explorer_filters,
    assemble_adjudications,
    explorer_release_status,
    render_explorer_html,
    validate_explorer_payload,
)


def fixture_adjudications() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "adjudication_id": "a1",
                "season": 2023,
                "event_id": "2023-a",
                "session_type": "Race",
                "incident_family": "causing_collision",
                "outcome_family": "time_penalty",
                "guideline_regime": "internal_unavailable",
                "conformance_status": "unclear",
                "review_status": "reviewed",
            },
            {
                "adjudication_id": "a2",
                "season": 2025,
                "event_id": "2025-a",
                "session_type": "Race",
                "incident_family": "causing_collision",
                "outcome_family": "no_further_action",
                "guideline_regime": "public_2025",
                "conformance_status": "conformant",
                "review_status": "unreviewed",
            },
            {
                "adjudication_id": "a3",
                "season": 2025,
                "event_id": "2025-a",
                "session_type": "Race",
                "incident_family": "forcing_off_track",
                "outcome_family": "time_penalty",
                "guideline_regime": "public_2025",
                "conformance_status": "mitigated",
                "review_status": "unreviewed",
            },
            {
                "adjudication_id": "a4",
                "season": 2025,
                "event_id": "2025-b",
                "session_type": "Sprint",
                "incident_family": "forcing_off_track",
                "outcome_family": "time_penalty",
                "guideline_regime": "public_2025",
                "conformance_status": "conformant",
                "review_status": "reviewed",
            },
        ]
    )


def test_filter_count_matches_duckdb_reference_query() -> None:
    frame = fixture_adjudications()
    filtered = apply_explorer_filters(
        frame,
        {
            "season": {2025},
            "incident_family": {"forcing_off_track"},
            "outcome_family": {"time_penalty"},
        },
    )
    with duckdb.connect() as connection:
        connection.register("fixture", frame)
        reference = connection.sql(
            """
            SELECT count(*)
            FROM fixture
            WHERE season = 2025
              AND incident_family = 'forcing_off_track'
              AND outcome_family = 'time_penalty'
            """
        ).fetchone()[0]

    assert len(filtered) == reference == 2


def test_unsupported_filter_is_explicit() -> None:
    with pytest.raises(ValueError, match="Unsupported explorer filter"):
        apply_explorer_filters(fixture_adjudications(), {"nationality": {"British"}})


def test_assemble_adjudication_resolves_driver_and_guideline_evidence() -> None:
    coded = pd.DataFrame(
        [
            {
                "adjudication_id": "a1",
                "incident_id": "i1",
                "event_id": "2025-a",
                "source_document_id": "doc-1",
                "source_url": "https://www.fia.com/decision.pdf",
                "accused_driver_number": 1,
                "affected_driver_number": 2,
                "outcome_family": "time_penalty",
                "penalty_seconds": 5,
                "penalty_points": 1,
                "grid_places": None,
                "guideline_clause": "Penalty_2025_test",
                "guideline_regime": "public_2025",
            }
        ]
    )
    events = pd.DataFrame(
        [{"event_id": "2025-a", "season": 2025, "event_name": "Test GP"}]
    )
    texts = pd.DataFrame(
        [
            {
                "document_id": "doc-1",
                "fact_text": "Fact",
                "decision_text": "Decision",
                "reason_text": "Reason",
            }
        ]
    )
    results = pd.DataFrame(
        [
            {"event_id": "2025-a", "driver_number": 1, "driver_name": "Driver One"},
            {"event_id": "2025-a", "driver_number": 2, "driver_name": "Driver Two"},
        ]
    )
    classifications = pd.DataFrame(
        [{"event_id": "2025-a", "classification_url": "https://www.fia.com/class.pdf"}]
    )
    regulatory = pd.DataFrame(
        [
            {
                "event_id": "2025-a",
                "sporting_regulation_url": "https://www.fia.com/sporting.pdf",
                "appendix_l_url": "https://www.fia.com/l.pdf",
                "driving_guideline_url": "https://www.fia.com/driving.pdf",
                "penalty_guideline_url": "https://www.fia.com/penalty.pdf",
            }
        ]
    )

    result = assemble_adjudications(
        coded, events, texts, results, classifications, regulatory
    ).iloc[0]

    assert result.accused_driver_name == "Driver One"
    assert result.affected_driver_name == "Driver Two"
    assert result.rule_url == "https://www.fia.com/penalty.pdf"
    assert result.sanction_label == "Time Penalty · 5 seconds · 1 penalty points"


def valid_payload() -> dict:
    return {
        "metadata": {
            "title": "Explorer",
            "release_status": "provisional",
            "generated_at_utc": "2026-01-01T00:00:00+00:00",
            "git_commit": "abc1234",
            "adjudication_count": 1,
            "event_count": 1,
            "incident_count": 1,
        },
        "adjudications": [
            {
                "adjudication_id": "a1",
                "season": 2025,
                "event_id": "2025-a",
                "incident_family": "causing_collision",
                "outcome_family": "time_penalty",
                "conformance_status": "conformant",
                "review_status": "single_coded_pending_human",
                "guideline_clause": "Penalty_2025_test",
                "source_url": "https://www.fia.com/decision.pdf",
                "rule_url": "https://www.fia.com/penalty.pdf",
            }
        ],
        "impacts": [],
        "quality": {
            "active_retrieval_failures": 0,
            "recalled_source_records": 0,
            "metadata_only_regulatory_sources": 0,
            "missing_core_text_ids": [],
            "review_complete": 0,
            "review_unresolved": 1,
            "review_total": 1,
            "curated_review_ready": 0,
            "curated_review_total": 1,
            "source_data_as_of": None,
            "timing_data_as_of": None,
        },
    }


def test_rendered_explorer_has_accessible_views_and_embedded_data() -> None:
    output = render_explorer_html(valid_payload())
    match = re.search(
        r'<script id="explorer-data" type="application/json">(.*?)</script>', output
    )

    assert match is not None
    assert json.loads(match.group(1))["metadata"]["release_status"] == "provisional"
    assert 'role="tablist"' in output
    assert 'aria-live="polite"' in output
    assert "Comparable cases" in output
    assert "Download filtered CSV" in output
    assert "lines.join('\\n')" in output
    assert "lines.join('\n')" not in output


def test_payload_rejects_missing_official_url() -> None:
    payload = valid_payload()
    payload["adjudications"][0]["source_url"] = ""

    with pytest.raises(ValueError, match="Missing official decision URL"):
        validate_explorer_payload(payload)


@pytest.mark.parametrize(
    ("unresolved", "ready", "total", "expected"),
    [
        (1, 13, 13, "provisional"),
        (0, 12, 13, "provisional"),
        (0, 13, 13, "reviewed"),
    ],
)
def test_release_requires_review_and_reconciliation(
    unresolved: int, ready: int, total: int, expected: str
) -> None:
    quality = {
        "review_unresolved": unresolved,
        "curated_review_ready": ready,
        "curated_review_total": total,
    }

    assert explorer_release_status(quality) == expected
