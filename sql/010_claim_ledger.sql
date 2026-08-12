CREATE TABLE IF NOT EXISTS metadata.claim_ledger (
    claim_id VARCHAR PRIMARY KEY,
    report_section VARCHAR NOT NULL,
    research_question VARCHAR NOT NULL,
    claim_template VARCHAR NOT NULL,
    estimand VARCHAR NOT NULL,
    population VARCHAR NOT NULL,
    required_method VARCHAR NOT NULL,
    minimum_acceptance VARCHAR NOT NULL,
    required_sensitivity VARCHAR NOT NULL,
    evidence_grade_if_met VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    primary_limitation VARCHAR NOT NULL
);
