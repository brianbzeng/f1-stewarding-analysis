# Pilot Independent Review Guide

The pilot has an AI-assisted first coding pass. This review is the first independent human check and
must remain separate from the initial file so agreement and corrections are auditable.

## What to review

Open `data/manual/pilot_independent_review.csv`. It contains 13 targets:

- nine accused-driver adjudications;
- two mechanically calculated post-race penalty impacts;
- one served-penalty impact labeled not estimable;
- one next-event grid-penalty impact labeled not estimable.

Each row contains official FIA evidence links and a short initial summary. Use
`data/manual/pilot_coded_adjudications.csv`, `data/manual/pilot_impact_assessments.csv`, the decision
codebook, and the event-date source matrix for the complete first-pass fields.

## Review procedure

For each row:

1. Start a timer and open every URL in `evidence_urls`.
2. For an adjudication, verify accused and affected drivers, incident grouping, session, lap, turn,
   incident family, outcome, sanction values, responsibility language, evidence cited, first-lap
   status, guideline clause, conformance, and primary-study inclusion.
3. For an impact assessment, verify how the sanction was applied, completed laps, official order and
   gaps, evidence tier, arithmetic, points, podium/win flags, and assumptions.
4. Set `review_status` to `agree`, `correct`, or `needs_discussion`.
5. Add `reviewer_id`, an ISO-8601 UTC timestamp, and `review_minutes`.
6. For `correct`, write only changed fields in `corrected_fields_json` and explain the evidence in
   `reviewer_notes`. Example: `{"lap_number": 47, "turn_number": 6}`.
7. For `needs_discussion`, explain the ambiguity in `reviewer_notes`.
8. Run `f1stewards review-status` after saving.

After all discussion items are resolved, run `f1stewards reconcile-pilot`. The command will refuse
an incomplete sheet and will create new reviewed versions rather than modifying either first-pass
file. See `docs/pilot_reconciliation_workflow.md` for the protected fields and audit outputs.

Do not edit the first-pass adjudication or impact CSV during independent review. Reconciliation is a
separate, documented step.

## Known items that deserve attention

- Two 2019 documents concern opposite sides of the same lap-69 incident. Confirm whether two
  adjudication rows are appropriate for the final estimand.
- FIA incident times are minute-rounded. A lapped driver's personal lap can differ from the global
  race lap, particularly Colapinto's 2025 incidents.
- 2025 Doc 46 appears to replace unavailable recalled Doc 39; confirm the lineage language without
  assuming identical content.
- The current 2023 Appendix L link resolves to a 6 December revision, after Abu Dhabi. Do not use it
  to infer event-date internal guidance.
- Perez's 2023 penalty was added after the race; Tsunoda's 2025 penalty was served. The same number
  of seconds therefore does not support the same counterfactual method.

## Completion criteria

The review gate passes only when:

- all 13 rows are complete;
- every correction has a non-empty JSON object and evidence note;
- every discussion item is reconciled or explicitly accepted as unresolved;
- review effort is summarized for scale planning;
- final reconciled rows receive a new coder/reviewer version rather than silent overwrites.
