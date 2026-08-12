CREATE TABLE IF NOT EXISTS metadata.regulatory_sources (
    source_id VARCHAR PRIMARY KEY,
    document_type VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    issuing_body VARCHAR NOT NULL,
    publication_date DATE,
    effective_from DATE,
    effective_through DATE,
    source_url VARCHAR NOT NULL,
    resolved_url VARCHAR,
    source_status VARCHAR NOT NULL,
    applicability_status VARCHAR NOT NULL,
    is_guideline BOOLEAN NOT NULL,
    notes VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata.event_regulatory_sources (
    event_id VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL,
    event_role VARCHAR NOT NULL,
    PRIMARY KEY (event_id, source_id)
);
