ALTER TABLE raw.fastf1_results ADD COLUMN IF NOT EXISTS laps_completed DOUBLE;
ALTER TABLE raw.fastf1_results ADD COLUMN IF NOT EXISTS classification_gap_seconds DOUBLE;

UPDATE raw.fastf1_results AS r
SET laps_completed = lap_counts.laps_completed
FROM (
    SELECT event_id, driver_number, max(lap_number) AS laps_completed
    FROM raw.fastf1_laps
    GROUP BY event_id, driver_number
) AS lap_counts
WHERE r.event_id = lap_counts.event_id
  AND r.driver_number = lap_counts.driver_number
  AND r.laps_completed IS NULL;

UPDATE raw.fastf1_results
SET classification_gap_seconds = CASE
    WHEN finish_position = 1 THEN 0
    ELSE result_time_seconds
END
WHERE classification_gap_seconds IS NULL
  AND result_time_seconds IS NOT NULL;
