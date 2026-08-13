CREATE TABLE IF NOT EXISTS metadata.steward_country_evidence (
    evidence_id VARCHAR PRIMARY KEY,
    steward_id VARCHAR NOT NULL,
    observed_date DATE NOT NULL,
    date_precision VARCHAR NOT NULL CHECK (
        date_precision IN ('exact', 'month', 'season', 'year')
    ),
    source_country_code VARCHAR NOT NULL,
    analysis_country_code VARCHAR NOT NULL,
    evidence_dimension VARCHAR NOT NULL CHECK (
        evidence_dimension IN (
            'fia_published_country_code',
            'formula1_competition_nationality',
            'fia_asn_affiliation',
            'fia_biographical_country'
        )
    ),
    source_type VARCHAR NOT NULL,
    source_url VARCHAR NOT NULL,
    source_title VARCHAR NOT NULL,
    source_note VARCHAR NOT NULL
);

CREATE OR REPLACE VIEW analysis.v_steward_country_evidence_summary AS
WITH evidence AS (
    SELECT
        steward_id,
        count(*) AS evidence_records,
        count(DISTINCT analysis_country_code) AS distinct_analysis_codes,
        min(observed_date) AS first_observed_date,
        max(observed_date) AS last_observed_date,
        string_agg(
            DISTINCT analysis_country_code,
            ' | '
            ORDER BY analysis_country_code
        ) AS observed_analysis_codes
    FROM metadata.steward_country_evidence
    GROUP BY steward_id
)
SELECT
    steward.steward_id,
    steward.full_name,
    coalesce(evidence.evidence_records, 0) AS evidence_records,
    coalesce(evidence.distinct_analysis_codes, 0) AS distinct_analysis_codes,
    evidence.first_observed_date,
    evidence.last_observed_date,
    evidence.observed_analysis_codes,
    CASE
        WHEN evidence.steward_id IS NULL THEN 'no_source_evidence'
        WHEN evidence.distinct_analysis_codes > 1 THEN 'source_conflict_unresolved'
        ELSE 'single_observed_code_not_temporally_resolved'
    END AS resolution_status
FROM curated.stewards AS steward
LEFT JOIN evidence USING (steward_id);

CREATE OR REPLACE VIEW analysis.v_steward_country_research_worklist AS
WITH exposure AS (
    SELECT
        member.steward_id,
        count(DISTINCT member.panel_id) AS panel_count,
        count(DISTINCT assignment.document_id) AS decision_document_count,
        min(event.season) AS first_study_season,
        max(event.season) AS last_study_season
    FROM curated.panel_members AS member
    JOIN curated.panels AS panel USING (panel_id)
    JOIN curated.document_panels AS assignment USING (panel_id)
    JOIN metadata.events AS event ON event.event_id = panel.event_id
    GROUP BY member.steward_id
)
SELECT
    summary.steward_id,
    summary.full_name,
    summary.resolution_status,
    summary.evidence_records,
    summary.observed_analysis_codes,
    exposure.panel_count,
    exposure.decision_document_count,
    exposure.first_study_season,
    exposure.last_study_season,
    CASE summary.resolution_status
        WHEN 'source_conflict_unresolved' THEN 1
        WHEN 'no_source_evidence' THEN 2
        ELSE 3
    END AS research_priority_tier
FROM analysis.v_steward_country_evidence_summary AS summary
JOIN exposure USING (steward_id)
WHERE summary.resolution_status <> 'single_observed_code_not_temporally_resolved'
ORDER BY
    research_priority_tier,
    exposure.decision_document_count DESC,
    summary.full_name;
