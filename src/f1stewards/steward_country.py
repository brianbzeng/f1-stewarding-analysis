"""Dated source evidence for steward country and sporting-affiliation research."""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

from f1stewards.config import PROJECT_ROOT
from f1stewards.steward_panels import load_steward_name_aliases

STEWARD_COUNTRY_EVIDENCE_PATH = PROJECT_ROOT / "config" / "steward_country_evidence.csv"
EVIDENCE_COLUMNS = [
    "evidence_id",
    "steward_id",
    "observed_date",
    "date_precision",
    "source_country_code",
    "analysis_country_code",
    "evidence_dimension",
    "source_type",
    "source_url",
    "source_title",
    "source_note",
]
DATE_PRECISIONS = {"exact", "month", "season", "year"}
EVIDENCE_DIMENSIONS = {
    "fia_published_country_code",
    "formula1_competition_nationality",
    "fia_asn_affiliation",
    "fia_biographical_country",
}
EVIDENCE_ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_]*")
COUNTRY_CODE_PATTERN = re.compile(r"[A-Z]{3}")


def load_steward_country_evidence(
    path: Path = STEWARD_COUNTRY_EVIDENCE_PATH,
) -> pd.DataFrame:
    """Load the reviewed evidence ledger without collapsing source disagreements."""

    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != EVIDENCE_COLUMNS:
        raise ValueError(f"Unexpected columns in {path.name}")
    if frame.empty or frame.eq("").any().any():
        raise ValueError(f"{path.name} must contain complete evidence records")
    if frame["evidence_id"].duplicated().any():
        raise ValueError("steward country evidence_id values must be unique")
    if not frame["evidence_id"].map(
        lambda value: bool(EVIDENCE_ID_PATTERN.fullmatch(value))
    ).all():
        raise ValueError("evidence_id values must be stable lowercase identifiers")

    canonical_ids = set(
        load_steward_name_aliases()
        .loc[lambda aliases: aliases["alias_status"].eq("canonical"), "steward_id"]
        .tolist()
    )
    unknown_ids = sorted(set(frame["steward_id"]) - canonical_ids)
    if unknown_ids:
        raise ValueError(f"Unknown steward_id values: {', '.join(unknown_ids)}")
    if not set(frame["date_precision"]).issubset(DATE_PRECISIONS):
        raise ValueError("Unsupported steward evidence date_precision")
    if not set(frame["evidence_dimension"]).issubset(EVIDENCE_DIMENSIONS):
        raise ValueError("Unsupported steward evidence dimension")
    for column in ["source_country_code", "analysis_country_code"]:
        if not frame[column].map(
            lambda value: bool(COUNTRY_CODE_PATTERN.fullmatch(value))
        ).all():
            raise ValueError(f"{column} must contain three-letter uppercase codes")
    if not frame["source_url"].str.startswith("https://").all():
        raise ValueError("Steward country evidence must use HTTPS source URLs")

    observed_dates = pd.to_datetime(frame["observed_date"], format="%Y-%m-%d", errors="coerce")
    if observed_dates.isna().any():
        raise ValueError("Steward country evidence has invalid observed_date values")
    frame = frame.copy()
    frame["observed_date"] = observed_dates.dt.date
    return frame


def replace_steward_country_evidence(
    connection: duckdb.DuckDBPyConnection,
    evidence: pd.DataFrame,
) -> int:
    """Replace the evidence ledger transactionally."""

    connection.register("steward_country_evidence_batch", evidence)
    try:
        connection.execute("BEGIN TRANSACTION")
        connection.execute("DELETE FROM metadata.steward_country_evidence")
        connection.execute(
            """
            INSERT INTO metadata.steward_country_evidence BY NAME
            SELECT * FROM steward_country_evidence_batch
            """
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.unregister("steward_country_evidence_batch")
    return len(evidence)


def steward_country_evidence_audit(
    connection: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:
    """Measure evidence coverage and block analysis when source codes conflict."""

    row = connection.sql(
        """
        WITH panel_stewards AS (
            SELECT DISTINCT steward_id
            FROM curated.panel_members
        ),
        summarized AS (
            SELECT
                panel_steward.steward_id,
                count(evidence.evidence_id) AS evidence_records,
                count(DISTINCT evidence.analysis_country_code) AS distinct_codes,
                count(evidence.evidence_id) FILTER (
                    WHERE evidence.evidence_dimension IN (
                        'fia_published_country_code',
                        'formula1_competition_nationality'
                    )
                ) AS direct_code_records
            FROM panel_stewards AS panel_steward
            LEFT JOIN metadata.steward_country_evidence AS evidence USING (steward_id)
            GROUP BY panel_steward.steward_id
        )
        SELECT
            (SELECT count(*) FROM panel_stewards) AS panel_stewards,
            (SELECT count(*) FROM metadata.steward_country_evidence) AS evidence_records,
            count(*) FILTER (WHERE evidence_records > 0) AS stewards_with_evidence,
            count(*) FILTER (WHERE direct_code_records > 0) AS stewards_with_direct_codes,
            count(*) FILTER (WHERE distinct_codes > 1) AS source_conflicts,
            count(*) FILTER (WHERE distinct_codes = 1) AS single_code_stewards,
            count(*) FILTER (WHERE distinct_codes = 0) AS no_evidence_stewards
        FROM summarized
        """
    ).fetchone()
    (
        panel_stewards,
        evidence_records,
        stewards_with_evidence,
        stewards_with_direct_codes,
        source_conflicts,
        single_code_stewards,
        no_evidence_stewards,
    ) = row
    controls = [
        (
            "evidence_integrity",
            "country_evidence_nonempty",
            evidence_records > 0,
            evidence_records,
            "> 0",
        ),
        (
            "analysis_release",
            "all_panel_stewards_have_evidence",
            stewards_with_evidence == panel_stewards,
            stewards_with_evidence,
            panel_stewards,
        ),
        (
            "analysis_release",
            "all_panel_stewards_have_direct_code_evidence",
            stewards_with_direct_codes == panel_stewards,
            stewards_with_direct_codes,
            panel_stewards,
        ),
        (
            "analysis_release",
            "no_unresolved_country_code_conflicts",
            source_conflicts == 0,
            source_conflicts,
            0,
        ),
        (
            "analysis_release",
            "steward_country_analysis_release",
            (
                single_code_stewards == panel_stewards
                and stewards_with_direct_codes == panel_stewards
                and source_conflicts == 0
            ),
            (
                f"single_code={single_code_stewards}; conflicts={source_conflicts}; "
                f"missing={no_evidence_stewards}"
            ),
            f"single_code={panel_stewards}; conflicts=0; missing=0",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "gate_type": gate_type,
                "control": control,
                "status": "pass" if passed else "fail",
                "observed": str(observed),
                "expected": str(expected),
                "detail": (
                    f"evidence_records={evidence_records}; panel_stewards={panel_stewards}; "
                    f"with_evidence={stewards_with_evidence}; "
                    f"with_direct_codes={stewards_with_direct_codes}"
                ),
            }
            for gate_type, control, passed, observed, expected in controls
        ]
    )
