-- Each query must return zero rows before a release is tagged.

-- DuckDB does not enforce foreign keys across schemas, so these checks enforce lineage.
SELECT d.document_id, d.event_id
FROM raw.source_documents AS d
LEFT JOIN metadata.events AS e USING (event_id)
WHERE e.event_id IS NULL;

-- Every event in the frozen 2018-2025 population must have discovered FIA evidence.
SELECT e.event_id, e.season
FROM metadata.events AS e
LEFT JOIN raw.source_documents AS d USING (event_id)
GROUP BY e.event_id, e.season
HAVING count(d.document_id) = 0;

-- Parsed content types must remain in the documented source taxonomy.
SELECT document_id, content_document_class, content_classification_basis
FROM raw.document_text
WHERE content_document_class IS NOT NULL
  AND content_document_class NOT IN (
      'steward_decision', 'summons', 'final_classification',
      'provisional_classification', 'championship_points',
      'race_director_notes', 'circuit_map', 'other'
  );

SELECT document_id, content_document_class, content_classification_basis
FROM raw.document_text
WHERE (content_document_class IS NULL) <> (content_classification_basis LIKE 'empty_text%');

-- A verified-unavailable record must preserve both the failed attempt and adjudication note.
SELECT document_id, source_availability_status, retrieval_error, source_availability_note
FROM raw.source_documents
WHERE source_availability_status = 'verified_unavailable'
  AND (
      retrieval_error IS NULL
      OR source_availability_note IS NULL
      OR content_sha256 IS NOT NULL
      OR is_recalled
  );

SELECT document_id, source_availability_status
FROM raw.source_documents
WHERE source_availability_status NOT IN ('advertised', 'verified_unavailable');

-- Corrected-document lineage must point backward to one recalled record in the same event.
SELECT
    successor.document_id,
    successor.event_id,
    successor.supersedes_document_id,
    predecessor.event_id AS predecessor_event_id,
    predecessor.is_recalled AS predecessor_is_recalled
FROM raw.source_documents AS successor
LEFT JOIN raw.source_documents AS predecessor
    ON predecessor.document_id = successor.supersedes_document_id
WHERE successor.supersedes_document_id IS NOT NULL
  AND (
      predecessor.document_id IS NULL
      OR predecessor.event_id <> successor.event_id
      OR NOT predecessor.is_recalled
      OR successor.is_recalled
  );

SELECT supersedes_document_id, count(*) AS successor_count
FROM raw.source_documents
WHERE supersedes_document_id IS NOT NULL
GROUP BY supersedes_document_id
HAVING count(*) > 1;

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

-- Harm assessments must resolve to adjudications and official classification evidence.
SELECT h.harm_assessment_id
FROM curated.harm_assessments AS h
LEFT JOIN curated.adjudications AS a USING (adjudication_id)
LEFT JOIN raw.source_documents AS d
  ON h.classification_source_document_id = d.document_id
WHERE a.adjudication_id IS NULL OR d.document_id IS NULL;

-- Observed position harm must preserve complete arithmetic.
SELECT harm_assessment_id
FROM curated.harm_assessments
WHERE net_positions_lost_observed IS NOT NULL
  AND (
      position_before IS NULL
      OR position_after IS NULL
      OR net_positions_lost_observed <> position_after - position_before
  );

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

-- Every dated event must map to a season-effective International Sporting Code issue.
SELECT e.event_id, e.season, e.event_date
FROM metadata.events AS e
LEFT JOIN analysis.v_event_international_sporting_code_selection AS r USING (event_id)
WHERE e.event_date IS NOT NULL
  AND r.source_id IS NULL;

-- Pilot Code selections require a resolved official binary and verified effective date.
SELECT event_id, source_id, resolution_status, selection_status
FROM analysis.v_event_international_sporting_code_selection
WHERE event_id IN ('2019-aut', '2023-abu', '2025-aut')
  AND (
      document_url IS NULL
      OR resolution_status NOT LIKE 'verified_official_binary%'
      OR selection_status <> 'effective_date_verified'
  );

-- Supplemental locations must resolve to both an incident and their cited source document.
SELECT l.location_id
FROM curated.incident_locations AS l
LEFT JOIN curated.adjudications AS a USING (incident_id)
LEFT JOIN raw.source_documents AS d ON l.source_document_id = d.document_id
WHERE a.incident_id IS NULL OR d.document_id IS NULL;

-- A turn range preserves source wording only when both increasing bounds are present.
SELECT location_id
FROM curated.incident_locations
WHERE location_type = 'turn_range'
  AND (
      turn_start_number IS NULL
      OR turn_end_number IS NULL
      OR turn_end_number <= turn_start_number
  );

-- Directed incident edges must resolve and cannot connect a driver to itself.
SELECT r.relation_id
FROM curated.incident_relations AS r
LEFT JOIN curated.adjudications AS a USING (incident_id)
LEFT JOIN raw.source_documents AS d ON r.source_document_id = d.document_id
WHERE a.incident_id IS NULL
   OR d.document_id IS NULL
   OR r.source_driver_number = r.target_driver_number;

-- Each incident chain uses a contiguous, unique sequence beginning at one.
WITH ordered AS (
    SELECT
        relation_id,
        incident_id,
        sequence,
        row_number() OVER (PARTITION BY incident_id ORDER BY sequence) AS expected_sequence
    FROM curated.incident_relations
)
SELECT relation_id
FROM ordered
WHERE sequence <> expected_sequence;

-- A cross-event sanction effect must resolve to the originating adjudication and sanction source.
SELECT x.cross_event_effect_id
FROM curated.cross_event_sanction_effects AS x
LEFT JOIN curated.adjudications AS a USING (adjudication_id)
LEFT JOIN curated.incidents AS i USING (incident_id)
LEFT JOIN raw.source_documents AS d ON x.source_document_id = d.document_id
WHERE a.adjudication_id IS NULL
   OR d.document_id IS NULL
   OR x.origin_event_id <> i.event_id;

-- Realized grid displacement is deterministic qualifying-to-start arithmetic.
SELECT cross_event_effect_id
FROM curated.cross_event_sanction_effects
WHERE realized_grid_places_lost <> starting_grid_position - qualifying_position
   OR (
       grid_effect_level = 'mechanical'
       AND realized_grid_places_lost <> nominal_grid_places
   );

-- Session-keyed FastF1 rows must resolve to the frozen event catalog.
SELECT r.event_id, r.session_type
FROM raw.fastf1_session_results AS r
LEFT JOIN metadata.events AS e USING (event_id)
WHERE e.event_id IS NULL
   OR (r.session_type = 'Sprint' AND NOT e.has_sprint);

-- Every normalized lap must resolve to one classification row in the same session.
SELECT l.event_id, l.session_type, l.driver_number, l.lap_number
FROM raw.fastf1_session_laps AS l
LEFT JOIN raw.fastf1_session_results AS r
  ON r.event_id = l.event_id
 AND r.session_type = l.session_type
 AND r.driver_number = l.driver_number
WHERE r.driver_number IS NULL;

-- Absolute lap-time lineage must agree with timestamp presence and the derived flag.
SELECT event_id, session_type, driver_number, lap_number,
       lap_start_timestamp, lap_start_timestamp_basis,
       lap_start_timestamp_is_derived
FROM raw.fastf1_session_laps
WHERE lap_start_timestamp_basis NOT IN (
          'fastf1_lap_start_date',
          'session_t0_plus_lap_start_time',
          'unavailable'
      )
   OR (lap_start_timestamp_basis = 'unavailable' AND lap_start_timestamp IS NOT NULL)
   OR (lap_start_timestamp_basis <> 'unavailable' AND lap_start_timestamp IS NULL)
   OR (
       lap_start_timestamp_is_derived
       <> (lap_start_timestamp_basis = 'session_t0_plus_lap_start_time')
   );

-- Normalization lineage must be recognized and conservative raw fallbacks cannot become clean laps.
SELECT event_id, session_type, driver_number, lap_number,
       lap_normalization_basis, compound, tyre_life, fresh_tyre, is_accurate
FROM raw.fastf1_session_laps
WHERE lap_normalization_basis NOT IN (
          'fastf1_session_laps',
          'fastf1_raw_timing_fallback',
          'legacy_pilot_fastf1_session_laps'
      )
   OR (
       lap_normalization_basis = 'fastf1_raw_timing_fallback'
       AND (
           is_accurate IS DISTINCT FROM FALSE
           OR compound IS NOT NULL
           OR tyre_life IS NOT NULL
           OR fresh_tyre IS NOT NULL
       )
   );

-- Successful ingestion ledger counts must reconcile to the stored session tables.
WITH observed AS (
    SELECT
        i.event_id,
        i.session_type,
        count(DISTINCT r.driver_number) AS result_rows,
        count(DISTINCT (l.driver_number, l.lap_number)) AS lap_rows,
        (
            SELECT count(*)
            FROM raw.fastf1_session_race_control_messages AS m
            WHERE m.event_id = i.event_id
              AND m.session_type = i.session_type
        ) AS message_rows,
        count(DISTINCT CASE
            WHEN l.lap_start_timestamp_basis = 'fastf1_lap_start_date'
                THEN (l.driver_number, l.lap_number)
        END) AS direct_lap_timestamp_rows,
        count(DISTINCT CASE
            WHEN l.lap_start_timestamp_basis = 'session_t0_plus_lap_start_time'
                THEN (l.driver_number, l.lap_number)
        END) AS derived_lap_timestamp_rows,
        count(DISTINCT CASE
            WHEN l.lap_start_timestamp_basis = 'unavailable'
                THEN (l.driver_number, l.lap_number)
        END) AS missing_lap_timestamp_rows
    FROM metadata.fastf1_session_ingestion AS i
    LEFT JOIN raw.fastf1_session_results AS r
      ON r.event_id = i.event_id
     AND r.session_type = i.session_type
    LEFT JOIN raw.fastf1_session_laps AS l
      ON l.event_id = i.event_id
     AND l.session_type = i.session_type
    WHERE i.status = 'succeeded'
    GROUP BY i.event_id, i.session_type
)
SELECT i.event_id, i.session_type
FROM metadata.fastf1_session_ingestion AS i
JOIN observed AS o USING (event_id, session_type)
WHERE i.status = 'succeeded'
  AND (
      i.finished_at IS NULL
      OR i.error_message IS NOT NULL
      OR i.result_rows <> o.result_rows
      OR i.lap_rows <> o.lap_rows
      OR i.message_rows <> o.message_rows
      OR i.direct_lap_timestamp_rows <> o.direct_lap_timestamp_rows
      OR i.derived_lap_timestamp_rows <> o.derived_lap_timestamp_rows
      OR i.missing_lap_timestamp_rows <> o.missing_lap_timestamp_rows
      OR i.lap_normalization_basis IS NULL
      OR EXISTS (
          SELECT 1
          FROM raw.fastf1_session_laps AS basis_lap
          WHERE basis_lap.event_id = i.event_id
            AND basis_lap.session_type = i.session_type
            AND basis_lap.lap_normalization_basis
                IS DISTINCT FROM i.lap_normalization_basis
      )
  );
