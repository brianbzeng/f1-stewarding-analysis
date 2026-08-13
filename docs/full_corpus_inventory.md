# Full-Corpus FIA Inventory

## Population contract

The study population is the 173 completed Formula One championship events in the 2018-2025
FastF1 schedules. Testing sessions are excluded. `config/study_events.csv` is the frozen,
deterministic contract: it preserves season, round, race date and UTC offset, event format, Sprint
status, stable event ID, guideline regime, archive system, and official FIA archive target.

| Season | Events | FIA source records | Outcome labels | Recalled outcomes | Parsed live outcomes | Content-confirmed decisions | Full labeled template | Format review |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2018 | 21 | 1,359 | 243 | 0 | 243 | 211 | 196 | 15 |
| 2019 | 21 | 952 | 264 | 0 | 264 | 264 | 242 | 22 |
| 2020 | 17 | 831 | 147 | 0 | 147 | 147 | 137 | 10 |
| 2021 | 22 | 1,044 | 175 | 0 | 175 | 175 | 159 | 16 |
| 2022 | 22 | 1,207 | 238 | 0 | 238 | 238 | 225 | 13 |
| 2023 | 22 | 1,283 | 259 | 0 | 259 | 259 | 227 | 32 |
| 2024 | 24 | 1,396 | 319 | 5 | 314 | 314 | 261 | 53 |
| 2025 | 24 | 1,390 | 357 | 14 | 343 | 343 | 280 | 63 |
| **Total** | **173** | **9,462** | **2,002** | **19** | **1,983** | **1,951** | **1,727** | **224** |

These are evidence-population counts, not final analytical adjudication counts. They deliberately
precede session, offence-family, document-version, referral, and eligibility rules.

## Outcome classification and parser audit

The title classifier covers the observed FIA outcome families `Decision`, `Infringement`, and
`Offence`, including legacy `Offence Doc...`, corrected, bulk, team, and organizer rulings. An exact
additional rule retains the 2022 Alonso penalty-point-total correction; a generic `penalty` keyword
is deliberately not used. A corpus-wide missed-outcome audit found no remaining `other` title with
decision, infringement, offence, penalty, disqualification, reprimand, warning, fine, appeal, or
Right of Review language.

The 2018 archive demonstrates why title and content typing must remain distinct. Its 243 outcome
labels resolve to 211 steward decisions, 29 summonses, two Race Director notes, and one Technical
Delegate referral. The pipeline preserves both classifications rather than rewriting source
history. Of the 211 actual decisions, 196 expose all four core labels; the remaining 15 are retained
for format review.

The 2019 archive exposes one further source-system anomaly: an Australian Grand Prix file declares
PDF content but serves a base64-wrapped PDF body. Retrieval accepts this only when strict base64
validation succeeds and the decoded bytes contain a PDF signature. The normalized file is then
checksummed like every other source. All 264 outcome-labelled 2019 files are genuine steward
decisions; 242 expose all four core labels and 22 remain in the format-review queue.

The FIA's 2020 Russian Grand Prix archive initially returned HTTP 404 for the second Car 7
pit-lane-speeding decision, while the older Event & Timing page exposed only the first decision. A
bounded retry later returned the valid, distinct Document 20 PDF. Its checksum and lineage are
retained separately from Document 17. No source is currently `verified_unavailable`; the explicit
exception mechanism remains available for future confirmed broken links without inferring content.

All 147 outcome-labelled 2020 files are genuine steward decisions. Of these, 137 expose all four
core labels and 10 narrative protest, driver-change, or event-procedure decisions require format
review.

All 175 outcome-labelled 2021 files are genuine steward decisions. Of these, 159 expose all four
core labels. The 16 format-review records include start permissions or withdrawal, protests and
Rights of Review, appeal deadlines, driver changes, and other session administration. They remain
valid decisions but do not enter incident-penalty comparisons without later eligibility coding.

All 238 outcome-labelled 2022 files are genuine steward decisions, with 225 exposing all four core
labels. The 13 format-review records include start permissions or withdrawal, schedule and starting
procedure decisions, protests, a power-unit cover-period extension, and the steward-issued Alonso
notice correcting his 12-month penalty-point total from three to five.

All 259 outcome-labelled 2023 files are genuine steward decisions. Of these, 227 expose all four
core labels and 32 use narrative or bulk formats. They include start permissions, session and team
administration, protests and reviews, the mandatory Sainz replacement-component penalty after Las
Vegas drain-cover damage, and Alonso's successful Saudi Arabian Right of Review reversing a
10-second penalty. The latter two remain visible for institutional-constraint and reversal analyses
rather than being grouped with routine incident penalties.

The 2024 archive contains 319 outcome labels, of which five are recalled records without live PDF
links. All 314 retrievable files are genuine steward decisions: 261 use all four core labels and 53
use narrative or bulk formats. One Austrian pit-lane-speeding PDF shifts its Fact, Infringement,
Decision, and Reason semantics one label to the left; it is retained for explicit human realignment
rather than silently rewritten. Mexico corrected Doc 47 is linked to recalled Doc 43. Four recalled
Belgian pit-speeding notices have no visible successor and remain explicit unavailable exclusions.

The 2025 archive contains 357 outcome labels: 343 live, content-confirmed decisions and 14 recalled
versions. The pipeline links every recalled 2025 decision to its visible successor, including title
and driver-number corrections; 280 live decisions use all four core labels and 63 require format
review. Three Hungarian rulings genuinely omit the Fact label while retaining the allegation,
decision, and reasoning.

Across all seasons, the 224 format-review records comprise 83 session or bulk rulings, 44
start/withdrawal decisions, 30 protests or reviews, 11 technical or team decisions, nine known
incident-source anomalies, and 47 legacy or other nonstandard decisions. These are retained as
valid document versions but require later analytical eligibility coding.

Parser v4 recognizes the exact observed FIA heading typo `Infringment`, repairs the exact observed
`InfringementBreach` extraction join, rejects lowercase prose fragments that resemble headings, and
records missing infringement as a first-class warning. All 1,983 live outcome PDFs were parsed with
v4 and no parser execution failures.

## Corrected and recalled lineage

`config/document_lineage.yml` records 15 verified corrected-successor relationships. The warehouse
requires each successor to point to one recalled predecessor in the same event and rejects duplicate
use of a predecessor. Fifteen of the 19 recalled outcomes are therefore linked. The four unresolved
records are the unavailable 2024 Belgian pit-speeding notices, for which the archive exposes no live
successor. Their contents are not inferred and they are excluded from analytical denominators.

## Archive systems

- For 2019-2025, the collector uses the FIA decision-document archive and its published timestamps.
- For 2018, the collector follows the older event page to its Event & Timing Information page and
  extracts document cards. Those pages expose dates but not reliable publication times, so the
  pipeline records the source date string and does not invent timestamp precision.
- Six early-2018 landing pages lost their timing-page handoff during an FIA site migration. Their
  official timing URLs are explicit `archive_url_overrides` in `config/full_collection.yml`.
- Five 2021-2023 Mexico/Brazil archive pages require the FIA's historical event label rather than
  the corresponding FastF1 display name. Their transformations are explicit
  `archive_event_overrides` in the same configuration file.

Configuration, rather than hidden scraper branches, is the audit trail for these exceptions.

## Reproducibility and controls

1. `f1stewards build-study-catalog` regenerates the population from completed FastF1 schedules and
   prints the CSV SHA-256 digest.
2. Expected event counts are fixed by season. Missing schedules, unexpected counts, duplicate
   event IDs, duplicate season/round pairs, missing pilot events, and orphan URL overrides fail
   catalog generation.
3. `f1stewards study-discover` writes content-addressed source lineage to Parquet and DuckDB while
   retaining an event-level retry queue. The default `decisions` profile retrieves the bounded
   outcome set; broader adjudication and impact profiles are explicit in
   `config/evidence_profiles.yml`.
4. `f1stewards study-inventory` reconciles document IDs and event coverage across the catalog,
   Parquet manifest, DuckDB, and failure queue. It exits nonzero on any mismatch by default.
5. `f1stewards quality-check` requires every frozen event to resolve to source evidence and enforces
   source availability, corrected-document lineage, parser, and curated-data controls.

At the 2026-08-12 checkpoint, all 173 events were covered; Parquet and DuckDB each contained 9,462
unique source-document IDs; no catalog event was missing evidence; and the active discovery and
retrieval failure counts were zero. Bounded outcome retrieval and parser-v4 content typing were
complete for all eight seasons.

## Interpretation boundary

Inventory coverage does not establish analytical eligibility. Before modeling, the pipeline must
resolve document versions, separate summonses from outcomes, restrict sessions and incident
families, code multi-party relationships, and quantify all parsing, review, and eligibility
exclusions. Every later denominator must trace back to this frozen population and publish its
attrition counts.

The checksum-protected full-corpus seed now supplies that traceable bridge: 2,002 document-version
review rows and 1,951 live decision seeds reconstruct exactly from the warehouse. Final inclusion,
accused-driver normalization, incident grouping, and independent review remain pending; see
`docs/full_corpus_coding_workflow.md`.
