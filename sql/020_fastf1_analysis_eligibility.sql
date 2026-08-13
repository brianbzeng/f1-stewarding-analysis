CREATE OR REPLACE VIEW analysis.v_fastf1_driver_lap_coverage AS
SELECT
    r.event_id,
    r.session_type,
    r.driver_number,
    r.driver_name,
    coalesce(r.laps_completed, 0)::BIGINT AS classified_laps,
    count(l.lap_number) AS stored_timing_laps,
    count(l.lap_number) FILTER (
        WHERE l.lap_number <= coalesce(r.laps_completed, 0)
    ) AS stored_within_classified_distance,
    count(l.lap_number) FILTER (
        WHERE l.lap_number > coalesce(r.laps_completed, 0)
    ) AS stored_beyond_classified_distance,
    greatest(
        coalesce(r.laps_completed, 0)::BIGINT
        - count(l.lap_number) FILTER (
            WHERE l.lap_number <= coalesce(r.laps_completed, 0)
        ),
        0
    ) AS missing_within_classified_distance,
    count(l.lap_number) FILTER (
        WHERE l.lap_start_timestamp IS NULL
          AND l.lap_start_time_seconds IS NULL
    ) AS timing_rows_without_start,
    count(l.lap_number) FILTER (
        WHERE l.is_accurate IS DISTINCT FROM TRUE
    ) AS timing_rows_not_marked_accurate,
    count(l.lap_number) FILTER (
        WHERE l.lap_normalization_basis = 'fastf1_raw_timing_fallback'
    ) AS fallback_timing_rows
FROM raw.fastf1_session_results AS r
LEFT JOIN raw.fastf1_session_laps AS l
  ON l.event_id = r.event_id
 AND l.session_type = r.session_type
 AND l.driver_number = r.driver_number
GROUP BY
    r.event_id,
    r.session_type,
    r.driver_number,
    r.driver_name,
    r.laps_completed;

CREATE OR REPLACE VIEW analysis.v_fastf1_lap_eligibility AS
SELECT
    l.*,
    coalesce(r.laps_completed, 0)::BIGINT AS classified_laps,
    l.lap_number <= coalesce(r.laps_completed, 0) AS is_within_classified_distance,
    l.lap_number > coalesce(r.laps_completed, 0) AS is_beyond_classified_distance,
    (
        l.lap_start_timestamp IS NOT NULL
        OR l.lap_start_time_seconds IS NOT NULL
    ) AS is_incident_timing_eligible,
    l.lap_normalization_basis = 'fastf1_session_laps' AS has_model_supported_normalizer,
    l.is_accurate IS TRUE AS has_accurate_timing,
    l.track_status = '1' AS has_green_track_status,
    (
        l.pit_in_time_seconds IS NULL
        AND l.pit_out_time_seconds IS NULL
    ) AS is_uninterrupted_lap,
    (
        l.compound IS NOT NULL
        AND l.stint IS NOT NULL
        AND l.tyre_life IS NOT NULL
    ) AS has_tyre_context,
    (
        l.lap_normalization_basis = 'fastf1_session_laps'
        AND l.is_accurate IS TRUE
        AND l.lap_number <= coalesce(r.laps_completed, 0)
        AND l.lap_time_seconds IS NOT NULL
        AND l.track_status = '1'
        AND l.pit_in_time_seconds IS NULL
        AND l.pit_out_time_seconds IS NULL
        AND l.compound IS NOT NULL
        AND l.stint IS NOT NULL
        AND l.tyre_life IS NOT NULL
    ) AS is_pace_model_eligible
FROM raw.fastf1_session_laps AS l
JOIN raw.fastf1_session_results AS r
  ON r.event_id = l.event_id
 AND r.session_type = l.session_type
 AND r.driver_number = l.driver_number;

CREATE OR REPLACE VIEW analysis.v_fastf1_session_data_quality AS
WITH driver_quality AS (
    SELECT
        event_id,
        session_type,
        count(*) AS classified_drivers,
        sum(classified_laps) AS classified_completed_laps,
        sum(stored_timing_laps) AS stored_timing_laps,
        sum(stored_within_classified_distance) AS stored_within_classified_distance,
        sum(stored_beyond_classified_distance) AS stored_beyond_classified_distance,
        sum(missing_within_classified_distance) AS missing_within_classified_distance,
        sum(timing_rows_without_start) AS timing_rows_without_start,
        sum(timing_rows_not_marked_accurate) AS timing_rows_not_marked_accurate,
        sum(fallback_timing_rows) AS fallback_timing_rows
    FROM analysis.v_fastf1_driver_lap_coverage
    GROUP BY event_id, session_type
),
lap_quality AS (
    SELECT
        event_id,
        session_type,
        count(*) FILTER (
            WHERE is_incident_timing_eligible
        ) AS incident_timing_eligible_rows,
        count(*) FILTER (
            WHERE is_pace_model_eligible
        ) AS pace_model_eligible_rows
    FROM analysis.v_fastf1_lap_eligibility
    GROUP BY event_id, session_type
)
SELECT
    driver_quality.*,
    coalesce(lap_quality.incident_timing_eligible_rows, 0) AS incident_timing_eligible_rows,
    coalesce(lap_quality.pace_model_eligible_rows, 0) AS pace_model_eligible_rows
FROM driver_quality
LEFT JOIN lap_quality USING (event_id, session_type);
