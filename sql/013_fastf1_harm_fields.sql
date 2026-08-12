ALTER TABLE raw.fastf1_laps ADD COLUMN IF NOT EXISTS pit_in_time_seconds DOUBLE;
ALTER TABLE raw.fastf1_laps ADD COLUMN IF NOT EXISTS pit_out_time_seconds DOUBLE;
ALTER TABLE raw.fastf1_laps ADD COLUMN IF NOT EXISTS tyre_life DOUBLE;
ALTER TABLE raw.fastf1_laps ADD COLUMN IF NOT EXISTS fresh_tyre BOOLEAN;
