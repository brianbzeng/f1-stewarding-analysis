CREATE TABLE IF NOT EXISTS raw.fastf1_session_results (
    event_id VARCHAR NOT NULL,
    session_type VARCHAR NOT NULL CHECK (session_type IN ('Race', 'Sprint')),
    driver_number INTEGER NOT NULL,
    driver_name VARCHAR,
    abbreviation VARCHAR,
    country_code VARCHAR,
    team_name VARCHAR,
    grid_position DOUBLE,
    finish_position DOUBLE,
    classified_position VARCHAR,
    laps_completed DOUBLE,
    result_time_seconds DOUBLE,
    classification_gap_seconds DOUBLE,
    status VARCHAR,
    points DOUBLE,
    retrieved_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (event_id, session_type, driver_number)
);

CREATE TABLE IF NOT EXISTS raw.fastf1_session_laps (
    event_id VARCHAR NOT NULL,
    session_type VARCHAR NOT NULL CHECK (session_type IN ('Race', 'Sprint')),
    driver_number INTEGER NOT NULL,
    lap_number DOUBLE NOT NULL,
    lap_time_seconds DOUBLE,
    lap_start_time_seconds DOUBLE,
    lap_start_timestamp TIMESTAMPTZ,
    lap_start_timestamp_basis VARCHAR,
    lap_start_timestamp_is_derived BOOLEAN,
    pit_in_time_seconds DOUBLE,
    pit_out_time_seconds DOUBLE,
    position DOUBLE,
    compound VARCHAR,
    stint DOUBLE,
    tyre_life DOUBLE,
    fresh_tyre BOOLEAN,
    track_status VARCHAR,
    is_accurate BOOLEAN,
    retrieved_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (event_id, session_type, driver_number, lap_number)
);

CREATE TABLE IF NOT EXISTS raw.fastf1_session_race_control_messages (
    event_id VARCHAR NOT NULL,
    session_type VARCHAR NOT NULL CHECK (session_type IN ('Race', 'Sprint')),
    message_timestamp TIMESTAMPTZ,
    message_time_seconds DOUBLE,
    category VARCHAR,
    message VARCHAR,
    status VARCHAR,
    flag VARCHAR,
    scope VARCHAR,
    sector DOUBLE,
    racing_number DOUBLE,
    lap_number DOUBLE,
    retrieved_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata.fastf1_session_ingestion (
    event_id VARCHAR NOT NULL,
    session_type VARCHAR NOT NULL CHECK (session_type IN ('Race', 'Sprint')),
    status VARCHAR NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    fastf1_version VARCHAR NOT NULL,
    result_rows INTEGER,
    lap_rows INTEGER,
    message_rows INTEGER,
    direct_lap_timestamp_rows INTEGER,
    derived_lap_timestamp_rows INTEGER,
    missing_lap_timestamp_rows INTEGER,
    error_message VARCHAR,
    PRIMARY KEY (event_id, session_type)
);

ALTER TABLE raw.fastf1_session_laps
    ADD COLUMN IF NOT EXISTS lap_start_timestamp_basis VARCHAR;

ALTER TABLE raw.fastf1_session_laps
    ADD COLUMN IF NOT EXISTS lap_start_timestamp_is_derived BOOLEAN;

UPDATE raw.fastf1_session_laps
SET lap_start_timestamp_basis = CASE
        WHEN lap_start_timestamp IS NOT NULL THEN 'fastf1_lap_start_date'
        ELSE 'unavailable'
    END
WHERE lap_start_timestamp_basis IS NULL;

UPDATE raw.fastf1_session_laps
SET lap_start_timestamp_is_derived = FALSE
WHERE lap_start_timestamp_is_derived IS NULL;

ALTER TABLE metadata.fastf1_session_ingestion
    ADD COLUMN IF NOT EXISTS direct_lap_timestamp_rows INTEGER;

ALTER TABLE metadata.fastf1_session_ingestion
    ADD COLUMN IF NOT EXISTS derived_lap_timestamp_rows INTEGER;

ALTER TABLE metadata.fastf1_session_ingestion
    ADD COLUMN IF NOT EXISTS missing_lap_timestamp_rows INTEGER;

INSERT INTO raw.fastf1_session_results
SELECT event_id, 'Race', driver_number, driver_name, abbreviation, country_code, team_name,
       grid_position, finish_position, classified_position, laps_completed,
       result_time_seconds, classification_gap_seconds, status, points, retrieved_at
FROM raw.fastf1_results AS legacy
WHERE NOT EXISTS (
    SELECT 1
    FROM raw.fastf1_session_results AS current
    WHERE current.event_id = legacy.event_id
      AND current.session_type = 'Race'
);

INSERT INTO raw.fastf1_session_laps (
    event_id, session_type, driver_number, lap_number, lap_time_seconds,
    lap_start_time_seconds, lap_start_timestamp, lap_start_timestamp_basis,
    lap_start_timestamp_is_derived, pit_in_time_seconds, pit_out_time_seconds,
    position, compound, stint, tyre_life, fresh_tyre, track_status, is_accurate,
    retrieved_at
)
SELECT event_id, 'Race', driver_number, lap_number, lap_time_seconds, lap_start_time_seconds,
       lap_start_timestamp,
       CASE WHEN lap_start_timestamp IS NOT NULL THEN 'fastf1_lap_start_date'
            ELSE 'unavailable' END,
       FALSE,
       pit_in_time_seconds, pit_out_time_seconds, position, compound, stint, tyre_life,
       fresh_tyre, track_status, is_accurate, retrieved_at
FROM raw.fastf1_laps AS legacy
WHERE NOT EXISTS (
    SELECT 1
    FROM raw.fastf1_session_laps AS current
    WHERE current.event_id = legacy.event_id
      AND current.session_type = 'Race'
);

INSERT INTO raw.fastf1_session_race_control_messages
SELECT event_id, 'Race', message_timestamp, message_time_seconds, category, message, status,
       flag, scope, sector, racing_number, lap_number, retrieved_at
FROM raw.fastf1_race_control_messages AS legacy
WHERE NOT EXISTS (
    SELECT 1
    FROM raw.fastf1_session_race_control_messages AS current
    WHERE current.event_id = legacy.event_id
      AND current.session_type = 'Race'
);

INSERT INTO metadata.fastf1_session_ingestion (
    event_id, session_type, status, started_at, finished_at, fastf1_version,
    result_rows, lap_rows, message_rows, direct_lap_timestamp_rows,
    derived_lap_timestamp_rows, missing_lap_timestamp_rows, error_message
)
WITH results AS (
    SELECT event_id, session_type, count(*) AS result_rows,
           min(retrieved_at) AS first_retrieved_at,
           max(retrieved_at) AS last_retrieved_at
    FROM raw.fastf1_session_results
    GROUP BY event_id, session_type
),
laps AS (
    SELECT event_id, session_type, count(*) AS lap_rows,
           count(*) FILTER (
               WHERE lap_start_timestamp_basis = 'fastf1_lap_start_date'
           ) AS direct_rows,
           count(*) FILTER (
               WHERE lap_start_timestamp_basis = 'session_date_plus_lap_start_time'
           ) AS derived_rows,
           count(*) FILTER (
               WHERE lap_start_timestamp_basis = 'unavailable'
           ) AS missing_rows
    FROM raw.fastf1_session_laps
    GROUP BY event_id, session_type
),
messages AS (
    SELECT event_id, session_type, count(*) AS message_rows
    FROM raw.fastf1_session_race_control_messages
    GROUP BY event_id, session_type
)
SELECT
    r.event_id,
    r.session_type,
    'succeeded',
    r.first_retrieved_at,
    r.last_retrieved_at,
    'legacy_pilot_backfill',
    r.result_rows,
    coalesce(l.lap_rows, 0),
    coalesce(m.message_rows, 0),
    coalesce(l.direct_rows, 0),
    coalesce(l.derived_rows, 0),
    coalesce(l.missing_rows, 0),
    NULL
FROM results AS r
LEFT JOIN laps AS l USING (event_id, session_type)
LEFT JOIN messages AS m USING (event_id, session_type)
ON CONFLICT (event_id, session_type) DO NOTHING;

CREATE OR REPLACE VIEW analysis.v_fastf1_session_coverage AS
SELECT
    e.season,
    e.round_number,
    e.event_id,
    e.event_name,
    r.session_type,
    count(DISTINCT r.driver_number) AS classified_drivers,
    count(DISTINCT (l.driver_number, l.lap_number)) AS driver_laps,
    count(DISTINCT m.message_timestamp) AS timestamped_messages
FROM metadata.events AS e
JOIN raw.fastf1_session_results AS r USING (event_id)
LEFT JOIN raw.fastf1_session_laps AS l
  ON l.event_id = r.event_id
 AND l.session_type = r.session_type
LEFT JOIN raw.fastf1_session_race_control_messages AS m
  ON m.event_id = r.event_id
 AND m.session_type = r.session_type
GROUP BY e.season, e.round_number, e.event_id, e.event_name, r.session_type;
