ALTER TABLE raw.fastf1_laps ADD COLUMN IF NOT EXISTS lap_start_timestamp TIMESTAMPTZ;
ALTER TABLE raw.fastf1_race_control_messages
    ADD COLUMN IF NOT EXISTS message_timestamp TIMESTAMPTZ;
