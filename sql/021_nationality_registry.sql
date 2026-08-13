CREATE TABLE IF NOT EXISTS metadata.driver_nationality_registry (
    driver_id VARCHAR PRIMARY KEY,
    abbreviation VARCHAR NOT NULL UNIQUE,
    permanent_number INTEGER,
    full_name VARCHAR NOT NULL,
    f1_country_code VARCHAR NOT NULL,
    nationality VARCHAR NOT NULL,
    is_british BOOLEAN NOT NULL,
    source_type VARCHAR NOT NULL,
    source_url VARCHAR NOT NULL,
    source_note VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata.event_country_crosswalk (
    event_country_label VARCHAR PRIMARY KEY,
    f1_country_code VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL,
    source_url VARCHAR NOT NULL,
    source_note VARCHAR NOT NULL
);

CREATE OR REPLACE VIEW analysis.v_event_country_identity AS
SELECT
    e.event_id,
    e.season,
    e.round_number,
    e.event_name,
    e.country AS event_country_label,
    x.f1_country_code AS event_f1_country_code,
    x.source_type AS event_country_source_type,
    x.source_url AS event_country_source_url,
    CASE
        WHEN x.event_country_label IS NULL THEN 'missing_crosswalk'
        ELSE 'matched'
    END AS event_country_match_status
FROM metadata.events AS e
LEFT JOIN metadata.event_country_crosswalk AS x
  ON x.event_country_label = e.country;

CREATE OR REPLACE VIEW analysis.v_fastf1_driver_identity AS
WITH normalized AS (
    SELECT
        r.*,
        nullif(nullif(trim(r.country_code), ''), 'nan') AS observed_f1_country_code
    FROM raw.fastf1_session_results AS r
)
SELECT
    r.event_id,
    r.session_type,
    e.season,
    e.round_number,
    r.driver_number,
    r.driver_name AS observed_driver_name,
    r.abbreviation,
    r.team_name,
    r.observed_f1_country_code,
    d.driver_id,
    d.full_name AS registry_driver_name,
    d.permanent_number,
    d.f1_country_code AS registry_f1_country_code,
    d.nationality,
    d.is_british,
    d.source_type AS nationality_source_type,
    d.source_url AS nationality_source_url,
    ec.event_country_label,
    ec.event_f1_country_code,
    CASE
        WHEN d.driver_id IS NULL THEN NULL
        WHEN ec.event_f1_country_code IS NULL THEN NULL
        ELSE d.f1_country_code = ec.event_f1_country_code
    END AS home_race_driver,
    CASE
        WHEN d.driver_id IS NULL THEN 'missing_registry'
        WHEN r.observed_f1_country_code IS NULL THEN 'registry_backfill'
        WHEN r.observed_f1_country_code = d.f1_country_code THEN 'observed_match'
        ELSE 'observed_conflict'
    END AS nationality_match_status
FROM normalized AS r
JOIN metadata.events AS e USING (event_id)
LEFT JOIN metadata.driver_nationality_registry AS d
  ON d.abbreviation = r.abbreviation
LEFT JOIN analysis.v_event_country_identity AS ec USING (event_id);

CREATE OR REPLACE VIEW analysis.v_driver_season_nationality AS
SELECT
    season,
    driver_id,
    registry_driver_name AS driver_name,
    abbreviation,
    registry_f1_country_code AS f1_country_code,
    nationality,
    is_british,
    nationality_source_type,
    nationality_source_url,
    count(*) AS classification_rows,
    count(*) FILTER (
        WHERE nationality_match_status = 'observed_match'
    ) AS observed_match_rows,
    count(*) FILTER (
        WHERE nationality_match_status = 'registry_backfill'
    ) AS registry_backfill_rows,
    count(*) FILTER (
        WHERE nationality_match_status = 'observed_conflict'
    ) AS observed_conflict_rows,
    bool_or(home_race_driver) AS has_home_race_classification
FROM analysis.v_fastf1_driver_identity
GROUP BY
    season,
    driver_id,
    registry_driver_name,
    abbreviation,
    registry_f1_country_code,
    nationality,
    is_british,
    nationality_source_type,
    nationality_source_url;
