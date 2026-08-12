CREATE TABLE IF NOT EXISTS curated.harm_assessments (
    harm_assessment_id VARCHAR PRIMARY KEY,
    adjudication_id VARCHAR NOT NULL REFERENCES curated.adjudications(adjudication_id),
    incident_id VARCHAR NOT NULL,
    event_id VARCHAR NOT NULL,
    source_document_id VARCHAR NOT NULL,
    classification_source_document_id VARCHAR NOT NULL,
    affected_driver_number INTEGER NOT NULL,
    counterparty_driver_number INTEGER NOT NULL,
    responsibility_status VARCHAR NOT NULL CHECK (
        responsibility_status IN (
            'fault_established', 'shared_or_racing_incident', 'no_fault_finding', 'unresolved'
        )
    ),
    harm_evidence_level VARCHAR NOT NULL CHECK (
        harm_evidence_level IN ('observed', 'bounded', 'modeled', 'not_estimable')
    ),
    damage_evidence VARCHAR NOT NULL CHECK (
        damage_evidence IN (
            'confirmed', 'repair_observed', 'alleged', 'no_confirmed_damage', 'unknown'
        )
    ),
    damage_type VARCHAR NOT NULL,
    repair_stop_required VARCHAR NOT NULL CHECK (repair_stop_required IN ('yes', 'no', 'unclear')),
    pit_lap INTEGER,
    pit_response_status VARCHAR NOT NULL CHECK (
        pit_response_status IN ('confirmed', 'plausible', 'no', 'unclear')
    ),
    pit_lane_loss_seconds DOUBLE,
    repair_stationary_seconds DOUBLE,
    retirement_status VARCHAR NOT NULL,
    position_before INTEGER,
    position_after INTEGER,
    net_positions_lost_observed INTEGER,
    affected_relative_time_loss_seconds DOUBLE,
    post_incident_clean_laps INTEGER NOT NULL,
    persistent_pace_status VARCHAR NOT NULL,
    persistent_delta_per_lap_seconds DOUBLE,
    persistent_laps_exposed INTEGER,
    persistent_loss_seconds_lower DOUBLE,
    persistent_loss_seconds_estimate DOUBLE,
    persistent_loss_seconds_upper DOUBLE,
    net_effect_direction VARCHAR NOT NULL CHECK (
        net_effect_direction IN ('harmed', 'neutral', 'possible_benefit', 'benefit', 'unclear')
    ),
    benefit_mechanism VARCHAR,
    evidence_urls VARCHAR NOT NULL,
    calculation_method VARCHAR NOT NULL,
    assumptions VARCHAR NOT NULL,
    review_status VARCHAR NOT NULL
);

CREATE VIEW IF NOT EXISTS analysis.v_harm_sanction_balance AS
SELECT
    h.harm_assessment_id,
    h.adjudication_id,
    h.incident_id,
    h.event_id,
    h.affected_driver_number,
    h.counterparty_driver_number,
    h.responsibility_status,
    h.harm_evidence_level,
    h.damage_evidence,
    h.repair_stop_required,
    h.retirement_status,
    h.net_positions_lost_observed,
    h.affected_relative_time_loss_seconds,
    h.persistent_loss_seconds_lower,
    h.persistent_loss_seconds_estimate,
    h.persistent_loss_seconds_upper,
    h.net_effect_direction,
    a.outcome_family,
    a.penalty_seconds,
    a.penalty_points,
    a.grid_places,
    i.positions_changed AS sanction_positions_changed,
    i.points_changed AS sanction_points_changed,
    CASE
        WHEN h.responsibility_status <> 'fault_established'
            THEN 'not_comparable_without_fault_finding'
        WHEN h.harm_evidence_level = 'not_estimable'
            THEN 'harm_not_estimable'
        ELSE 'eligible_for_multimetric_review'
    END AS proportionality_scope
FROM curated.harm_assessments AS h
JOIN curated.adjudications AS a USING (adjudication_id)
LEFT JOIN curated.classification_impact AS i USING (adjudication_id);
