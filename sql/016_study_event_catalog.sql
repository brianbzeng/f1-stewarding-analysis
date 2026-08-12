ALTER TABLE metadata.events ADD COLUMN IF NOT EXISTS event_timezone VARCHAR;
ALTER TABLE metadata.events ADD COLUMN IF NOT EXISTS archive_system VARCHAR;
ALTER TABLE metadata.events ADD COLUMN IF NOT EXISTS event_format VARCHAR;
ALTER TABLE metadata.events ADD COLUMN IF NOT EXISTS has_sprint BOOLEAN DEFAULT FALSE;
ALTER TABLE metadata.events ADD COLUMN IF NOT EXISTS catalog_source_url VARCHAR;
