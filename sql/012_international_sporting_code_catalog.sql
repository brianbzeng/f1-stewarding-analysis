CREATE TABLE IF NOT EXISTS metadata.international_sporting_code_issues (
    source_id VARCHAR PRIMARY KEY,
    season INTEGER NOT NULL CHECK (season BETWEEN 2018 AND 2025),
    precedence INTEGER NOT NULL CHECK (precedence >= 1),
    publication_date DATE,
    effective_from DATE NOT NULL,
    effective_through DATE NOT NULL,
    title VARCHAR NOT NULL,
    archive_url VARCHAR NOT NULL,
    document_url VARCHAR,
    resolution_status VARCHAR NOT NULL,
    selection_status VARCHAR NOT NULL,
    notes VARCHAR NOT NULL,
    UNIQUE (season, precedence)
);

CREATE OR REPLACE VIEW analysis.v_event_international_sporting_code_selection AS
SELECT
    e.event_id,
    e.season,
    e.event_name,
    e.event_date,
    r.source_id,
    r.precedence,
    r.publication_date,
    r.effective_from,
    r.effective_through,
    r.title,
    r.archive_url,
    r.document_url,
    r.resolution_status,
    r.selection_status,
    r.notes
FROM metadata.events AS e
JOIN metadata.international_sporting_code_issues AS r
  ON e.season = r.season
 AND e.event_date BETWEEN r.effective_from AND r.effective_through
QUALIFY row_number() OVER (
    PARTITION BY e.event_id
    ORDER BY r.effective_from DESC, r.precedence DESC
) = 1;
