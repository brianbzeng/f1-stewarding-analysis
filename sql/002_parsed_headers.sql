ALTER TABLE raw.document_text ADD COLUMN IF NOT EXISTS driver_number INTEGER;
ALTER TABLE raw.document_text ADD COLUMN IF NOT EXISTS driver_name VARCHAR;
ALTER TABLE raw.document_text ADD COLUMN IF NOT EXISTS session_type VARCHAR;
ALTER TABLE raw.document_text ADD COLUMN IF NOT EXISTS incident_time_raw VARCHAR;
