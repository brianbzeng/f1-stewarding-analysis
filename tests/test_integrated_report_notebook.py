from f1stewards.integrated_report_notebook import build_integrated_report_cells


def test_integrated_report_has_complete_narrative_and_source_gate() -> None:
    cells = build_integrated_report_cells("SETUP_SENTINEL = True")
    markdown = "\n".join(
        cell.source for cell in cells if cell.cell_type == "markdown"
    )
    code = "\n".join(cell.source for cell in cells if cell.cell_type == "code")

    for chapter in range(1, 11):
        assert f'id="chapter-{chapter}"' in markdown
    assert 'id="methods"' in markdown
    assert 'id="citations"' in markdown
    assert "Primary result:" in markdown
    assert "Final conclusion" in markdown
    assert "model-led source audit" in markdown
    assert "no claim of full-corpus human inter-rater agreement" in markdown
    assert "never applied retrospectively" in markdown
    assert "Inconsistency audit and case studies" in markdown
    assert "Japan 2024" in markdown
    assert "São Paulo 2021" in markdown
    assert "–" not in markdown
    assert "—" not in markdown
    assert "assert int(disagreement_taxonomy.sum()) == 131" in code
    assert "SETUP_SENTINEL = True" in code
    assert "assert len(decision_citations) == 418" in code
    assert "Official decision" in code
    assert "strict_manifest" in code


def test_integrated_report_uses_colorblind_safe_palette_and_alt_text() -> None:
    cells = build_integrated_report_cells("pass")
    code = "\n".join(cell.source for cell in cells if cell.cell_type == "code")

    for color in ("#0072B2", "#56B4E9", "#009E73", "#E69F00", "#D55E00"):
        assert color in code
    assert "alt_text" in code
    assert "Wilson 95% intervals" in code


def test_inconsistency_chapter_cites_every_discussed_decision() -> None:
    cells = build_integrated_report_cells("pass")
    markdown = "\n".join(
        cell.source for cell in cells if cell.cell_type == "markdown"
    )

    source_fragments = (
        "2019%20Canadian%20Grand%20Prix%20-%20Offence%20-%20Car%205",
        "doc_50_-_2019_austrian_grand_prix",
        "doc_50_-_2021_british_grand_prix",
        "bra_doc_55_-_decision_-_mercedes_-_right_of_review_0.pdf",
        "2021_f1_abu_dhabi_grand_prix_-_report_to_the_wmsc",
        "2024%20United%20States%20Grand%20Prix%20-%20Infringement%20-%20Car%204",
        "Turn%204%20Forcing%20another%20driver%20of%20the%20track",
        "Turn%208%20Leaving%20the%20track%20and%20gaining%20an%20advantage",
        "2024%20Japanese%20Grand%20Prix%20-%20Decision%20-%20Car%2063",
        "2025_hungarian_grand_prix_-_decision_-_car_22",
        "2025_italian_grand_prix_-_infringement_-_car_31",
    )
    for fragment in source_fragments:
        assert fragment in markdown
