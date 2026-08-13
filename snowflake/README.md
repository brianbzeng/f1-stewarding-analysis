# Snowflake / Snowsight portability demonstration

This folder is an optional deployment target for the validated pilot model. DuckDB remains the
canonical local engine because it is free, reproducible, and sufficient for the portfolio dataset.
Snowflake demonstrates platform portability, governed loading, SQL application delivery, and
quality monitoring without making the analysis depend on a paid account.

No remote deployment has been claimed. The repository contains credential-free export, DDL, load,
view, analysis, and validation assets; a real account run should be recorded only after saving
Snowsight query IDs and results.

## 1. Build and validate the local package

```powershell
f1stewards export-snowflake-pilot
f1stewards validate-snowflake-export <printed export directory>
```

The export is content-addressed and contains 16 Snappy-compressed Parquet files plus a manifest with
row counts, ordered columns, SHA-256 hashes, Git commit, and release status. The machine-specific
PDF cache path is deliberately excluded. The latest package uses the independently reviewed pilot
tables and is labeled `reviewed`; that label applies to the pilot analytical layer, not the blocked
full-corpus outcome population. The latest reproducible local run is recorded in
`snowflake/local_validation.md`.

## 2. Prepare Snowsight

Use an existing warehouse that you are authorized to run. Execute `00_setup.sql` and
`01_tables.sql` in a Snowsight worksheet. These scripts create a portfolio database, six schemas, a
Parquet file format, a named internal stage, and bounded pilot tables; they do not create a warehouse
or contain credentials.

Upload the 16 Parquet files to `LANDING.F1_STEWARDS_STAGE` through **Ingestion → Add Data → Load
files into a Stage**. Snowsight supports uploading multiple files to a named internal stage; the
official instructions and privilege requirements are in [Staging files using
Snowsight](https://docs.snowflake.com/en/user-guide/data-load-local-file-system-stage-ui).

Do not paste `PUT` into a worksheet. Snowflake documents that `PUT` is a client command for Snowflake
CLI, SnowSQL, or drivers; Snowsight’s upload interface is the small-pilot path. See the official
[`PUT` reference](https://docs.snowflake.com/en/sql-reference/sql/put).

## 3. Load, validate, and query

Run the remaining worksheets in order:

1. `02_load.sql` — fail-fast `COPY INTO` loads with case-insensitive column matching;
2. `03_analysis_views.sql` — evidence-linked, review-state, and event-date rule views plus examples;
3. `04_quality_controls.sql` — zero-row integrity violations and a separate release-status gate;
4. `05_parity_checks.sql` — frozen pilot row counts for DuckDB/Snowflake parity.

Snowflake’s `COPY INTO <table>` supports named stages, Parquet, `MATCH_BY_COLUMN_NAME`, and
`ON_ERROR`; its load history is visible in Snowsight. See the official [`COPY INTO <table>`
reference](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table) and [internal-stage load
guide](https://docs.snowflake.com/en/user-guide/data-load-local-file-system-copy).

The event-date rule views use `QUALIFY ROW_NUMBER()` to choose one applicable issue per event, a
pattern supported directly by [Snowflake `QUALIFY`](https://docs.snowflake.com/en/sql-reference/constructs/qualify).

## 4. Evidence required before calling it deployed

Save the following in a future `snowflake/run_evidence/` directory or deployment ticket:

- Snowflake account locator and role/warehouse names, with credentials excluded;
- Git commit and export manifest/export ID;
- query IDs for setup, each `COPY INTO`, quality controls, and parity checks;
- load results and row-count parity output;
- warehouse size and elapsed/credit usage;
- teardown or retention decision.

Until that evidence exists, describe this work as a **validated deployment package**, not as a live
Snowflake implementation.
