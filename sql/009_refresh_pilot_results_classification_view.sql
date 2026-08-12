CREATE OR REPLACE VIEW analysis.v_pilot_results AS
SELECT
    e.season,
    e.event_name,
    r.driver_number,
    r.driver_name,
    r.country_code,
    r.team_name,
    r.grid_position,
    r.finish_position,
    r.laps_completed,
    r.result_time_seconds,
    r.classification_gap_seconds,
    r.status,
    r.points
FROM raw.fastf1_results AS r
JOIN metadata.events AS e USING (event_id)
WHERE e.is_pilot;
