from f1stewards.integrated_report_notebook import build_integrated_report_cells


def test_integrated_report_has_complete_narrative_and_source_gate() -> None:
    cells = build_integrated_report_cells("SETUP_SENTINEL = True")
    markdown = "\n".join(
        cell.source for cell in cells if cell.cell_type == "markdown"
    )
    code = "\n".join(cell.source for cell in cells if cell.cell_type == "code")

    for chapter in range(1, 10):
        assert f'id="chapter-{chapter}"' in markdown
    assert 'id="methods"' in markdown
    assert 'id="citations"' in markdown
    assert "The short answer" in markdown
    assert "Final conclusion" in markdown
    assert "model-led source audit" in markdown
    assert "not independent human double-coding" in markdown
    assert "never applied retrospectively" in markdown
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
