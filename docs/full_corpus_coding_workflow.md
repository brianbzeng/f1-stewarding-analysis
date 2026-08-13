# Full-Corpus Coding Workflow

Status: machine-generated seed bundle complete; final human eligibility and adjudication coding
pending.

## Purpose

The full-corpus queues bridge the frozen FIA inventory and the analytical unit of one accused-driver
adjudication. They preserve the complete denominator while using deterministic text rules only to
prioritize review. A suggestion is not a final scope, fault, sanction-consistency, or fairness
finding.

The protected seed bundle is in `data/manual/full_corpus_seed/`:

| File | Unit | Frozen rows | Purpose |
|---|---:|---:|---|
| `document_review_queue.csv` | one FIA archive outcome label | 2,002 | version, content, session, offence-family, and eligibility review |
| `adjudication_seed_queue.csv` | one live content-confirmed decision document | 1,951 | source-rich starting rows that may be split, grouped, or excluded after review |
| `exclusion_qa_sample.csv` | one proposed exclusion selected by frozen hash | 403 | stratified false-exclusion audit across season, session scope, and offence family |
| `manifest.json` | one seed release | 1 | source/config hashes, output hashes, row counts, and suggestion counts |

Run:

```powershell
f1stewards build-full-coding-queues
f1stewards audit-full-coding-queues
```

The builder refuses to replace a differing bundle unless `--overwrite` is explicitly supplied. Use
that option only after an intentional warehouse or rule change. The audit reconstructs all four
files from DuckDB and fails if any byte differs.

## Denominator and attrition contract

The document queue retains all 2,002 FIA archive labels classified as outcomes:

- 1,951 live PDFs content-confirmed as steward decisions;
- 32 live labels whose bodies are summonses, Race Director notes, or another non-decision type;
- 15 recalled labels with a verified corrected successor; and
- 4 recalled Belgian pit-speeding labels with no recoverable successor.

Only the 1,951 live, content-confirmed decisions seed possible adjudication rows. This is not the
final study population: session, offence family, document format, accused-driver unit, and referral
eligibility still require review.

The version rules are structural:

- `live_standalone` and `corrected_successor` can seed review;
- `recalled_linked_predecessor` stays in provenance but receives a version-exclusion suggestion;
- `recalled_unresolved` requires an explicit disposition; and
- every successor retains `supersedes_document_id`.

No recalled record silently becomes a no-action decision or a missing outcome.

## Machine-suggestion boundary

The frozen patterns in `config/full_corpus_coding.yml` classify only text observed in the title,
Fact, and Infringement sections. They do not infer an offence from penalty severity. The rule order
reflects the protocol's primary families, the qualifying-impeding secondary population, and common
strict-liability or administrative exclusions.

Session normalization is era-aware. In 2021, FIA used “Sprint Qualifying” for the Saturday sprint
race, so those records normalize to `Sprint`; from 2024, the same phrase denotes the qualifying
session that sets the Sprint grid. This distinction was found by the first exclusion-QA audit and is
covered by regression tests.

Current review triage is:

| Suggestion | Rows | Meaning |
|---|---:|---|
| `primary_candidate` | 260 | Race/Sprint source matched one and only one primary family |
| `secondary_candidate` | 66 | qualifying source matched only qualifying impeding |
| `manual_offence_review` | 254 | unclassified or analytically conflicting family language |
| `manual_session_review` | 66 | no reliable session label and no higher-priority version/content disposition |
| `out_of_scope_suggestion` | 1,305 | recognized exclusion or out-of-scope session |
| `content_exclusion_suggestion` | 32 | archive label is not a decision when its body is inspected |
| `version_exclusion_suggestion` | 15 | recalled predecessor has a linked live successor |
| `version_resolution_required` | 4 | recalled version has no recoverable successor |

These counts are workload measures, not reportable incident counts. In particular, legacy titles
such as “Incident with Car” remain manual review cases because the title alone does not distinguish
causing a collision, forcing off track, a racing incident, or another allegation. A source that
matches families across analytical groups, or more than one in-scope family, also stays manual
rather than inheriting the first regex match. Multiple strict-liability labels may remain a proposed
exclusion, with every matched family retained for audit.

## Review sequence

1. Copy the protected seed files into a dated or content-addressed working directory. Never edit the
   seed release in place.
2. Resolve the 19 recalled outcomes and 32 content mismatches first. Preserve linked predecessors
   even when they are excluded from the effective analytical version.
3. Review every `primary_candidate`, `secondary_candidate`, `manual_offence_review`, and
   `manual_session_review` row against the official PDF. Complete every final field or give a
   controlled exclusion reason.
4. Review parser-warning documents from the PDF rather than treating missing headings as missing
   decisions. Legacy and bulk formats can contain valid adjudications.
5. Split documents that adjudicate multiple accused drivers into separate rows. Conversely, group
   multiple document versions or mirrored driver decisions into the same `incident_id` when the
   evidence supports one underlying incident.
6. Deduplicate the final analytical version before creating `CodedAdjudication` records. A corrected
   successor becomes the source document; the predecessor remains provenance.
7. Independently review inclusion, incident grouping, offence family, outcome, and highlighted case
   studies. Record disagreement rather than silently overwriting the first code.
8. Publish an attrition table from 2,002 labels to final adjudications, with a count and reason for
   every exclusion stage.

The frozen rules select 403 of the 1,305 out-of-scope suggestions across all 223 observed
season/session/family strata. Selection uses a documented SHA-256 ordering, a 10% target, at least
two rows per non-singleton stratum, and at most eight rows per stratum. This is a review workload,
not a statistical estimate of an error rate. Any discovered
false exclusion triggers a rule audit and full regeneration, not a one-row exception hidden in a
notebook.

## Multi-car and harm handoff

`participant_driver_numbers_suggestion` retains every Car number that the deterministic extractor
finds, while `affected_driver_numbers_suggestion` removes only the parsed accused driver. These are
review aids. They do not assign fault or claim that every mentioned driver was harmed.

After incident grouping, the approved extension tables are populated separately:

- one directed `IncidentRelation` per supported link in a multi-car chain;
- one `HarmAssessment` per affected driver whose consequence is evaluated;
- one `ImpactAssessment` for the burden imposed on a sanctioned driver; and
- one `CrossEventSanctionEffect` when a grid sanction is applied at a later event.

Damage, repair stops, position loss, relative-time loss, persistent pace loss, retirement, and a
possibly beneficial forced stop remain separate fields. No generic pit-stop cost or composite
fairness score is allowed. Harm-to-sanction proportionality is assessed only after responsibility
status is independently reviewed.

## Acceptance gate before modeling

Statistical work cannot begin until:

- every document label has a reviewed disposition;
- every included row has one effective source version and one accused-driver adjudication;
- every exclusion has a controlled reason;
- incident IDs and multi-party relations pass linkage validation;
- no pending or `needs_discussion` review target remains in the analytical release; and
- frozen-population, queue, curated-table, and attrition counts reconcile exactly.
