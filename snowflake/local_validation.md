# Local Snowflake Package Validation

## Run identity

- Source commit: `f287005`
- Export ID: `snowflake-pilot-1b82517a6011`
- Generated UTC: `2026-08-12T10:03:48.961330+00:00`
- Export schema: `snowflake_pilot_v1`
- Release status: `provisional`
- Remote Snowflake status: **not executed**

## Verified artifacts

| Snowflake table | Rows | File/hash/schema/count |
|---|---:|---|
| `METADATA.EVENTS` | 3 | pass |
| `RAW.SOURCE_DOCUMENTS` | 156 | pass |
| `RAW.DOCUMENT_TEXT` | 26 | pass |
| `RAW.FASTF1_RESULTS` | 60 | pass |
| `METADATA.REGULATORY_SOURCES` | 11 | pass |
| `METADATA.EVENT_REGULATORY_SOURCES` | 11 | pass |
| `METADATA.SPORTING_REGULATION_ISSUES` | 65 | pass |
| `METADATA.INTERNATIONAL_SPORTING_CODE_ISSUES` | 9 | pass |
| `METADATA.CLAIM_LEDGER` | 12 | pass |
| `CURATED.ADJUDICATIONS` | 9 | pass |
| `CURATED.IMPACT_ASSESSMENTS` | 4 | pass |
| `AUDIT.INDEPENDENT_REVIEW` | 13 | pass |

`f1stewards validate-snowflake-export` reopened every Parquet file and matched its SHA-256,
manifest row count, and ordered columns. Automated tests also compared every Parquet projection with
the corresponding Snowflake DDL, confirmed one fail-fast load per table, rejected machine-local PDF
paths, tested content-addressed reruns, and detected a deliberately corrupted Parquet footer.

The repository-wide validation at package completion passed 60 tests, 14 DuckDB quality controls,
and the unchanged scale-readiness gate. The export remains provisional because 0/13 independent
reviews are complete; local validation does not convert candidate coding into findings.

## What this proves

- the pilot can be transformed into typed, stage-ready Parquet without credentials;
- load contracts, source lineage, event-date rule logic, review status, and parity expectations are
  explicit and testable;
- the export contains public analytical data and no Snowflake credential or machine-local cache path;
- DuckDB remains the controlled source while a warehouse deployment is optional.

## What remains to prove remotely

A real Snowsight run must still capture query IDs for setup, all 12 `COPY INTO` statements, the 15
integrity controls, the release gate, and parity checks. Warehouse name/size, elapsed time, load
history, and credit use should be recorded. Until then, this is a locally validated deployment
package rather than a claimed live Snowflake environment.
