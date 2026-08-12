from pathlib import Path

import pandas as pd

from f1stewards.cli import _write_discovery_failures


def test_discovery_failure_queue_removes_successes_and_retains_unattempted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "failures.csv"
    pd.DataFrame(
        [
            {
                "event_id": "2020-aut",
                "season": 2020,
                "archive_url": "https://www.fia.com/aut",
                "failed_at_utc": "2026-08-12T00:00:00+00:00",
                "error": "old failure",
            },
            {
                "event_id": "2021-bhr",
                "season": 2021,
                "archive_url": "https://www.fia.com/bhr",
                "failed_at_utc": "2026-08-12T00:00:00+00:00",
                "error": "unattempted failure",
            },
        ]
    ).to_csv(path, index=False)

    _write_discovery_failures(
        [
            {
                "event_id": "2022-mco",
                "season": 2022,
                "archive_url": "https://www.fia.com/mco",
                "failed_at_utc": "2026-08-13T00:00:00+00:00",
                "error": "new failure",
            }
        ],
        {"2020-aut", "2022-mco"},
        path,
    )

    result = pd.read_csv(path)
    assert result["event_id"].tolist() == ["2021-bhr", "2022-mco"]
    assert result["error"].tolist() == ["unattempted failure", "new failure"]
