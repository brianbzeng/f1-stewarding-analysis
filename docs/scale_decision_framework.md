# Full-Scale Collection Decision Framework

The 2018-2025 collector starts only after the pilot produces a defensible `go`, `go with reduced
scope`, or `stop/revise` decision. Technical feasibility alone is not enough.

## Gates

| Gate | Pass rule | Current status |
|---|---|---|
| Discovery and retrieval | all visible pilot records represented; linked evidence resumable and checksummed | pass |
| Decision parsing | at least 95% extract core text or enter a visible exception queue | pass |
| Source lineage | recalls/corrections preserved; unresolved version gaps explicitly flagged | conditional pass |
| Event-date law/guidance | governing versions linked without retrospective substitution | conditional pass: 2023 Appendix L binary unresolved |
| Timing and classification | all pilot Race sessions link; official tables cross-checked | pass |
| Coding validity | controlled fields and impossible combinations validated | pass |
| Independent review | all pilot targets reviewed; disagreements reconciled | pending |
| Review burden | median minutes per target supports the available project schedule | pending |
| Analytical yield | estimated comparable adjudications support each planned model | pending full inventory |

## Decision choices

### Go

Use when the review vocabulary is stable, unresolved lineage is acceptably rare, and the measured
review burden is sustainable. Collect all Race and Sprint events from 2018-2025.

### Go with reduced scope

Use when broad collection is feasible but one analytical claim is not. Possible reductions:

- focus on causing collisions and forcing off track;
- use 2022-2025 for comparability while retaining older seasons descriptively;
- limit guideline conformance to public 2025 guidance;
- treat nationality as descriptive if adjusted power or overlap is inadequate;
- exclude qualifying impeding from the primary release.

### Stop/revise

Use when corrected-decision lineage cannot be resolved reliably, review effort is excessive, or the
estimated comparable sample is too small for the promised adjusted models. A strong descriptive
oversight report is preferable to an underpowered causal-sounding analysis.

## Metrics to record after review

- completed targets and unresolved targets;
- agreement, correction, and discussion counts;
- median and total review minutes;
- fields with the most disagreement;
- recalled/corrected lineage resolution rate;
- rate of records requiring external video or unavailable evidence;
- estimated adjudications per event and by incident family;
- minimum detectable effect or simulation-based power for each inferential question.

Run `f1stewards scale-readiness` for the measured gate table. It deliberately returns
`blocked_pending_review` while any review target is pending and `human_go_no_go_required` after all
objective gates pass; it never turns review time or analytical yield into an automatic scope choice.

## Claim-level decision

Each research question receives its own designation after full inventory and EDA:

- `supported for inference`;
- `descriptive only`;
- `case-study only`;
- `dropped`.

The project should not expand model complexity to preserve a predetermined headline.
