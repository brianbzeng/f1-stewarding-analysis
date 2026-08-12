ALTER TABLE curated.harm_assessments
    ADD COLUMN IF NOT EXISTS position_window_start_lap INTEGER;
ALTER TABLE curated.harm_assessments
    ADD COLUMN IF NOT EXISTS position_window_end_lap INTEGER;
ALTER TABLE curated.harm_assessments
    ADD COLUMN IF NOT EXISTS relative_time_comparator_driver_number INTEGER;
ALTER TABLE curated.harm_assessments
    ADD COLUMN IF NOT EXISTS relative_time_window_start_lap INTEGER;
ALTER TABLE curated.harm_assessments
    ADD COLUMN IF NOT EXISTS relative_time_window_end_lap INTEGER;

CREATE TABLE IF NOT EXISTS curated.incident_locations (
    location_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    event_id VARCHAR NOT NULL,
    source_document_id VARCHAR NOT NULL,
    session_type VARCHAR NOT NULL CHECK (session_type IN ('Race', 'Sprint')),
    lap_number INTEGER NOT NULL,
    location_type VARCHAR NOT NULL CHECK (
        location_type IN ('single_turn', 'turn_range', 'straight', 'pit_lane', 'other', 'unknown')
    ),
    turn_start_number INTEGER,
    turn_end_number INTEGER,
    location_text VARCHAR NOT NULL,
    evidence_urls VARCHAR NOT NULL,
    coding_notes VARCHAR NOT NULL,
    coder_id VARCHAR NOT NULL,
    review_status VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS curated.incident_relations (
    relation_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL,
    event_id VARCHAR NOT NULL,
    source_document_id VARCHAR NOT NULL,
    sequence INTEGER NOT NULL,
    source_driver_number INTEGER NOT NULL,
    target_driver_number INTEGER NOT NULL,
    relation_type VARCHAR NOT NULL,
    relation_scope VARCHAR NOT NULL,
    fault_attributed BOOLEAN NOT NULL,
    evidence_level VARCHAR NOT NULL,
    evidence_urls VARCHAR NOT NULL,
    coding_notes VARCHAR NOT NULL,
    coder_id VARCHAR NOT NULL,
    review_status VARCHAR NOT NULL,
    UNIQUE (incident_id, sequence)
);

CREATE TABLE IF NOT EXISTS curated.cross_event_sanction_effects (
    cross_event_effect_id VARCHAR PRIMARY KEY,
    adjudication_id VARCHAR NOT NULL REFERENCES curated.adjudications(adjudication_id),
    origin_event_id VARCHAR NOT NULL,
    application_event_id VARCHAR NOT NULL,
    source_document_id VARCHAR NOT NULL,
    driver_number INTEGER NOT NULL,
    sanction_type VARCHAR NOT NULL CHECK (sanction_type = 'grid_penalty'),
    nominal_grid_places INTEGER NOT NULL,
    qualifying_position INTEGER NOT NULL,
    starting_grid_position INTEGER NOT NULL,
    realized_grid_places_lost INTEGER NOT NULL,
    grid_effect_level VARCHAR NOT NULL,
    official_finish_position INTEGER,
    race_status VARCHAR NOT NULL,
    official_points DOUBLE NOT NULL,
    finish_effect_level VARCHAR NOT NULL,
    counterfactual_finish_position INTEGER,
    counterfactual_points DOUBLE,
    application_grid_url VARCHAR NOT NULL,
    application_classification_url VARCHAR NOT NULL,
    evidence_urls VARCHAR NOT NULL,
    calculation_method VARCHAR NOT NULL,
    assumptions VARCHAR NOT NULL,
    review_status VARCHAR NOT NULL
);

CREATE VIEW IF NOT EXISTS analysis.v_incident_relation_chains AS
SELECT
    incident_id,
    event_id,
    count(*) AS relation_count,
    list_unique(
        list_concat(list(source_driver_number), list(target_driver_number))
    ) AS participant_count,
    bool_or(fault_attributed) AS has_fault_attributed_edge,
    string_agg(
        CAST(source_driver_number AS VARCHAR) || '->' || CAST(target_driver_number AS VARCHAR),
        ';' ORDER BY sequence
    ) AS ordered_driver_edges
FROM curated.incident_relations AS outer_relations
GROUP BY incident_id, event_id;
