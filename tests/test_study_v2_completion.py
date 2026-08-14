from f1stewards.study_v2_completion import audit_study_v2_completion


def test_study_v2_completion_audit_passes_every_release_control() -> None:
    audit = audit_study_v2_completion()

    assert len(audit) == 27
    assert audit["control"].is_unique
    assert audit["status"].eq("pass").all()
