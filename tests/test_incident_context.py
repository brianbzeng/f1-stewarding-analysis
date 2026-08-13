from f1stewards.incident_context import extract_context_candidates


def test_context_extraction_keeps_evidence_and_ambiguity() -> None:
    context = extract_context_candidates(
        "On the first lap Car 4 attempted a pass on the inside. Car 4's front axle was "
        "ahead of the mirror at the apex. The cars remained alongside on the exit."
    )

    assert context["first_lap_candidate"] is True
    assert context["attacker_line_candidate"] == "inside"
    assert context["overlap_candidate"] == "ambiguous"
    assert context["corner_phase_candidate"] == "apex|exit"
    assert "front axle" in str(context["context_evidence_json"])


def test_context_does_not_infer_absent_conditions() -> None:
    context = extract_context_candidates("The Stewards reviewed video evidence.")

    assert context["first_lap_candidate"] is False
    assert context["wet_track_candidate"] is False
    assert context["attacker_line_candidate"] == "unknown"
    assert context["overlap_candidate"] == "unknown"
    assert context["context_review_status"] == "machine_extracted_pending_human_review"
