import re

from f1stewards.config import PROJECT_ROOT
from f1stewards.snowflake import TABLE_NAMES

SNOWFLAKE_ROOT = PROJECT_ROOT / "snowflake"


def sql(name: str) -> str:
    return (SNOWFLAKE_ROOT / name).read_text(encoding="utf-8")


def test_setup_uses_existing_warehouse_and_contains_no_credentials() -> None:
    setup = sql("00_setup.sql").upper()
    all_sql = "\n".join(path.read_text(encoding="utf-8") for path in SNOWFLAKE_ROOT.glob("*.sql"))

    assert "CREATE WAREHOUSE" not in setup
    assert setup.count("CREATE SCHEMA IF NOT EXISTS") == 6
    assert "CREATE STAGE IF NOT EXISTS LANDING.F1_STEWARDS_STAGE" in setup
    assert "PUT FILE:" not in all_sql.upper()
    assert not re.search(r"PASSWORD\s*=|SECRET_KEY|PRIVATE_KEY", all_sql, re.IGNORECASE)


def test_ddl_and_copy_scripts_cover_every_export_table_once() -> None:
    ddl = sql("01_tables.sql").upper()
    load = sql("02_load.sql")

    assert len(re.findall(r"\bCOPY\s+INTO\b", load, re.IGNORECASE)) == len(TABLE_NAMES)
    for export_name, table_name in TABLE_NAMES.items():
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in ddl
        assert len(re.findall(rf"COPY\s+INTO\s+{re.escape(table_name)}\b", load, re.I)) == 1
        assert f"FILES = ('{export_name}.parquet')" in load


def test_analysis_and_quality_scripts_keep_release_limits_explicit() -> None:
    analysis = sql("03_analysis_views.sql").upper()
    quality = sql("04_quality_controls.sql").upper()

    assert analysis.count("QUALIFY ROW_NUMBER()") == 2
    assert "DESCRIPTIVE ONLY WHILE PROVISIONAL" in analysis
    assert "V_EVIDENCE_LINKED_ADJUDICATIONS" in analysis
    assert quality.count("SF_QC_") == 15
    assert "UNRESOLVED_REVIEW_TARGETS" in quality
    assert "CURATED_ROWS_NOT_RELEASE_READY" in quality
    assert "'PROVISIONAL'" in quality


def test_parity_script_freezes_all_twelve_pilot_counts() -> None:
    parity = sql("05_parity_checks.sql").upper()
    expected = {
        "METADATA.EVENTS": 3,
        "RAW.SOURCE_DOCUMENTS": 156,
        "RAW.DOCUMENT_TEXT": 26,
        "RAW.FASTF1_RESULTS": 60,
        "METADATA.REGULATORY_SOURCES": 11,
        "METADATA.EVENT_REGULATORY_SOURCES": 11,
        "METADATA.SPORTING_REGULATION_ISSUES": 65,
        "METADATA.INTERNATIONAL_SPORTING_CODE_ISSUES": 9,
        "METADATA.CLAIM_LEDGER": 12,
        "CURATED.ADJUDICATIONS": 9,
        "CURATED.IMPACT_ASSESSMENTS": 4,
        "AUDIT.INDEPENDENT_REVIEW": 13,
    }

    for table_name, row_count in expected.items():
        assert f"('{table_name}', {row_count})" in parity
