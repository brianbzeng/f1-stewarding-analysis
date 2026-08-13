# Full-Corpus FIA Inventory

## Population contract

The study population is the 173 completed Formula One championship events in the 2018-2025
FastF1 schedules. Testing sessions are excluded. `config/study_events.csv` is the frozen,
deterministic contract: it preserves season, round, race date and UTC offset, event format, Sprint
status, stable event ID, guideline regime, archive system, and official FIA archive target.

| Season | Events | FIA source records | Steward decisions | Recalled notices |
|---:|---:|---:|---:|---:|
| 2018 | 21 | 1,359 | 175 | 0 |
| 2019 | 21 | 952 | 250 | 0 |
| 2020 | 17 | 831 | 123 | 0 |
| 2021 | 22 | 1,044 | 162 | 0 |
| 2022 | 22 | 1,207 | 225 | 0 |
| 2023 | 22 | 1,283 | 217 | 0 |
| 2024 | 24 | 1,396 | 251 | 17 |
| 2025 | 24 | 1,390 | 277 | 28 |
| **Total** | **173** | **9,462** | **1,680** | **45** |

These are discovery counts, not final analytical adjudication counts. They deliberately precede
session, offence-family, document-version, referral, and exclusion rules.

The 2018 archive demonstrates why that distinction matters: its labels call all 175 retrieved files
“Stewards Decision,” while content typing identifies 143 steward decisions, 29 summonses, two Race
Director notes, and one Technical Delegate referral. The pipeline preserves both the archive label
and content-derived class rather than rewriting source history.
Of the 143 actual 2018 decisions, 130 (90.9%) expose the standard labeled Decision section. The
remaining 13 are retained in an explicit manual-review queue; they are mostly permissions to start,
re-scrutineering rulings, protests, or event-wide procedural decisions rather than silently failed
parses.

The 2019 archive exposes one further source-system anomaly: an Australian Grand Prix file declares
PDF content but serves a base64-wrapped PDF body. Retrieval accepts this only when strict base64
validation succeeds and the decoded bytes contain a PDF signature. The normalized file is then
checksummed like every other source. All 250 decision-labelled 2019 files are genuine steward
decisions; 231 (92.4%) expose the standard labeled Decision section and 19 remain in the explicit
nonstandard-format review queue.

The FIA's 2020 Russian Grand Prix archive initially returned HTTP 404 for the second Car 7
pit-lane-speeding decision, while the older Event & Timing page exposed only the first decision.
A bounded retry later returned the valid, distinct Document 20 PDF. Its checksum and lineage are
retained separately from the earlier Document 17 decision. No source is currently classified as
`verified_unavailable`; the explicit exception mechanism remains available for future confirmed
broken links without allowing their contents to be inferred.

All 123 decision-labelled 2020 files are genuine steward decisions. Every file exposes the standard
Fact, Offence, Decision, and Reason sections, so the season has no parser-format review cases.

All 162 decision-labelled 2021 files are also genuine steward decisions. Of these, 155 (95.7%)
expose the standard labeled sections. The seven format-review records are narrative administrative
decisions: five permissions to start after failing to set a qualifying time, one permission to
start Sprint Qualifying, and one force-majeure withdrawal approval. They are retained as valid
decisions but do not enter incident-penalty comparisons without later eligibility coding.

All 225 decision-labelled 2022 files are genuine steward decisions, with 220 (97.8%) using the
standard labeled sections. The five narrative-format records comprise three permissions to start,
one withdrawal approval, and one extension to the power-unit cover period caused by delayed FIA
personnel availability. As in 2021, these administrative decisions remain auditable but are not
eligible for incident-penalty comparisons without later coding.

All 217 decision-labelled 2023 files are genuine steward decisions. Of these, 205 (94.5%) expose
the full labeled template and 12 use narrative formats: nine permissions to start, one Sprint
withdrawal, the mandatory Sainz replacement-component penalty after Las Vegas drain-cover damage,
and Alonso's successful Saudi Arabian Right of Review reversing a 10-second penalty. The latter two
remain visible for later institutional-constraint and reversal analyses rather than being grouped
with routine incident penalties. Forty-seven standard documents reproduce the FIA heading typo
`Infringment`; parser v3 recognizes that exact observed spelling while rejecting lowercase prose
fragments that previously resembled headings.

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

The configuration, rather than hidden scraper branches, is the audit trail for these exceptions.

## Reproducibility and controls

1. `f1stewards build-study-catalog` regenerates the population from completed FastF1 schedules and
   prints the CSV SHA-256 digest.
2. Expected event counts are fixed by season. Missing schedules, unexpected counts, duplicate
   event IDs, duplicate season/round pairs, missing pilot events, and orphan URL overrides fail
   catalog generation.
3. `f1stewards study-discover` writes the content-addressed source lineage to Parquet and DuckDB,
   while retaining an event-level retry queue for archive failures. With `--download`, its default
   `decisions` evidence profile retrieves only steward outcomes; broader adjudication and impact
   profiles are explicit in `config/evidence_profiles.yml`.
4. `f1stewards study-inventory` reconciles document IDs and event coverage across the catalog,
   Parquet manifest, DuckDB, and failure queue. It exits nonzero on any mismatch by default.
5. `f1stewards quality-check` separately requires every frozen event to resolve to at least one
   source document and enforces the existing lineage and curated-data controls.

At the 2026-08-12 checkpoint, all 173 events were covered; Parquet and DuckDB each contained 9,462
unique source-document IDs; no catalog event was missing evidence; and the active discovery-failure
queue contained zero rows. Bounded decision retrieval and content typing were complete through the
2023 season, with no active retrieval failures.

## Interpretation boundary

Inventory coverage does not establish adjudication completeness by itself. Before modeling, the
pipeline must download the bounded decision evidence, parse document versions, resolve corrected
and recalled lineage, separate summonses from outcomes, restrict the analytical sessions and
incident families, and quantify unresolved parsing or coding exclusions. All later denominators
must trace back to this frozen population and publish their attrition counts.
