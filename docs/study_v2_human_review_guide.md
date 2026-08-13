# Study v2 Independent Human Review Guide

The packet is source-first and blind to GPT-5.6 Sol's final coding. Do not look at the model-reviewed
workspace while completing a row. Read `raw_text`; use the separated sections as navigation aids,
not as a replacement for the full source. Open `source_url` when the text is missing, garbled, or
ambiguous.

Reviewer A covers every elevated-risk or multi-car source plus a deterministic clean-exclusion
sample. Reviewer B covers every high-risk inclusion, a separate stratified exclusion sample, and all
published pilot case studies. Type only in the `reviewed_*`, confidence, evidence, reviewer, date,
and notes columns. Do not add, remove, rename, reorder, or sort rows.

## Coding order

1. Decide whether this is the effective source version.
2. Identify the source body: decision, summons, note, classification, or other.
3. Code the session and incident family from the source.
4. Decide whether it belongs in the frozen primary or secondary study population.
5. For included decisions, code accused and affected drivers, lap, location, outcome, sanction, and
   fault language.
6. Copy a short evidence span and explain any inference in `review_notes`.

Use `unknown` when the public source does not support a value. Do not infer a driver from a headline
when the body contradicts it. Preserve every participant in a multi-car incident; responsibility is
edge-specific. Do not use damage or finishing outcome to infer fault.

## Allowed review values

- version: `effective`, `superseded`, `recalled_unavailable`, `unknown`
- content class: `steward_decision`, `summons`, `race_director_note`, `classification`, `other`,
  `unknown`
- eligibility: `primary`, `secondary`, `exclude`, `unknown`
- outcome: `time_penalty`, `grid_penalty`, `drive_through`, `stop_go`, `reprimand`,
  `no_further_action`, `racing_incident`, `other`, `unknown`
- fault: `wholly_to_blame`, `predominantly_to_blame`, `mainly_at_fault`, `shared_fault`,
  `racing_incident`, `no_conclusion`, `not_applicable`, `unknown`
- confidence: `high`, `medium`, `low`

Pipe-separate multiple driver numbers in source order. Use numbers only, without `Car` prefixes.
Penalty fields remain blank when they do not apply. Store the lap and location only when stated or
when your note documents a defensible Race Control/timing link.

## Reconciliation

After both packets are complete, a comparison script will populate `reconciliation_queue.csv` with
field-level disagreements. The adjudicator reads the source without being told which reviewer is
preferred, records one reconciled value and evidence span, and signs the row. Do not settle
disagreements by copying the previous model answer.

Completing this audit validates the reviewed records and estimates error in the sampled exclusions.
It does not turn unreviewed model-coded records into human-coded records.
