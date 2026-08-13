# The Cost of Discretion

An auditable analysis of consistency, potential nationality effects, and competitive impact in Formula One stewarding decisions from 2018 through 2025.

This project treats stewarding decisions as regulatory evidence, not fan opinion. Its purpose is to determine whether formally adjudicated driving incidents receive comparable treatment after accounting for observable context, and to prioritize unusual decisions for human review. It does **not** claim that a statistical model can determine fault or prove misconduct.

## Final report

Read the recruiter-facing [report landing page](reports/README.md), open the
[executable Jupyter report](notebooks/06_final_oversight_report.ipynb), or download the
[code-free HTML edition](reports/the_cost_of_discretion.html). The central finding is that nominal
penalty severity and realized competitive burden are different quantities. The independently
reviewed pilot demonstrates that distinction. A disclosed GPT-5.6 Sol review releases 346 primary
cases for descriptive analysis; the report does not present that model review as independent human
assurance. The broad consistency model is weak and the nationality result remains inconclusive.

The follow-on [Study v2 progress report](reports/the_cost_of_discretion_study_v2.html) implements
the original report's six improvement recommendations. Its executable sequence is notebooks
[07](notebooks/07_study_v2_protocol_and_review.ipynb) through
[12](notebooks/12_study_v2_report.ipynb). It adds a risk-based human-review packet, a public Race
Control referral funnel, validated incident-lap windows, outcome-blind close-case matching,
driver-level harm records, damage-source research, and a gated nationality diagnostic. Results that
still need human judgment remain withheld.

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

## Full-corpus review commands

```powershell
f1stewards build-full-corpus-review-explorer `
  data/manual/full_corpus_workspaces/full-coding-e0192ecbd9e4
f1stewards build-full-corpus-first-pass `
  data/manual/full_corpus_workspaces/full-coding-e0192ecbd9e4
f1stewards build-full-corpus-exception-packet `
  data/manual/full_corpus_first_pass/full-coding-e0192ecbd9e4
f1stewards apply-full-corpus-review-ledger `
  data/manual/full_corpus_first_pass/full-coding-e0192ecbd9e4 `
  <exported-review-ledger.json>
f1stewards validate-edited-full-coding-workspace `
  data/manual/full_corpus_review_edits/full-coding-e0192ecbd9e4
python scripts/build_model_review_release.py
f1stewards build-analysis-features `
  data/manual/full_corpus_model_review/model-review-3dacc1268f13/full-coding-e0192ecbd9e4 `
  --strict-release
```

The generated [full-corpus review console](explorer/full_corpus_review.html) exposes every document,
adjudication, and stratified exclusion-QA target while preserving the original human-review gate.
Browser drafts export only editable final fields in a ledger locked to the current workspace hash;
the apply command writes a separate workspace and reruns protected-lineage validation.

The disclosed [GPT-5.6 Sol review protocol](docs/model_review_protocol.md) maps the 4,441 queue
obligations to 2,003 unique FIA records, records source-backed corrections, and writes a separate
content-addressed workspace. It is a model-led second pass, not independent human review.

## Study v2 commands

```powershell
python scripts/build_study_v2_review_packet.py
python scripts/build_study_v2_referral_funnel.py
python scripts/build_study_v2_incident_clock.py
python scripts/build_study_v2_incident_context.py
python scripts/build_study_v2_close_cases.py
python scripts/build_study_v2_damage_screening.py
python scripts/build_study_v2_layers.py
python scripts/build_study_v2_nationality.py
python scripts/build_study_v2_notebooks.py
python scripts/audit_study_v2_completion.py
```

The [Study v2 protocol](docs/study_v2_protocol.md) is the controlling design. The human review and
damage-evidence worklists are intentionally unfinished so an independent reviewer can complete them
without seeing model answers. The final command writes a requirement-level
[completion audit](reports/generated/study_v2/completion_audit.csv) and fails if any frozen artifact,
gate, notebook, or report phase is missing. The notebook command builds and executes notebooks
07-12 and exports the integrated HTML report in one reproducible step.

The conservative [machine-assisted first pass](docs/full_corpus_first_pass.md) prepopulates 1,903
document dispositions and 1,856 adjudication rows as `single_coded_pending_human`. This includes
207 clearly out-of-scope parser-warning sources in each worklist, but never a parser-warning
inclusion. It leaves 100 document exceptions, 96 adjudication exceptions, and all 486 exclusion-QA
judgments unstarted. The generated
[first-pass review console](explorer/full_corpus_first_pass_review.html) exposes those assignments
without counting any as independent review.

The current content-addressed [exception investigation packet](docs/full_corpus_exception_packet.md)
is `exception-packet-2e9bc5621dfa`. It collapses the 682 unresolved independent-review queue rows to
582 unique FIA documents, eliminating 100 duplicate
source reviews. It gives every investigation a root cause, priority, linked queue IDs, official URL,
available Fact/Decision/Reason evidence, and review question. The QA console now carries the same
linked decision evidence for all 486 sampled exclusions.

The subsequent [parser-format source review](docs/parser_format_source_review.md) records final
fields for the 17 remaining nonstandard-format investigations: 16 controlled exclusions and one
included Hungarian no-action adjudication. Its versioned ledger changes no protected field and
keeps every row `single_coded_pending_human`; the review console now shows 1,920 document and 1,873
adjudication rows pending human confirmation, with 83 and 79 respectively still unstarted.

The next [analytical-scope conflict review](docs/analytical_scope_conflict_review.md) records all 18
cross-family/session decisions: eight secondary Qualifying-impeding inclusions and ten exclusions.
It also preserves a previously unlinked corrected Italian decision by coding its matching earlier
version as superseded. The chained console now shows 1,938 document and 1,891 adjudication rows
pending human confirmation, leaving 65 and 61 respectively unstarted.

The follow-on 61-case manual-scope ledger records 52 source-coded primary inclusions and nine
controlled exclusions, including mirrored and multi-car incident structure. A final archive-level
ledger preserves the four unavailable recalled 2024 Belgian pit-lane-speeding versions without
imputing their missing outcomes. The complete four-step review chain is content-addressed at
workspace SHA-256 `e1d4c4a969aee29b3db2a4f65e253e444c2e0c7d735cc3ec5451e3ec7b883f8f`.
Every source-coded record remains `single_coded_pending_human`; none is mislabeled as independent
review.

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
9,467 source-document records, including 2,003 outcome labels and 45 recalled notices across all
document classes. Nineteen recalls are outcome records: 15 link to verified corrected successors
and four unavailable Belgian versions remain explicit exclusions. All 1,984 live outcome PDFs are
retrieved and parsed with parser v4, yielding 1,952 content-confirmed steward decisions and zero
active discovery or retrieval failures. The frozen Parquet manifest and DuckDB lineage agree
exactly. The disclosed model-review tier now releases 346 primary cases; independent human review
remains a separate future assurance layer.

The first full-corpus coding bridge is now reproducible and checksum-protected. Its document queue
retains all 2,003 outcome labels, and its adjudication seed retains all 1,952 live,
content-confirmed decisions. The initial deterministic rules supplied triage, not findings. The
second pass reviewed all session and offence-family conflicts and a deterministic 486-row exclusion
sample spanning all 272 observed season/session/family strata. See the
[full-corpus coding workflow](docs/full_corpus_coding_workflow.md) and the original
[exclusion-QA diagnostic](docs/exclusion_qa_audit.md), which records the first-pass false-exclusion
mechanism before the model-reviewed release.
The [full FastF1 collection method](docs/full_fastf1_collection.md) now covers all 197 expected
Race/Sprint sessions: 3,938 classifications, 198,620 driver laps, and 16,039 Race Control messages.
Strict completeness and 38 warehouse controls pass. All laps remain available for incident timing,
while 162,383 satisfy the conservative pace-model gate. Timestamp, normalization, and known
historical source gaps remain explicit rather than imputed.

The [steward-panel extraction](docs/steward_panel_extraction.md) now assigns all 1,952 live
decisions at document grain: 1,936 signatures parse directly, 16 use a bounded single-panel event
consensus, and none remain unresolved. The resulting 181 panels preserve seven events with
within-weekend substitutions and identify 83 stewards. Every extraction control passes; panel-
nationality analysis remains explicitly blocked until all steward nationalities have source-backed
lineage.

The follow-on [steward-country evidence ledger](docs/steward_country_evidence.md) currently holds
92 dated official-source records for 82 of the 83 stewards. It keeps raw and normalized codes
separate and exposes an official-source `BEL`/`LUX` conflict rather than forcing a static value.
Panel identity is usable as adjustment context; steward-country comparisons remain blocked.

The content-addressed [full-corpus coding workspace](docs/full_corpus_coding_workspace.md) joins all
1,952 adjudication starters to protected source lineage and timing-quality context. The original
first pass remained explicitly pending human review and produced no reportable outcome estimate.
The separate [full-corpus review console](docs/full_corpus_review_console.md) preserves that human
workflow for future independent assurance.

The disclosed [GPT-5.6 Sol review](docs/model_review_protocol.md) provides a separate assurance
tier. It covers all 4,441 queue obligations across 2,003 unique FIA records, records 16 version-
history corrections plus sanction-field corrections, and leaves zero unresolved rows. Four recalled
sources remain metadata-only exclusions. The resulting build, `features-57542b24ea9f`, releases 346
primary cases under `reportable_model_reviewed`; it does not relabel model work as human review.

The [gated analysis feature release](docs/analysis_feature_release.md) materializes one
adjudication-grain table and a separate accused/affected driver-role bridge in DuckDB. All release
controls now pass for the model-reviewed tier: 2,003 source dispositions, 1,952 adjudication codings,
486 exclusion checks, complete identities, and complete binary outcomes. Steward-country exposure
remains separately blocked by its evidence gate.

The [grouped validation and nationality method](docs/model_validation_method.md) is frozen in
configuration and tested. Event-grouped outcome validation on 346 cases finds little predictive
value in incident type, season, and multi-car status (ROC AUC 0.558). The released population has
44 British and 302 other accused-driver cases. The raw sanction-rate difference is descriptive, and
power remains too low for subtle effects, so the final report labels nationality inconclusive.

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
