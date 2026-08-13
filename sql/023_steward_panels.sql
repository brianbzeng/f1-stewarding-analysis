CREATE TABLE IF NOT EXISTS metadata.steward_name_aliases (
    observed_name VARCHAR PRIMARY KEY,
    steward_id VARCHAR NOT NULL,
    canonical_name VARCHAR NOT NULL,
    alias_status VARCHAR NOT NULL
);

ALTER TABLE curated.panel_members
ADD COLUMN IF NOT EXISTS member_sequence INTEGER;

CREATE TABLE IF NOT EXISTS curated.document_panels (
    document_id VARCHAR PRIMARY KEY,
    event_id VARCHAR NOT NULL,
    panel_id VARCHAR REFERENCES curated.panels(panel_id),
    assignment_basis VARCHAR NOT NULL CHECK (
        assignment_basis IN ('document_signature_exact', 'single_event_panel_consensus', 'unresolved')
    ),
    signature_parse_status VARCHAR NOT NULL CHECK (
        signature_parse_status IN ('exact', 'event_consensus', 'unresolved')
    ),
    extracted_member_count INTEGER NOT NULL,
    raw_signature_lines VARCHAR,
    parser_version VARCHAR NOT NULL
);

CREATE OR REPLACE VIEW analysis.v_document_panel_composition AS
SELECT
    assignment.document_id,
    assignment.event_id,
    assignment.panel_id,
    assignment.assignment_basis,
    assignment.signature_parse_status,
    assignment.extracted_member_count,
    panel.panel_size,
    string_agg(steward.full_name, ' | ' ORDER BY member.member_sequence)
        AS panel_member_names,
    count(steward.steward_id) FILTER (
        WHERE steward.nationality IS NOT NULL
    ) AS sourced_nationality_members,
    count(steward.steward_id) FILTER (
        WHERE steward.nationality IS NULL
    ) AS missing_nationality_members
FROM curated.document_panels AS assignment
LEFT JOIN curated.panels AS panel USING (panel_id)
LEFT JOIN curated.panel_members AS member USING (panel_id)
LEFT JOIN curated.stewards AS steward USING (steward_id)
GROUP BY
    assignment.document_id,
    assignment.event_id,
    assignment.panel_id,
    assignment.assignment_basis,
    assignment.signature_parse_status,
    assignment.extracted_member_count,
    panel.panel_size;
