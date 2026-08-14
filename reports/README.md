# The Cost of Discretion

## What public FIA data can and cannot show about Formula 1 stewarding, 2018-2025

Read the completed report as an [executable Jupyter notebook](../notebooks/06_final_oversight_report.ipynb)
or a [code-free HTML report](the_cost_of_discretion.html).

The follow-on [Study v2 report](the_cost_of_discretion_study_v2.html) and its
[executable notebook](../notebooks/12_study_v2_report.ipynb) implement the improvement roadmap while
adding a strict source-cited model audit and keeping the remaining evidence gates visible.

### Main finding

The penalty written in a stewarding decision is not always what it costs on track. The report keeps
four facts separate: responsibility, the written penalty, its actual competitive cost, and harm to
the affected driver.

In the independently reviewed pilot, Perez's post-race five-second penalty cost two places, six
points, and a podium. Colapinto's post-race five-second penalty changed no place or points. A served
ten-second penalty changed strategy and traffic, so simply subtracting ten seconds from the final
time would be misleading.

![Four reviewed cases show different competitive consequences for nominal sanctions](generated/pilot_harm_sanction_matrix.png)

### What the full dataset supports

The evidence system covers all 173 completed events from 2018 through 2025: 9,467 FIA archive
records, 2,003 version-preserving outcome records, 1,984 local source files, and 1,935 effective
steward decisions. The released primary set contains 346 formal Race/Sprint cases across 131 events.

GPT-5.6 Sol completed a disclosed strict audit of all 418 included decisions and 502 sampled
exclusions. Every one of the 920 audit rows cites an FIA source. The audit corrected seven fault
labels and 25 affected-driver lists, confirmed 32 predecessor-successor version pairs, and retained
four unavailable archive labels as unresolved public evidence. This is model-led source review, not
independent human annotation.

![The source population narrows to 346 model-reviewed cases](generated/population_flow.png)

Of the 346 cases, 214 received a sanction (61.8%). Rates vary by incident family and season, but
these differences are descriptive and mix case facts, rule changes, mitigation, and referral.

![Sanction rates vary across incident types and seasons](generated/model_reviewed_sanction_rates.png)

### Consistency result

A grouped model using incident type, season, and multi-car status barely improved over a simple
baseline. Its ROC AUC was 0.558. This does not prove inconsistent stewarding. It shows that broad
case labels do not capture enough decision context to judge consistency or rank supposedly bad
decisions.

![Broad case labels do not predict decisions reliably](generated/grouped_model_calibration.png)

### Nationality conclusion

British accused drivers received sanctions in 25 of 44 cases (56.8%), compared with 189 of 302
other-driver cases (62.6%). That raw 5.8-point difference is not an adjusted estimate. With only 44
British-driver cases, the design is underpowered for subtle effects.

The result is **inconclusive**. It is not evidence of either bias or no bias.

![Simulation shows inadequate power for subtle nationality effects](generated/nationality_power.png)

### Study v2 implementation

The next version now has executable scaffolding for all six recommendations:

1. The strict model audit covers 920 source records with zero unresolved adversarial exceptions.
   Blank blinded packets remain available for optional future independent human validation.
2. The public Race Control feed yields 966 episodes and 177 high-confidence decision links.
3. Outcome-blind matching gives at least five close neighbors to 317 of 346 cases.
4. Conduct, participant harm, and sanction burden are stored in separate tables and units.
5. Driver-specific timing gives 241 single-lap harm mappings and 28 estimable teammate-relative
   pace screens; these remain source-research leads, not confirmed damage effects.
6. Nationality remains gated and inconclusive: the British-accused cell is 44 versus the frozen
   minimum of 98, and the 15-point power target is not met.

The proportionality release remains at zero because damage, causal harm, and realized sanction cost
are not complete enough for a population claim. The report does not turn timing screens or nominal
penalties into a fairness verdict.

The machine-verifiable [Study v2 completion audit](generated/study_v2/completion_audit.csv) checks
27 protocol, citation, artifact, gate, notebook, and report controls. It preserves the distinction
between model review and independent human review.

### Portfolio evidence

The project uses tested Python, Jupyter, DuckDB SQL, FastF1 enrichment, traceable review records,
Git/CI, and a locally validated Snowflake/Snowsight package. The report explicitly separates
model-reviewed findings from independently human-reviewed pilot evidence.
