# Full-Study FastF1 Collection

Status: resumable session-keyed pipeline implemented; full local enrichment in progress.

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

## Absolute lap-time lineage

Incident PDFs commonly report local clock time rather than a lap. The pipeline therefore preserves
how each absolute `lap_start_timestamp` was obtained:

- `fastf1_lap_start_date`: directly populated by FastF1 after timing/car data establish the session
  time origin;
- `session_date_plus_lap_start_time`: derived from FastF1's UTC session anchor and relative lap-start
  time when the absolute field is unavailable; or
- `unavailable`: neither route supports a timestamp.

The derived route is explicit, tested, and never overwrites a direct timestamp. The ingestion ledger
stores counts for all three bases. A session can be downloaded successfully while still having
missing analytical fields; coverage and timestamp completeness are separate controls.

The first bounded full-study load, the 2018 Australian Race, initially demonstrated that historical
position telemetry can be unavailable. After the cached car stream established FastF1's time
origin, a forced normalized reload produced 940 direct absolute lap starts from 940 stored laps.
The logged position-stream warning remains a source limitation; normalized lap position was present
for 939 of the 940 rows.

## Quality controls

The SQL suite now rejects:

- session rows that do not resolve to the frozen event catalog;
- Sprint rows at events not marked as Sprint events;
- lap rows without a same-session classification record;
- invalid timestamp basis, nullability, or derived-flag combinations; and
- successful ledger counts that disagree with stored results, laps, messages, or timestamp lineage.

Completeness is enforced separately by `study-fastf1-inventory --strict`. This prevents a clean
partial load from being mistaken for the completed 197-session enrichment population.
