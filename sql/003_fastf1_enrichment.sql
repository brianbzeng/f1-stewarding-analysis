CREATE TABLE IF NOT EXISTS raw.fastf1_results (
    event_id VARCHAR NOT NULL,
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
    PRIMARY KEY (event_id, driver_number)
);

CREATE TABLE IF NOT EXISTS raw.fastf1_laps (
    event_id VARCHAR NOT NULL,
    driver_number INTEGER NOT NULL,
    lap_number DOUBLE NOT NULL,
    lap_time_seconds DOUBLE,
    lap_start_time_seconds DOUBLE,
    lap_start_timestamp TIMESTAMPTZ,
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
    PRIMARY KEY (event_id, driver_number, lap_number)
);

CREATE TABLE IF NOT EXISTS raw.fastf1_race_control_messages (
    event_id VARCHAR NOT NULL,
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

CREATE VIEW IF NOT EXISTS analysis.v_pilot_results AS
SELECT
    e.season,
    e.event_name,
    r.driver_number,
    r.driver_name,
    r.country_code,
    r.team_name,
    r.grid_position,
    r.finish_position,
    r.status,
    r.points
FROM raw.fastf1_results AS r
JOIN metadata.events AS e USING (event_id)
WHERE e.is_pilot;
