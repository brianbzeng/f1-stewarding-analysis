# The Cost of Discretion

## What public FIA data can—and cannot—establish about Formula 1 stewarding, 2018–2025

The completed report is available as an [executable Jupyter notebook](../notebooks/06_final_oversight_report.ipynb)
and a [code-free HTML reading version](the_cost_of_discretion.html).

### Executive finding

A nominal sanction and its realized competitive burden are not the same quantity. In the
independently reviewed pilot, Pérez's post-race five-second penalty mechanically cost two places,
six points, and a podium; Colapinto's post-race five-second penalty changed no place and no points.
A served ten-second penalty could not be converted honestly into a finishing counterfactual, while
a delayed three-place grid penalty had an exact starting-grid effect but an unknowable race-result
effect.

That gap matters to fairness, but it does not prove that a stewarding decision was wrong. The report
therefore keeps four dimensions separate: the responsibility finding, nominal sanction, realized
sanction burden, and affected-driver harm.

![Four reviewed cases show different competitive consequences for nominal sanctions](generated/pilot_harm_sanction_matrix.png)

### What the full corpus supports

The evidence system covers all 173 completed events from 2018 through 2025: 9,467 FIA archive
records, 2,003 version-preserving outcome labels, 1,984 live outcome PDFs, and 1,952
content-confirmed steward decisions. The provisional primary feature set contains 348 adjudications
across 131 events.

It contains **zero reporting-eligible full-corpus rows** because independent document,
adjudication, and 486-row exclusion-QA review remains incomplete. This is a deliberate fail-closed
control. The report consequently withholds league-wide sanction rates, anomaly rankings,
guideline-departure rates, and nationality effects.

![The source population narrows to a deliberately blocked analytical release](generated/population_flow.png)

### Nationality conclusion

The outcome-free design contains 44 British and 304 other accused-driver exposures. Estimated
common support is 97.4%, and overlap weighting reduces the largest absolute standardized difference
from 0.526 to 0.040. But no frozen power scenario reaches the 80% target: estimated detection power
ranges from 8.2% to 78.8% for assumed 5–20 percentage-point differences.

The correct conclusion is **inconclusive**, not “no bias” and not “bias.” No observed sanction
outcome was used in this design diagnostic.

![Simulation shows inadequate power for subtle nationality effects](generated/nationality_power.png)

### Recommendations

1. Publish structured, stable incident and adjudication identifiers with driver roles, session,
   lap, finding, sanction, application timing, and version status.
2. Publish the exact guidance effective at each event and identify the written baseline,
   aggravating factors, and mitigation in each decision.
3. Report seconds, grid positions, classification positions, points, repair, damage, and retirement
   separately; do not reduce them to one fairness score.
4. Preserve the referral limitation: formal decisions show treatment only among referred cases.
5. Use calibrated models to prioritize evidence review, never to declare a steward wrong
   automatically.

### Portfolio evidence

The report is backed by source-preserving ETL, typed Python models, DuckDB SQL, FastF1 enrichment,
content-addressed review lineage, automated validation, executed Jupyter notebooks, a self-service
evidence console, Git/CI, and a locally validated Snowflake/Snowsight deployment package. The
release gate demonstrates the same governance principle as an oversight data system: an available
number is not automatically an authorized finding.
