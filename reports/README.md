# The Cost of Discretion

## What public FIA data can and cannot show about Formula 1 stewarding, 2018-2025

Read the completed report as an [executable Jupyter notebook](../notebooks/06_final_oversight_report.ipynb)
or a [code-free HTML report](the_cost_of_discretion.html).

### Main finding

The penalty written in a stewarding decision is not always what it costs on track. This report calls
the written penalty the *nominal sanction* and the actual loss in places, points, or starting position
the *realized burden*.

In the independently reviewed pilot, Perez's post-race five-second penalty cost two places, six
points, and a podium. Colapinto's post-race five-second penalty changed no place or points. A served
ten-second penalty changed strategy and traffic, so simply subtracting ten seconds from the final
time would be misleading. A later three-place grid penalty had a clear effect on the next starting
grid, but not a measurable effect on the race result.

This difference matters for fairness, but it does not prove that a decision was wrong. The report
studies four related facts separately: responsibility, the written penalty, the penalty's actual
cost, and harm to the affected driver.

![Four reviewed cases show different competitive consequences for nominal sanctions](generated/pilot_harm_sanction_matrix.png)

### What the full dataset supports

The evidence system covers all 173 completed events from 2018 through 2025: 9,467 FIA archive
records, 2,003 version-preserving outcome records, 1,984 live outcome PDFs, and 1,952 confirmed
steward decisions. The possible primary case set contains 348 decisions across 131 events.

None of those 348 cases is approved for full-dataset reporting because independent document, case,
and exclusion review is incomplete. The report therefore withholds league-wide penalty rates,
anomaly rankings, guideline-departure rates, and nationality effects.

![The source population narrows to a deliberately blocked analytical release](generated/population_flow.png)

### Nationality conclusion

The design includes 44 British and 304 other accused-driver cases. Most cases have reasonable
comparisons in the other group, but the sample is too small to detect subtle differences. Estimated
power ranges from 8.2% to 78.8% across the prespecified scenarios, below the 80% target.

The result is **inconclusive**. It is not evidence of either bias or no bias. This design check did
not use observed penalty outcomes.

![Simulation shows inadequate power for subtle nationality effects](generated/nationality_power.png)

### Best ways to strengthen the study

1. Treat decision consistency and competitive consequence as two separate primary analyses.
2. Independently review all possible analytical cases, high-risk records, and the prespecified
   sample of exclusions; expand review when errors cross a published threshold.
3. Use Race Control messages to study the path from an incident being noted to a formal decision.
4. Compare closely matched cases before using a broader statistical model.
5. Estimate lasting damage on a representative collision sample with clean-lap controls and
   uncertainty ranges; keep cases as "not estimable" when the data cannot support an answer.
6. Keep nationality secondary unless a larger sample can detect differences small enough to matter.

### Recommendations to the FIA

1. Publish stable incident and decision IDs with driver roles, session, lap, finding, penalty timing,
   and version status.
2. Publish the exact guidance active at each event and list the normal penalty plus written
   aggravating or mitigating factors.
3. Report seconds, starting positions, finishing positions, points, repair, damage, and retirement
   separately instead of reducing them to one fairness score.
4. Publish what was noted, investigated, formally decided, and not referred.
5. Use models to flag cases for human review, not to decide that a steward was wrong.

### Portfolio evidence

The project uses tested Python, Jupyter, DuckDB SQL, FastF1 enrichment, traceable review records,
Git/CI, and a locally validated Snowflake/Snowsight package. Most importantly, the workflow blocks a
finding when its evidence checks have not passed.
