# Analytical Data Model

The warehouse separates source documents, incidents, adjudications, people, rules, and outcomes so that corrected documents and multi-driver incidents cannot be silently double-counted.

## Core grain

| Table | Grain |
|---|---|
| `events` | one championship event |
| `regulatory_sources` | one versioned governing instrument or published guideline |
| `event_regulatory_sources` | one source assignment to one event |
| `sessions` | one event session |
| `source_documents` | one retrieved document version |
| `incidents` | one underlying on-track incident |
| `adjudications` | one accused driver in one incident |
| `decisions` | one versioned steward outcome for an adjudication |
| `decision_lineage` | one supersession/review relationship |
| `stewards` | one steward identity |
| `event_stewards` | one steward assignment at one event |
| `rule_versions` | one version of one regulatory document |
| `rule_provisions` | one article/provision within a rule version |
| `guideline_sanctions` | one offence-session-guideline recommendation |
| `classifications` | one driver result in one session and classification version |
| `impact_estimates` | one counterfactual method for one adjudication |

The implemented pilot enrichment also keeps `fastf1_results`, `fastf1_laps`, and
`fastf1_race_control_messages` in the raw schema. `result_time_seconds` preserves FastF1's source
semantics; `classification_gap_seconds` normalizes the winner to zero so same-lap re-ranking cannot
accidentally compare the winner's total elapsed time with another driver's gap.

## Decision lineage

`source_documents.status` distinguishes active, recalled, corrected, and superseded files. `decisions.is_final` identifies the analytical outcome. A partial unique index prevents more than one final decision per adjudication.

The lineage table supports:

```text
summons -> initial decision -> corrected decision -> Right of Review -> final outcome
```

## Controlled fields

Canonical outcome values:

- `no_further_action`
- `warning`
- `reprimand`
- `black_white_flag`
- `time_penalty`
- `drive_through`
- `stop_go`
- `grid_drop`
- `disqualification`
- `other`

Canonical incident families are defined in the codebook and never inferred solely from penalty severity.

## Circularity flags

Each analytical feature records its provenance:

- `source_observed`: timing, classification, or event record;
- `decision_narrative`: extracted from the steward's reasoning;
- `manual_observed`: coder interpretation from publicly available evidence;
- `derived`: deterministic transformation;
- `model_generated`: prediction or simulation.

Features derived from the conclusion being predicted must be excluded or isolated in explicitly conditional models.

## Data lineage fields

DuckDB cannot enforce foreign keys across schemas. Cross-schema lineage is therefore
implemented as named zero-row checks in `sql/quality_checks.sql`; same-schema relationships
retain database constraints. This limitation and its compensating control are part of the
technical record.

All principal tables include:

- `created_at_utc`;
- `pipeline_version`;
- source document or source-record identifier;
- validation status;
- manual-review status where relevant.

Large timing tables remain partitioned Parquet and are queried through DuckDB views rather than copied unnecessarily into the database file.

## Snowflake portability boundary

The optional pilot export maps 12 bounded metadata, raw, curated, and audit tables to Snowflake. It
uses explicit projections rather than `SELECT *`, so migration-history column order cannot change
the manifest. Parquet files are loaded by case-insensitive column name, and the Snowflake worksheet
repeats cross-schema lineage, sanction, review, and event-date rule controls. Machine-specific local
cache paths are not exported. Full lap telemetry remains local until a real warehouse use case and
cost decision justify moving it.
