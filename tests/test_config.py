from pathlib import Path

import pytest

from f1stewards.config import load_regulatory_sources


def test_regulatory_sources_validate_and_cover_each_pilot() -> None:
    sources = load_regulatory_sources()
    covered = {event_id for source in sources for event_id in source.event_ids}

    assert covered == {"2019-aut", "2023-abu", "2025-aut"}
    assert sum(source.is_guideline for source in sources) == 2


def test_regulatory_sources_reject_unknown_event(tmp_path: Path) -> None:
    path = tmp_path / "sources.yml"
    path.write_text(
        """
regulatory_sources:
  - source_id: test-source
    document_type: test
    title: Test
    source_url: https://www.fia.com/test.pdf
    source_status: test
    applicability_status: contextual_only
    event_role: contextual
    event_ids: [2099-zzz]
    notes: Test
""".lstrip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown event_ids"):
        load_regulatory_sources(path)
