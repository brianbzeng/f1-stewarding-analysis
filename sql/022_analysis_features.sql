CREATE TABLE IF NOT EXISTS metadata.analysis_feature_builds (
    feature_build_id VARCHAR PRIMARY KEY,
    schema_version VARCHAR NOT NULL,
    workspace_id VARCHAR NOT NULL,
    workspace_input_sha256 VARCHAR NOT NULL,
    nationality_registry_sha256 VARCHAR NOT NULL,
    built_at_utc TIMESTAMPTZ NOT NULL,
    release_status VARCHAR NOT NULL CHECK (
        release_status IN ('blocked_pending_human_review', 'reportable_human_reviewed')
    ),
    adjudication_rows INTEGER NOT NULL,
    driver_role_rows INTEGER NOT NULL,
    interpretation_boundary VARCHAR NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis.adjudication_features (
    feature_build_id VARCHAR NOT NULL,
    workspace_id VARCHAR NOT NULL,
    adjudication_instance_id VARCHAR NOT NULL,
    adjudication_seed_id VARCHAR NOT NULL,
    adjudication_id VARCHAR,
    incident_id VARCHAR,
    document_id VARCHAR NOT NULL,
    source_url VARCHAR NOT NULL,
    event_id VARCHAR NOT NULL,
    season INTEGER NOT NULL,
    round_number INTEGER,
    event_name VARCHAR NOT NULL,
    event_date DATE,
    guideline_regime VARCHAR NOT NULL,
    feature_label_status VARCHAR NOT NULL,
    population_status VARCHAR NOT NULL,
    review_status VARCHAR,
    reporting_eligible BOOLEAN NOT NULL,
    provisional_design_eligible BOOLEAN NOT NULL,
    model_eligible BOOLEAN NOT NULL,
    session_type VARCHAR,
    incident_family VARCHAR,
    outcome_family VARCHAR,
    sanction_outcome BOOLEAN,
    outcome_model_eligible BOOLEAN NOT NULL,
    penalty_seconds DOUBLE,
    penalty_points INTEGER,
    grid_places INTEGER,
    fault_language VARCHAR,
    accused_driver_number INTEGER,
    accused_driver_id VARCHAR,
    accused_driver_name VARCHAR,
    accused_driver_abbreviation VARCHAR,
    accused_f1_country_code VARCHAR,
    accused_nationality VARCHAR,
    british_accused_driver BOOLEAN,
    home_race_accused BOOLEAN,
    accused_identity_match_status VARCHAR NOT NULL,
    affected_driver_count INTEGER NOT NULL,
    principal_affected_driver_id VARCHAR,
    british_affected_driver BOOLEAN,
    affected_identity_complete BOOLEAN NOT NULL,
    multi_party BOOLEAN NOT NULL,
    parser_review_required BOOLEAN NOT NULL,
    timing_session_loaded BOOLEAN NOT NULL,
    accused_driver_result_present BOOLEAN NOT NULL,
    panel_data_status VARCHAR NOT NULL,
    feature_provenance VARCHAR NOT NULL,
    PRIMARY KEY (feature_build_id, adjudication_instance_id)
);

CREATE TABLE IF NOT EXISTS analysis.adjudication_driver_roles (
    feature_build_id VARCHAR NOT NULL,
    workspace_id VARCHAR NOT NULL,
    adjudication_instance_id VARCHAR NOT NULL,
    event_id VARCHAR NOT NULL,
    session_type VARCHAR,
    driver_role VARCHAR NOT NULL CHECK (driver_role IN ('accused', 'affected')),
    role_sequence INTEGER NOT NULL,
    driver_number INTEGER NOT NULL,
    driver_id VARCHAR,
    driver_name VARCHAR,
    abbreviation VARCHAR,
    f1_country_code VARCHAR,
    nationality VARCHAR,
    is_british BOOLEAN,
    home_race_driver BOOLEAN,
    identity_match_status VARCHAR NOT NULL,
    role_number_basis VARCHAR NOT NULL,
    PRIMARY KEY (
        feature_build_id,
        adjudication_instance_id,
        driver_role,
        role_sequence
    )
);

CREATE TABLE IF NOT EXISTS analysis.feature_release_controls (
    feature_build_id VARCHAR NOT NULL,
    control_order INTEGER NOT NULL,
    control VARCHAR NOT NULL,
    status VARCHAR NOT NULL CHECK (status IN ('pass', 'fail')),
    observed VARCHAR NOT NULL,
    expected VARCHAR NOT NULL,
    detail VARCHAR NOT NULL,
    PRIMARY KEY (feature_build_id, control)
);

CREATE OR REPLACE VIEW analysis.v_latest_adjudication_features AS
WITH latest AS (
    SELECT feature_build_id
    FROM metadata.analysis_feature_builds
    ORDER BY built_at_utc DESC, feature_build_id DESC
    LIMIT 1
)
SELECT features.*
FROM analysis.adjudication_features AS features
JOIN latest USING (feature_build_id);

CREATE OR REPLACE VIEW analysis.v_latest_adjudication_driver_roles AS
WITH latest AS (
    SELECT feature_build_id
    FROM metadata.analysis_feature_builds
    ORDER BY built_at_utc DESC, feature_build_id DESC
    LIMIT 1
)
SELECT roles.*
FROM analysis.adjudication_driver_roles AS roles
JOIN latest USING (feature_build_id);
