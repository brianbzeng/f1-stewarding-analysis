# The Cost of Discretion

An auditable analysis of consistency, potential nationality effects, and competitive impact in Formula One stewarding decisions from 2018 through 2025.

This project treats stewarding decisions as regulatory evidence, not fan opinion. Its purpose is to determine whether formally adjudicated driving incidents receive comparable treatment after accounting for observable context, and to prioritize unusual decisions for human review. It does **not** claim that a statistical model can determine fault or prove misconduct.

## Questions

1. How predictable are penalty and no-further-action decisions from observable incident facts?
2. During 2025, how closely did sanctions follow the public FIA penalty and driving-standard guidelines?
3. After referral to the stewards, are adjusted outcomes associated with driver nationality, counterparty nationality, home-race status, or steward-panel composition?
4. Which penalties mechanically changed classifications, points, podiums, or wins, and which effects require a modeled counterfactual?
5. Which decisions are sufficiently unusual, well-supported, and competitively important to prioritize for manual review?

## Scope

- Completed seasons: 2018-2025
- Primary sessions: Race and Sprint
- Primary unit: one accused-driver adjudication within an underlying incident
- Primary incident families: causing a collision, forcing another driver off track, leaving the track and gaining an advantage, unsafe rejoining, moving under braking, and multiple defensive moves
- Secondary analysis: qualifying impeding, only if the feasibility and power review supports it
- Excluded from the primary models: technical infringements, power-unit penalties, pit-lane speeding, equipment violations, automatic grid drops, and other strict-liability offences

The analysis is conditional on formal referral or adjudication. It cannot identify comparable incidents that Race Control never referred to the stewards.

## Architecture

```text
FIA HTML/PDF + regulations + FastF1
                  |
                  v
         raw source manifest
                  |
                  v
     parsed and validated evidence
                  |
                  v
       DuckDB + partitioned Parquet
                  |
          +-------+--------+
          |                |
          v                v
  Jupyter analysis   evidence explorer
          |
          v
 executive brief + final report + technical appendix
```

The canonical local workflow uses Python, Jupyter, DuckDB, Parquet, and Git. A focused,
credential-free Snowflake/Snowsight deployment package demonstrates portability after the curated
pilot model, while DuckDB remains the reproducible source of truth.

## Repository layout

```text
config/       machine-readable source and pilot configuration
data/         raw, interim, processed, and external data (large files ignored)
docs/         protocol, source register, codebook, lineage, and recruiter mapping
explorer/     generated, evidence-linked static review application
notebooks/    numbered analysis notebooks
reports/      executive and technical deliverables
snowflake/    optional Snowsight DDL, loading, views, quality, and parity worksheets
sql/          portable schema and analytical queries
src/          reusable Python package
tests/        parser, schema, and transformation tests
```

## Quick start

The supported Python range is 3.11-3.13. Python 3.12 is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[analysis,dev]"
pytest
```

The first milestone is a three-event feasibility pilot. Do not run the full-season collector until the pilot's extraction, completeness, and manual-review gates pass.

## Pilot commands

```powershell
f1stewards init-db
f1stewards pilot-discover
f1stewards pilot-discover --event-id 2019-aut --download
f1stewards parse-decisions
f1stewards parser-audit
f1stewards pilot-fastf1
f1stewards build-coding-queue
f1stewards regulatory-audit
f1stewards sporting-regulation-audit
f1stewards international-sporting-code-audit
f1stewards claim-audit
f1stewards validate-coding
f1stewards validate-impact
f1stewards review-status
f1stewards reconcile-pilot
f1stewards scale-readiness
f1stewards build-explorer
f1stewards export-snowflake-pilot
f1stewards validate-snowflake-export <export-directory>
f1stewards quality-check
pytest
```

Downloads are low-rate and resumable. Linked source files are checksummed; reruns reuse a verified
local file. The archive parser also records recalled documents that FIA advertises without a usable
download link, preventing silent loss of decision versions.

## Evidence and interpretation policy

- Every analytical record must link to an official source document.
- The regulation version active on the event date must be preserved.
- Initial, corrected, recalled, reviewed, and final decisions must not be conflated.
- No-action decisions are data, not missing values.
- An anomaly score is a review aid, not a declaration that the stewards were wrong.
- Nationality results must be adjusted, uncertainty-aware, and presented for accused and affected drivers separately.
- Exact classification arithmetic must be separated from strategy-dependent counterfactual estimates.

## Project status

Milestone 1 foundation is complete. The three-event archive pilot discovered 156 source records,
including two unavailable recalled records, and retrieved 67 selected evidence PDFs with no active
retrieval failures. All 26 linked steward-decision PDFs yielded a Decision section; 25 yielded the
full standard Fact/Infringement/Decision/Reason structure. FastF1 enrichment adds 60 classifications,
3,684 driver laps, and 285 race-control messages. Eleven pilot event-date FIA regulatory sources are
registered and validated. A separate 65-issue Sporting Regulation catalog covers every season from
2018 through 2025 and deterministically selects the candidate issue published by each event date;
the exact PDFs for all three pilot selections are resolved. A nine-issue International Sporting Code
catalog separately models effective windows, including the April 2020 revision and unresolved
publication metadata for older binaries. The nine candidate adjudications and
four impact assessments have an
AI-assisted first coding pass, but every row remains explicitly pending independent human review.
The separate 13-row review packet preserves corrections and measured review effort without
overwriting the first pass.
Completed reviews are reconciled into new content-addressed files with protected lineage fields,
whole-record validation, a field-level change log, and SHA-256 input/output manifests; the command
cannot overwrite a previously generated version.

A dependency-free pilot evidence explorer is also generated from the same DuckDB and curated manual
inputs. It exposes nine candidate adjudications and four impact assessments with exact filters,
official evidence links, data-quality state, build lineage, and a downloadable filtered extract.
The explorer remains visibly provisional, and comparable-case/model views remain unavailable until
independent review, reconciliation, full-corpus collection, and model validation pass their gates.

The optional Snowflake/Snowsight package exports 12 content-addressed Parquet tables, excludes
machine-specific cache paths, verifies every file hash/schema/count locally, and supplies worksheet
SQL for setup, fail-fast loads, evidence-linked views, 15 integrity controls, review gating, and
DuckDB/Snowflake parity checks. It is accurately labeled a validated deployment package until a real
account run records query IDs and load results.

The project is published at
[brianbzeng/f1-stewarding-analysis](https://github.com/brianbzeng/f1-stewarding-analysis).
No license has been selected.
