from datetime import UTC, datetime

import pandas as pd

from f1stewards.manual import IndependentReviewRecord
from f1stewards.readiness import readiness_decision, review_gate


def review(status: str, minutes: float | None = None) -> IndependentReviewRecord:
    completed = status != "pending"
    return IndependentReviewRecord.model_validate(
        {
            "review_id": f"review-{status}",
            "target_type": "adjudication",
            "target_id": f"target-{status}",
            "evidence_urls": "https://www.fia.com/test.pdf",
            "initial_summary": "Test.",
            "review_status": status,
            "reviewer_id": "reviewer" if completed else None,
            "reviewed_at_utc": datetime.now(UTC) if completed else None,
            "review_minutes": minutes,
            "corrected_fields_json": None,
            "reviewer_notes": "Needs discussion." if status == "needs_discussion" else None,
        }
    )


def test_review_gate_stays_pending_for_discussion() -> None:
    gate = review_gate(
        [review("agree", 4.0), review("needs_discussion", 6.0)],
        maximum_unresolved=0,
    )

    assert gate["status"] == "pending"
    assert "median 5.0 min" in gate["metric"]


def test_readiness_decision_preserves_human_authority() -> None:
    assert (
        readiness_decision(pd.DataFrame({"status": ["pass", "pending"]}))
        == "blocked_pending_review"
    )
    assert (
        readiness_decision(
            pd.DataFrame({"status": ["pass", "conditional_pass", "requires_decision"]})
        )
        == "human_go_no_go_required"
    )
