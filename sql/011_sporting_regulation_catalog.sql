CREATE TABLE IF NOT EXISTS metadata.sporting_regulation_issues (
    source_id VARCHAR PRIMARY KEY,
    season INTEGER NOT NULL CHECK (season BETWEEN 2018 AND 2025),
    precedence INTEGER NOT NULL CHECK (precedence >= 1),
    publication_date DATE NOT NULL,
    issue_label VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    archive_url VARCHAR NOT NULL,
    document_url VARCHAR,
    resolution_status VARCHAR NOT NULL,
    selection_status VARCHAR NOT NULL,
    notes VARCHAR NOT NULL,
    UNIQUE (season, precedence)
);

CREATE OR REPLACE VIEW analysis.v_event_sporting_regulation_selection AS
SELECT
    e.event_id,
    e.season,
    e.event_name,
    e.event_date,
    r.source_id,
    r.precedence,
    r.publication_date,
    r.issue_label,
    r.title,
    r.archive_url,
    r.document_url,
    r.resolution_status,
    r.selection_status,
    r.notes,
    date_diff('day', r.publication_date, e.event_date) AS days_before_event
FROM metadata.events AS e
JOIN metadata.sporting_regulation_issues AS r
  ON e.season = r.season
 AND r.publication_date <= e.event_date
QUALIFY row_number() OVER (
    PARTITION BY e.event_id
    ORDER BY r.publication_date DESC, r.precedence DESC
) = 1;
