# Full-Study FastF1 Collection

Status: complete local enrichment; strict 197-session inventory and all warehouse controls pass.

## Purpose and authority

FastF1 supplies normalized lap timing, classifications, tyre/stint fields, pit timestamps, track
status, and Race Control messages needed to locate incidents and measure observed consequences. It
does not replace official FIA decisions or classifications. FIA evidence remains the authority for
the allegation, finding, sanction, and report citation; FastF1 is an enrichment and measurement
source whose uncertainty and missingness are reported.

## Session population

The frozen 2018-2025 event catalog implies 197 timing sessions:

- 173 Races; and
- 24 Sprints at events marked `has_sprint` in the frozen catalog.

Race and Sprint use separate composite keys. The original pilot tables keyed only by event and could
not safely store both sessions for the same driver. Migration `019_fastf1_session_enrichment.sql`
adds session-keyed results, laps, Race Control messages, and a resumable ingestion ledger while
backfilling the three validated pilot Races.

## Commands

```powershell
# Resume every missing Race and Sprint
f1stewards study-fastf1

# Bounded or targeted collection
f1stewards study-fastf1 --max-sessions 5
f1stewards study-fastf1 --event-id 2021-gbr --session-type Sprint

# Inspect coverage; strict mode fails until all 197 sessions are loaded
f1stewards study-fastf1-inventory
f1stewards study-fastf1-inventory --strict
```

Each session is fetched, normalized, written to ignored Parquet, and transactionally replaced in
DuckDB. The ledger records `running`, `succeeded`, or `failed`, FastF1 version, timestamps, row
counts, timestamp-lineage counts, and any bounded error. Successful sessions are skipped on rerun
unless `--force` is explicit. A failed bulk run continues by default and exits nonzero after
recording every attempted failure.

## Completed population audit

The completed local warehouse contains:

- 197 of 197 expected sessions, comprising 173 Races and 24 Sprints;
- 3,938 classifications;
- 198,620 driver-lap timing rows;
- 16,039 Race Control messages;
- 198,620 incident-timing-eligible rows; and
- 162,383 rows that satisfy the conservative pace-model eligibility contract.

Every ingestion-ledger record is `succeeded`; no successful session has zero Race Control
messages. `study-fastf1-inventory --strict` passes, as do all 35 queries in
`sql/quality_checks.sql`. The 656 rows beyond official classified distance are intentionally
retained as possible retirement or incident evidence and excluded from pace modeling.

## Absolute lap-time lineage

Incident PDFs commonly report local clock time rather than a lap. The pipeline therefore preserves
how each absolute `lap_start_timestamp` was obtained:

- `fastf1_lap_start_date`: directly populated by FastF1 after timing/car data establish the session
  time origin;
- `session_t0_plus_lap_start_time`: derived from FastF1's UTC `t0_date` timing origin and relative
  lap-start time when the absolute field is unavailable; or
- `unavailable`: neither route supports a timestamp.

The derived route is explicit, tested, and never overwrites a direct timestamp. The ingestion ledger
stores counts for all three bases. A session can be downloaded successfully while still having
missing analytical fields; coverage and timestamp completeness are separate controls.

The first bounded full-study load, the 2018 Australian Race, initially demonstrated that historical
position telemetry can be unavailable. After the cached car stream established FastF1's time
origin, a forced normalized reload produced 940 direct absolute lap starts from 940 stored laps.
The logged position-stream warning remains a source limitation; normalized lap position was present
for 939 of the 940 rows.

The 2018 Italian Race exposed a different FastF1 edge case: malformed historical tyre-stint data
prevented the library from constructing its processed `Laps` object even though its raw extended
timing stream was complete. A narrowly scoped fallback accepts raw timing only when its row count
equals the sum of official classified completed laps and driver-lap keys are unique. It preserves
basic timing, pit, position, and track-status fields, labels all rows
`fastf1_raw_timing_fallback`, and forces `is_accurate = false` with compound and tyre fields null.
This retains the 925 timing observations for incident reconstruction while excluding them from
persistent-pace models until a separate parity study supports broader use.

The completed population has three bounded timing limitations:

- the 2018 Bahrain Race is missing one within-classified-distance timing row for Kimi Räikkönen;
- the 2020 Austrian Race is missing 79 within-classified-distance rows across 20 drivers because
  both FastF1's processed and underlying raw timing streams end before the official classified lap
  totals; and
- all 958 stored laps from the 2022 French Race retain relative session timing but lack an absolute
  UTC timestamp because FastF1 could not load position telemetry and could not establish
  `t0_date`.

No values are imputed for these gaps. They remain queryable in
`analysis.v_fastf1_driver_lap_coverage` and `analysis.v_fastf1_session_data_quality`. The other
196 sessions have complete absolute lap-start timestamps. Timestamp lineage totals are 195,739
direct FastF1 timestamps, 1,923 explicit `t0_date` derivations, and 958 unavailable absolute
timestamps.

Raw timing coverage and model eligibility are intentionally separate. The warehouse retains timed
retirement or incident laps beyond a driver's official completed-lap count because those rows can
document the event that ended the race. `analysis.v_fastf1_lap_eligibility` marks those rows as
incident-timing evidence but excludes them from pace modeling. Its strict pace flag additionally
requires processed FastF1 normalization, an accurate timed lap within the classified distance,
green-flag track status, no pit entry or exit, and complete tyre context. Driver- and session-level
coverage views expose timing beyond the official classification and missing within-distance rows;
they never impute either condition.

## Quality controls

The SQL suite now rejects:

- session rows that do not resolve to the frozen event catalog;
- Sprint rows at events not marked as Sprint events;
- lap rows without a same-session classification record;
- invalid timestamp basis, nullability, or derived-flag combinations; and
- unrecognized normalization lineage or fallback rows presented as clean tyre/pace observations;
  and
- successful ledger counts or normalization bases that disagree with stored results, laps,
  messages, or timestamp lineage.

Completeness is enforced separately by `study-fastf1-inventory --strict`. This prevents a clean
partial load from being mistaken for the completed 197-session enrichment population.

FastF1's high-frequency telemetry cache is reproducible scratch data, not a project deliverable.
It grew to 12.19 GiB during collection and was safely removed after normalized session writes were
validated; a second 5.98 GiB cache was removed after final strict validation. The ignored normalized
Parquet files and DuckDB warehouse remain the local analytical source, and the cache will be
recreated automatically only when a session is explicitly re-fetched.
