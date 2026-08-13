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
config/       machine-readable source, full-population, and pilot configuration
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

The three-event feasibility pilot and its expanded manual-review gate are complete. The frozen
full-study catalog now contains all 173 completed championship events from 2018 through 2025.

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
f1stewards validate-harm
f1stewards validate-extensions
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

## Full-study inventory commands

```powershell
f1stewards build-study-catalog
f1stewards study-catalog
f1stewards init-study-db
f1stewards study-discover
f1stewards study-discover --download --download-profile decisions
f1stewards study-inventory
f1stewards build-full-coding-queues
f1stewards audit-full-coding-queues
f1stewards study-fastf1 --max-sessions 5
f1stewards study-fastf1-inventory --strict
f1stewards load-steward-panels --strict-extraction
f1stewards load-steward-country-evidence
```

`build-study-catalog` freezes FastF1 schedules into stable event IDs and FIA archive targets;
`study-discover` inventories official documents without downloading PDFs unless `--download` is
supplied. The strict `study-inventory` control exits nonzero if the event catalog, Parquet manifest,
DuckDB lineage, or active failure queue disagree. Historical FIA URL exceptions are declared in
configuration and covered by tests. See [the full-corpus inventory](docs/full_corpus_inventory.md).
Retrieval profiles are declared in `config/evidence_profiles.yml`; the default `decisions` profile
avoids downloading summonses, classifications, notes, and circuit maps before they are needed.

## Evidence and interpretation policy

- Every analytical record must link to an official source document.
- The regulation version active on the event date must be preserved.
- Initial, corrected, recalled, reviewed, and final decisions must not be conflated.
- No-action decisions are data, not missing values.
- An anomaly score is a review aid, not a declaration that the stewards were wrong.
- Nationality results must be adjusted, uncertainty-aware, and presented for accused and affected drivers separately.
- Exact classification arithmetic must be separated from strategy-dependent counterfactual estimates.

## Project status

The full 2018-2025 event inventory is complete. All 173 cataloged events have official FIA evidence:
9,462 source-document records, including 2,002 outcome labels and 45 recalled notices across all
document classes. Nineteen recalls are outcome records: 15 link to verified corrected successors
and four unavailable Belgian versions remain explicit exclusions. All 1,983 live outcome PDFs are
retrieved and parsed with parser v4, yielding 1,951 content-confirmed steward decisions and zero
active discovery or retrieval failures. The frozen Parquet manifest and DuckDB lineage agree
exactly. The next milestone is full-corpus analytical eligibility and adjudication coding before
statistical modeling; its protected machine-seed layer is complete and human disposition remains.

The first full-corpus coding bridge is now reproducible and checksum-protected. Its document queue
retains all 2,002 outcome labels, and its adjudication seed retains all 1,951 live,
content-confirmed decisions. Deterministic rules currently prioritize 260 primary Race/Sprint
candidates and 66 secondary qualifying-impeding candidates; 320 ambiguous session or offence-family
records remain mandatory manual review rather than automatic conclusions. The counts are triage
workload, not final study results. A deterministic 403-row sample spans all 223 observed
season/session/family exclusion strata so proposed exclusions receive a reproducible false-exclusion
audit. See [the full-corpus coding workflow](docs/full_corpus_coding_workflow.md).
The [first exclusion-QA diagnostic](docs/exclusion_qa_audit.md) documents an actual 2021 session-
terminology false-exclusion mechanism, the corrective regeneration, and the remaining human gate.
The [full FastF1 collection method](docs/full_fastf1_collection.md) now covers all 197 expected
Race/Sprint sessions: 3,938 classifications, 198,620 driver laps, and 16,039 Race Control messages.
Strict completeness and 35 warehouse controls pass. All laps remain available for incident timing,
while 162,383 satisfy the conservative pace-model gate. Timestamp, normalization, and known
historical source gaps remain explicit rather than imputed.

The [steward-panel extraction](docs/steward_panel_extraction.md) now assigns all 1,951 live
decisions at document grain: 1,935 signatures parse directly, 16 use a bounded single-panel event
consensus, and none remain unresolved. The resulting 181 panels preserve seven events with
within-weekend substitutions and identify 83 stewards. Every extraction control passes; panel-
nationality analysis remains explicitly blocked until all steward nationalities have source-backed
lineage.

The follow-on [steward-country evidence ledger](docs/steward_country_evidence.md) currently holds
92 dated official-source records for 82 of the 83 stewards. It keeps raw and normalized codes
separate and exposes an official-source `BEL`/`LUX` conflict rather than forcing a static value.
Panel identity is usable as adjustment context; steward-country comparisons remain blocked.

The content-addressed [full-corpus coding workspace](docs/full_corpus_coding_workspace.md) now joins
all 1,951 adjudication starters to protected source lineage and the complete timing-quality context.
All 260 primary candidates resolve to a loaded Race/Sprint session and accused-driver
classification. Exact-starter and edited-workspace validators separately protect reproducibility
while permitting final fields and traceable one-to-many adjudication splits. Human disposition and
independent review remain required before substantive modeling. The executed
[full-corpus readiness notebook](notebooks/04_full_corpus_readiness.ipynb) presents the denominator,
seasonal review workload, SQL candidate profile, timing coverage, and explicit blocked model gate.

The [gated analysis feature release](docs/analysis_feature_release.md) materializes one
adjudication-grain table and a separate accused/affected driver-role bridge in DuckDB. Its current
build contains 260 provisional candidates and 503 role rows with complete sourced identity joins;
eight ambiguous `other` outcomes remain outside the binary design set. All reporting flags remain
false because document, adjudication, and exclusion-QA human review has not begun. Exact
document-panel identity is now joined for all 260 candidate rows and hashed into the feature-build
lineage; steward-country exposure remains separately blocked by its evidence gate. The feature
schema can therefore support model engineering and overlap diagnostics without leaking unreviewed
suggestions into the eventual report.

The [grouped validation and nationality design method](docs/model_validation_method.md) is now
frozen in configuration and tested. Outcome validation enforces event-grouped folds and refuses
the current unreviewed labels. The separate outcome-free notebook finds limited nationality
support—34 British versus 226 other provisional accused-driver rows, no British exposure in
2018–2020, and 76.5% estimated common support. Across 4,000 stable cluster-robust simulations, no
assumed 5–20 point difference reaches the predefined 80% power target. This is a design warning,
not an effect estimate; absent material improvement after human coding, the nationality result will
be reported as descriptive or inconclusive.

Competitive-impact arithmetic now validates ordered same-lap classifications, preserves official
order on exact ties, calculates standard Race/Sprint position points and podium/win changes, and
separately classifies exact, saturated, or confounded grid displacement. The enhanced validator
reproduces both reviewed mechanical pilot cases—including Pérez's P4-to-P2, 12-to-18-point change—
without treating an in-race served penalty or a grid drop as a mechanical finish counterfactual.

Milestone 1 foundation is complete. The three-event archive pilot discovered 156 source records,
including two unavailable recalled records, and retrieved 67 selected evidence PDFs with no active
retrieval failures. Of 26 linked steward-decision PDFs, 25 yielded a complete Decision section and
the full standard Fact/Infringement/Decision/Reason structure. FastF1 enrichment adds 60 classifications,
3,684 driver laps, and 285 race-control messages. Eleven pilot event-date FIA regulatory sources are
registered and validated. A separate 65-issue Sporting Regulation catalog covers every season from
2018 through 2025 and deterministically selects the candidate issue published by each event date;
the exact PDFs for all three pilot selections are resolved. A nine-issue International Sporting Code
catalog separately models effective windows, including the April 2020 revision and unresolved
publication metadata for older binaries. The nine candidate adjudications, four impact assessments,
and two mirrored harm assessments retain their protected AI-assisted first pass. The separate
original 15-row independent review is complete with 15 agreements, no corrections, and no
unresolved discussions.
Reconciliation `pilot-0681d52afdea` promotes immutable copies to `double_coded` while preserving the
first pass, review notes, protected lineage fields, a field-level audit, and SHA-256 input/output
manifests.

The approved second-stage extension is implemented without altering that release. The staging layer
now contains nine affected-driver harm rows (one per adjudication), one source-preserving turn range,
two directed edges for a three-car interaction, and one cross-event sanction record. All 26 review
targets agree with no corrections or unresolved discussions. Reconciliation `pilot-41f4502411c2`
packages the expanded v3 schema as a separate immutable `double_coded` release.

A dependency-free pilot evidence explorer is also generated from the same DuckDB and curated manual
inputs. The current reviewed build exposes nine candidate adjudications, four sanction-impact
assessments, nine victim-harm rows, source-preserving incident context, and the exact P7-to-P10
application of Antonelli's carried grid penalty. Official evidence links, data-quality state, build
lineage, and a downloadable filtered extract remain visible. Comparable-case and model views remain
unavailable until the full corpus is collected and model validation passes its gates.

The optional Snowflake/Snowsight package exports 16 content-addressed Parquet tables, excludes
machine-specific cache paths, verifies every file hash/schema/count locally, and supplies worksheet
SQL for setup, fail-fast loads, evidence-linked views, 24 integrity controls, review gating, and
DuckDB/Snowflake parity checks. It is accurately labeled a validated deployment package until a real
account run records query IDs and load results.

The project is published at
[brianbzeng/f1-stewarding-analysis](https://github.com/brianbzeng/f1-stewarding-analysis).
No license has been selected.
