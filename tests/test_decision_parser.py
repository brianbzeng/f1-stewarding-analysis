from f1stewards.parsing.decision import normalize_pdf_text, parse_header_fields, split_sections


def test_split_sections_preserves_evidentiary_text() -> None:
    text = normalize_pdf_text(
        """
        FACT
        Car 1 and Car 2 made contact at Turn 3.
        INFRINGEMENT
        Alleged breach of Appendix L.
        DECISION
        No further action.
        REASON
        The Stewards determined neither driver was wholly or predominantly to blame.
        """
    )
    sections = split_sections(text)
    assert sections["fact_text"].startswith("Car 1")
    assert sections["decision_text"] == "No further action."
    assert "predominantly" in sections["reason_text"]


def test_split_sections_does_not_guess_absent_headings() -> None:
    sections = split_sections("No recognizable headings are present.")
    assert sections == {}


def test_decisions_boilerplate_is_not_a_decision_heading() -> None:
    sections = split_sections(
        "Decision No further action.\nDecisions of the Stewards are taken independently of the FIA."
    )
    assert sections["decision_text"].startswith("No further action.")


def test_split_sections_handles_inline_labels_and_trims_boilerplate() -> None:
    sections = split_sections(
        """
Fact Car 22 allegedly forced Car 18 off track.
Infringement Alleged breach of Appendix L.
Decision No further action.
Reason The applicable requirements were fulfilled.
Competitors are reminded that appeal rights may apply.
        """.strip()
    )
    assert sections["fact_text"] == "Car 22 allegedly forced Car 18 off track."
    assert sections["infringement_text"] == "Alleged breach of Appendix L."
    assert sections["decision_text"] == "No further action."
    assert sections["reason_text"] == "The applicable requirements were fulfilled."


def test_parse_header_fields_uses_incident_time_after_document_time() -> None:
    fields = parse_header_fields(
        """
Time 18:50
No / Driver 22 - Yuki Tsunoda
Time 15:36
Session Race
        """.strip()
    )
    assert fields == {
        "driver_number": 22,
        "driver_name": "Yuki Tsunoda",
        "session_type": "Race",
        "incident_time_raw": "15:36",
    }
