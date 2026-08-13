ALTER TABLE raw.source_documents
    ADD COLUMN IF NOT EXISTS source_availability_status VARCHAR DEFAULT 'advertised';

ALTER TABLE raw.source_documents
    ADD COLUMN IF NOT EXISTS source_availability_note VARCHAR;
