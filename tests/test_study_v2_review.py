from pathlib import Path

import pandas as pd

from f1stewards.study_v2_review import (
    FORBIDDEN_PACKET_FIELDS,
    REVIEW_FIELDS,
    _normalize_multiline_evidence,
    _round_robin_stratified_sample,
    select_review_documents,
    validate_review_packet,
)


def test_multiline_evidence_normalization_removes_only_line_padding() -> None:
    source = "  Fact heading  \nEvidence remains internal  \n \n"

    assert _normalize_multiline_evidence(source) == "  Fact heading\nEvidence remains internal"


def test_stratified_sample_is_deterministic_and_unique() -> None:
    frame = pd.DataFrame(
        {
            "document_id": [f"doc-{index}" for index in range(20)],
            "season": [2018 + index % 4 for index in range(20)],
            "family": ["a" if index % 3 else "b" for index in range(20)],
        }
    )
    first = _round_robin_stratified_sample(frame, 11, ["season", "family"], "salt")
    second = _round_robin_stratified_sample(frame, 11, ["season", "family"], "salt")

    assert first["document_id"].tolist() == second["document_id"].tolist()
    assert len(first) == 11
    assert first["document_id"].is_unique


def test_risk_selection_preserves_multi_party_documents() -> None:
    documents = pd.DataFrame(
        {
            "document_id": ["clean", "parser", "multi"],
            "parser_review_required": [False, True, False],
            "family_conflict_suggestion": [False, False, False],
            "version_state_suggestion": ["live_standalone"] * 3,
            "title": ["Decision"] * 3,
            "supersedes_document_id": [""] * 3,
            "successor_document_id": [""] * 3,
            "version_status_final": ["effective"] * 3,
            "review_status": ["model_reviewed_agree"] * 3,
            "eligibility_final": ["exclude", "exclude", "include"],
        }
    )
    adjudications = pd.DataFrame(
        {
            "document_id": ["multi"],
            "include_primary_final": [True],
            "multi_party_suggestion": [True],
        }
    )

    selected = select_review_documents(documents, adjudications).set_index("document_id")

    assert bool(selected.loc["parser", "elevated_risk"])
    assert bool(selected.loc["multi", "included_multi_party"])
    assert bool(selected.loc["clean", "clean_exclusion"])


def test_packet_validator_rejects_model_final_fields(tmp_path: Path) -> None:
    base = pd.DataFrame(
        {
            "document_id": ["doc-1"],
            **{field: [""] for field in REVIEW_FIELDS},
        }
    )
    from f1stewards.study_v2_review import _csv_bytes, _sha256_bytes

    for reviewer in ("a", "b"):
        base.to_csv(tmp_path / f"reviewer_{reviewer}_source_reviews.csv", index=False)
    manifest = {
        "reviewer_a_sha256": _sha256_bytes(_csv_bytes(base)),
        "reviewer_b_sha256": _sha256_bytes(_csv_bytes(base)),
    }
    import json

    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert validate_review_packet(tmp_path)["status"] == "pass"

    contaminated = base.copy()
    contaminated[next(iter(FORBIDDEN_PACKET_FIELDS))] = "model answer"
    contaminated.to_csv(tmp_path / "reviewer_a_source_reviews.csv", index=False)
    try:
        validate_review_packet(tmp_path)
    except ValueError as exc:
        assert "forbidden_fields_absent" in str(exc)
    else:
        raise AssertionError("Expected contaminated packet to fail")
