-- Each query must return zero rows before a release is tagged.

-- DuckDB does not enforce foreign keys across schemas, so these checks enforce lineage.
SELECT d.document_id, d.event_id
FROM raw.source_documents AS d
LEFT JOIN metadata.events AS e USING (event_id)
WHERE e.event_id IS NULL;

SELECT i.incident_id, i.source_document_id
FROM curated.incidents AS i
LEFT JOIN raw.source_documents AS d ON i.source_document_id = d.document_id
WHERE d.document_id IS NULL;

SELECT a.adjudication_id, a.decision_document_id
FROM curated.adjudications AS a
LEFT JOIN raw.source_documents AS d ON a.decision_document_id = d.document_id
WHERE d.document_id IS NULL;

-- Official evidence without a checksum after a claimed successful retrieval.
SELECT document_id, document_url
FROM raw.source_documents
WHERE retrieved_at IS NOT NULL
  AND retrieval_error IS NULL
  AND content_sha256 IS NULL;

-- Adjudications whose incident has not completed at least one review.
SELECT a.adjudication_id, i.coding_status, a.review_status
FROM curated.adjudications AS a
JOIN curated.incidents AS i USING (incident_id)
WHERE i.coding_status = 'unreviewed'
   OR a.review_status = 'unreviewed';

-- Impossible penalty values.
SELECT adjudication_id, penalty_seconds, penalty_points, grid_places
FROM curated.adjudications
WHERE COALESCE(penalty_seconds, 0) < 0
   OR COALESCE(penalty_points, 0) < 0
   OR COALESCE(grid_places, 0) < 0;

-- Mechanical impact must not be presented without its explicit arithmetic.
SELECT adjudication_id
FROM curated.classification_impact
WHERE impact_level = 'mechanical'
  AND (official_finish_position IS NULL OR mechanical_finish_position IS NULL);

-- Every event/source bridge must resolve on both sides.
SELECT l.event_id, l.source_id
FROM metadata.event_regulatory_sources AS l
LEFT JOIN metadata.events AS e USING (event_id)
LEFT JOIN metadata.regulatory_sources AS s USING (source_id)
WHERE e.event_id IS NULL OR s.source_id IS NULL;

-- A source cannot be labeled applicable when its stated window excludes the event.
SELECT l.event_id, l.source_id, e.event_date, s.effective_from, s.effective_through
FROM metadata.event_regulatory_sources AS l
JOIN metadata.events AS e USING (event_id)
JOIN metadata.regulatory_sources AS s USING (source_id)
WHERE s.applicability_status LIKE 'applicable%'
  AND (
      (s.effective_from IS NOT NULL AND e.event_date < s.effective_from)
      OR (s.effective_through IS NOT NULL AND e.event_date > s.effective_through)
  );

-- A report claim must not be marked release-ready without a declared evidence grade.
SELECT claim_id, status, evidence_grade_if_met
FROM metadata.claim_ledger
WHERE status IN ('supported_for_inference', 'descriptive_only', 'case_study_only')
  AND evidence_grade_if_met NOT IN ('A', 'B', 'C', 'D');

-- Every dated event must map to the latest Sporting Regulation issue published by that date.
SELECT e.event_id, e.season, e.event_date
FROM metadata.events AS e
LEFT JOIN analysis.v_event_sporting_regulation_selection AS r USING (event_id)
WHERE e.event_date IS NOT NULL
  AND r.source_id IS NULL;

-- Pilot clause-level work requires an event-verified official binary, not archive metadata alone.
SELECT event_id, source_id, resolution_status, selection_status
FROM analysis.v_event_sporting_regulation_selection
WHERE event_id IN ('2019-aut', '2023-abu', '2025-aut')
  AND (
      resolution_status <> 'verified_official_binary'
      OR selection_status <> 'event_verified'
  );
