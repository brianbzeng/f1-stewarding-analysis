from f1stewards.study_v2_nationality import evaluate_nationality_gate


def test_nationality_gate_reports_every_failed_prerequisite() -> None:
    passed, reason = evaluate_nationality_gate(
        british_rows=44,
        minimum_british_rows=98,
        overlap_status="usable_overlap",
        target_power=0.55,
        human_review_complete=False,
    )

    assert passed is False
    assert "minimum_exposed_sample_not_met" in reason
    assert "target_power_not_met" in reason
    assert "independent_human_review_incomplete" in reason


def test_nationality_gate_can_pass_only_when_all_conditions_pass() -> None:
    passed, reason = evaluate_nationality_gate(
        british_rows=120,
        minimum_british_rows=98,
        overlap_status="adequate",
        target_power=0.81,
        human_review_complete=True,
    )

    assert passed is True
    assert reason == "all_prespecified_gates_pass"
