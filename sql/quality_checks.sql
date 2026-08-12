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
