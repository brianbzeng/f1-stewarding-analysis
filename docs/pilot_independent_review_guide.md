# Pilot Independent Review Guide

The pilot has an AI-assisted first coding pass. This review is the first independent human check and
must remain separate from the initial file so agreement and corrections are auditable.

## What to review

Open `data/manual/pilot_independent_review.csv`. It contains 26 targets. The original 15 are
complete and preserved; the second-stage extension adds 11 pending targets:

- nine accused-driver adjudications;
- two mechanically calculated post-race penalty impacts;
- one served-penalty impact labeled not estimable;
- one next-event grid-penalty impact labeled not estimable.
- two mirrored driver-side harm assessments for the 2019 Austria lap-69 incident.
- seven additional affected-driver harm assessments, completing one harm row for every pilot
  adjudication;
- one source-preserving turn-range location;
- two directed edges in one three-car incident chain; and
- one carried-over grid-sanction effect.

Each row contains official FIA evidence links and a short initial summary. Use
`data/manual/pilot_coded_adjudications.csv`, `data/manual/pilot_impact_assessments.csv`,
`data/manual/pilot_harm_assessments.csv`, the three extension CSVs, the decision codebook, and the
event-date source matrix for the complete first-pass fields.

## Review procedure

For each row:

1. Start a timer and open every URL in `evidence_urls`.
2. For an adjudication, verify accused and affected drivers, incident grouping, session, lap, turn,
   incident family, outcome, sanction values, responsibility language, evidence cited, first-lap
   status, guideline clause, conformance, and primary-study inclusion.
3. For an impact assessment, verify how the sanction was applied, completed laps, official order and
   gaps, evidence tier, arithmetic, points, podium/win flags, and assumptions.
4. For a harm assessment, verify driver roles, responsibility status, confirmed versus unconfirmed
   damage, repair-stop link, position/time arithmetic, post-incident clean-lap support, net effect,
   and the distinction between observed change and causal counterfactual.
5. For a location, verify the exact source wording and reject false single-turn precision.
6. For each relation edge, verify direction, type, scope, evidence tier, and whether fault is
   attributed to that edge. Do not spread primary fault to contextual participants.
7. For a cross-event effect, verify the origin sanction, later qualifying/start positions, signed
   grid arithmetic, race status, and whether the finish/points counterfactual is supportable.
8. Set `review_status` to `agree`, `correct`, or `needs_discussion`.
9. Add `reviewer_id`, an ISO-8601 UTC timestamp, and `review_minutes`.
10. For `correct`, write only changed fields in `corrected_fields_json` and explain the evidence in
   `reviewer_notes`. Example: `{"lap_number": 47, "turn_number": 6}`.
11. For `needs_discussion`, explain the ambiguity in `reviewer_notes`.
12. Run `f1stewards review-status` after saving.

After all discussion items are resolved, run `f1stewards reconcile-pilot`. The command will refuse
an incomplete sheet and will create new reviewed versions rather than modifying either first-pass
file. See `docs/pilot_reconciliation_workflow.md` for the protected fields and audit outputs.

Do not edit any first-pass analytical CSV during independent review. Reconciliation is a separate,
documented step.

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
- For 2019 Austria, Leclerc's P1-to-P2 change and the 1.683-second relative swing are observed. The
  pass, racing line, battle, and contact are inseparable in that number. No repair stop is present,
  and one clean post-incident lap is insufficient to estimate lasting damage.
- Gasly's 2023 diffuser damage and continuing downforce loss are directly reported, but earlier
  Perez contact prevents a clean Hamilton-only seconds or finishing-position estimate.
- Norris retains P4 through the 2023 contact lap and loses it when Perez completes the pass on the
  following lap; the explicit position/time windows preserve both facts.
- Colapinto reports possible damage after Tsunoda contact, but Tsunoda's immediate front-wing stop
  invalidates a simple two-car relative-gap calculation.
- Piastri was forced onto the grass while chasing Norris, but his pit timing overlaps the available
  lap window and the 2.695-second final gap does not prove that the incident changed the winner.
- Antonelli's Austrian penalty moves him exactly from P7 qualifying to P10 on the British grid. His
  wet-race retirement after separate contact prevents a mechanical finish or points counterfactual.

## Completion criteria

The review gate passes only when:

- all 26 rows are complete;
- every correction has a non-empty JSON object and evidence note;
- every discussion item is reconciled or explicitly accepted as unresolved;
- review effort is summarized for scale planning;
- final reconciled rows receive a new coder/reviewer version rather than silent overwrites.
