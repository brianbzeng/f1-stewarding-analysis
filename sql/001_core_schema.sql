CREATE SCHEMA IF NOT EXISTS metadata;
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS curated;
CREATE SCHEMA IF NOT EXISTS analysis;

CREATE TABLE IF NOT EXISTS metadata.pipeline_runs (
    run_id VARCHAR PRIMARY KEY,
    command VARCHAR NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    git_commit VARCHAR,
    status VARCHAR NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    error_message VARCHAR
);

CREATE TABLE IF NOT EXISTS metadata.events (
    event_id VARCHAR PRIMARY KEY,
    season INTEGER NOT NULL CHECK (season BETWEEN 2018 AND 2025),
    round_number INTEGER,
    event_name VARCHAR NOT NULL,
    country VARCHAR,
    event_date DATE,
    archive_url VARCHAR NOT NULL,
    guideline_regime VARCHAR NOT NULL,
    is_pilot BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (season, event_name)
);

CREATE TABLE IF NOT EXISTS raw.source_documents (
    document_id VARCHAR PRIMARY KEY,
    event_id VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    document_url VARCHAR NOT NULL,
    archive_url VARCHAR NOT NULL,
    document_class VARCHAR NOT NULL,
    published_at_raw VARCHAR,
    published_at TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ NOT NULL,
    retrieved_at TIMESTAMPTZ,
    source_domain VARCHAR NOT NULL,
    content_sha256 VARCHAR,
    local_path VARCHAR,
    http_status INTEGER,
    content_type VARCHAR,
    retrieval_error VARCHAR,
    is_recalled BOOLEAN NOT NULL DEFAULT FALSE,
    supersedes_document_id VARCHAR,
    UNIQUE (document_url)
);

CREATE TABLE IF NOT EXISTS raw.document_text (
    document_id VARCHAR PRIMARY KEY REFERENCES raw.source_documents(document_id),
    parser_version VARCHAR NOT NULL,
    parsed_at TIMESTAMPTZ NOT NULL,
    page_count INTEGER NOT NULL,
    raw_text VARCHAR NOT NULL,
    driver_number INTEGER,
    driver_name VARCHAR,
    session_type VARCHAR,
    incident_time_raw VARCHAR,
    fact_text VARCHAR,
    infringement_text VARCHAR,
    decision_text VARCHAR,
    reason_text VARCHAR,
    parser_warnings_json JSON
);

CREATE TABLE IF NOT EXISTS curated.drivers (
    driver_id VARCHAR PRIMARY KEY,
    permanent_number INTEGER,
    full_name VARCHAR NOT NULL,
    nationality VARCHAR,
    nationality_source_url VARCHAR,
    valid_from DATE,
    valid_to DATE
);

CREATE TABLE IF NOT EXISTS curated.stewards (
    steward_id VARCHAR PRIMARY KEY,
    full_name VARCHAR NOT NULL,
    nationality VARCHAR,
    nationality_source_url VARCHAR
);

CREATE TABLE IF NOT EXISTS curated.panels (
    panel_id VARCHAR PRIMARY KEY,
    event_id VARCHAR NOT NULL,
    chair_steward_id VARCHAR,
    driver_steward_id VARCHAR,
    panel_size INTEGER,
    panel_source_document_id VARCHAR
);

CREATE TABLE IF NOT EXISTS curated.panel_members (
    panel_id VARCHAR NOT NULL REFERENCES curated.panels(panel_id),
    steward_id VARCHAR NOT NULL REFERENCES curated.stewards(steward_id),
    role VARCHAR,
    PRIMARY KEY (panel_id, steward_id)
);

CREATE TABLE IF NOT EXISTS curated.incidents (
    incident_id VARCHAR PRIMARY KEY,
    event_id VARCHAR NOT NULL,
    session_type VARCHAR NOT NULL CHECK (session_type IN ('Race', 'Sprint', 'Qualifying')),
    lap_number INTEGER,
    turn_number VARCHAR,
    incident_family VARCHAR NOT NULL,
    incident_description VARCHAR,
    referral_observed BOOLEAN NOT NULL DEFAULT TRUE,
    source_document_id VARCHAR NOT NULL,
    coding_status VARCHAR NOT NULL CHECK (coding_status IN ('unreviewed', 'single_coded', 'double_coded', 'adjudicated')),
    analyst_notes VARCHAR
);

CREATE TABLE IF NOT EXISTS curated.adjudications (
    adjudication_id VARCHAR PRIMARY KEY,
    incident_id VARCHAR NOT NULL REFERENCES curated.incidents(incident_id),
    accused_driver_id VARCHAR NOT NULL REFERENCES curated.drivers(driver_id),
    affected_driver_id VARCHAR REFERENCES curated.drivers(driver_id),
    panel_id VARCHAR REFERENCES curated.panels(panel_id),
    decision_document_id VARCHAR NOT NULL,
    outcome_family VARCHAR NOT NULL CHECK (
        outcome_family IN ('no_further_action', 'warning', 'reprimand', 'black_white_flag',
                           'fine', 'time_penalty',
                           'drive_through', 'stop_go', 'grid_penalty', 'disqualification', 'other')
    ),
    penalty_seconds DOUBLE,
    penalty_points INTEGER,
    grid_places INTEGER,
    responsibility_share VARCHAR,
    evidence_video BOOLEAN,
    evidence_telemetry BOOLEAN,
    evidence_team_radio BOOLEAN,
    guideline_clause VARCHAR,
    guideline_expected_outcome VARCHAR,
    conformance_status VARCHAR CHECK (
        conformance_status IN ('conformant', 'aggravated', 'mitigated', 'departed', 'not_applicable', 'unclear')
    ),
    outcome_coder_id VARCHAR,
    context_coder_id VARCHAR,
    review_status VARCHAR NOT NULL CHECK (review_status IN ('unreviewed', 'reviewed', 'adjudicated')),
    notes VARCHAR,
    UNIQUE (incident_id, accused_driver_id, decision_document_id)
);

CREATE TABLE IF NOT EXISTS curated.incident_context (
    adjudication_id VARCHAR PRIMARY KEY REFERENCES curated.adjudications(adjudication_id),
    corner_phase VARCHAR,
    attacker_defender_role VARCHAR,
    relative_position VARCHAR,
    corner_control VARCHAR,
    contact_observed BOOLEAN,
    damage_observed BOOLEAN,
    position_change_observed BOOLEAN,
    safety_car_context BOOLEAN,
    wet_conditions BOOLEAN,
    first_lap BOOLEAN,
    observable_severity VARCHAR,
    factual_support_tier VARCHAR NOT NULL CHECK (factual_support_tier IN ('official_only', 'official_plus_timing', 'manual_video_review'))
);

CREATE TABLE IF NOT EXISTS curated.classification_impact (
    adjudication_id VARCHAR PRIMARY KEY REFERENCES curated.adjudications(adjudication_id),
    impact_level VARCHAR NOT NULL CHECK (impact_level IN ('mechanical', 'bounded', 'modeled', 'not_estimable')),
    official_finish_position INTEGER,
    mechanical_finish_position INTEGER,
    official_points DOUBLE,
    mechanical_points DOUBLE,
    positions_changed INTEGER,
    points_changed DOUBLE,
    podium_changed BOOLEAN,
    win_changed BOOLEAN,
    assumptions VARCHAR,
    uncertainty_low DOUBLE,
    uncertainty_high DOUBLE
);

CREATE VIEW IF NOT EXISTS analysis.v_primary_adjudications AS
SELECT
    a.*,
    i.event_id,
    i.session_type,
    i.lap_number,
    i.turn_number,
    i.incident_family,
    i.coding_status,
    e.season,
    e.event_name,
    e.guideline_regime
FROM curated.adjudications AS a
JOIN curated.incidents AS i USING (incident_id)
JOIN metadata.events AS e USING (event_id)
WHERE i.session_type IN ('Race', 'Sprint')
  AND i.incident_family IN (
      'causing_collision',
      'forcing_off_track',
      'gaining_advantage_off_track',
      'unsafe_rejoin',
      'moving_under_braking',
      'multiple_defensive_moves'
  );
