from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from f1stewards.config import load_full_corpus_coding_settings

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_model_review_release.py"
SPEC = importlib.util.spec_from_file_location("build_model_review_release", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
_source_only_document_coding = MODULE._source_only_document_coding
_validate_document_disposition = MODULE._validate_document_disposition


def _source_lookup() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "document_id": "fia-test",
                "raw_text": "Decision. Race. Car 1 caused a collision with Car 2.",
                "fact_text": "Car 1 caused a collision with Car 2 during the race.",
                "infringement_text": "Alleged breach of the driving standard.",
                "decision_text": "A 5 second time penalty.",
                "reason_text": "The driver of Car 1 was wholly to blame.",
                "parser_warnings_json": "[]",
                "driver_number": "1",
                "driver_name": "Test Driver",
                "session_type": "Race",
                "incident_time_raw": "15:00",
                "content_document_class": "steward_decision",
                "content_classification_basis": "source text",
            }
        ]
    ).set_index("document_id")


def _document_row() -> pd.Series:
    return pd.Series(
        {
            "document_id": "fia-test",
            "title": "Decision - Car 1 - Causing a collision",
            "source_url": "https://example.test/fia-test.pdf",
            "season": "2025",
            "is_recalled": "False",
            "successor_document_id": "",
            "supersedes_document_id": "",
            "version_state_suggestion": "live_standalone",
            "content_status_suggestion": "content_confirmed_decision",
            "session_scope_suggestion": "primary_race_sprint",
            "offence_family_suggestion": "causing_collision",
            "eligibility_suggestion": "primary_candidate",
            "version_status_final": "effective",
            "session_scope_final": "primary",
            "offence_family_final": "causing_collision",
            "eligibility_final": "include",
        }
    )


def test_source_only_review_normalizes_csv_false_boolean() -> None:
    result = _source_only_document_coding(
        _document_row(),
        _source_lookup(),
        load_full_corpus_coding_settings(),
    )

    assert result["version"] == "live_standalone"
    assert result["session_scope"] == "primary_race_sprint"
    assert result["family"] == "causing_collision"
    assert result["eligibility"] == "primary_candidate"
    assert result["evidence_basis"] == "source_text_reclassification"


def test_document_agreement_requires_source_derived_final_match() -> None:
    settings = load_full_corpus_coding_settings()
    row = _document_row()
    result = _source_only_document_coding(row, _source_lookup(), settings)
    row["eligibility_final"] = "exclude"

    with pytest.raises(ValueError, match="Source-defined candidate was excluded"):
        _validate_document_disposition(row, result, settings)
