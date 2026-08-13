# Exclusion Quality-Control Audit

Status: first machine-assisted diagnostic complete; independent human disposition pending.

## Objective

The exclusion audit tests a high-risk pipeline failure: an FIA decision that belongs in a planned
analysis could be assigned an out-of-scope suggestion because of changing session terminology,
legacy wording, or an overly broad strict-liability pattern.

The audit population is not chosen by fame or analyst judgment. `exclusion_qa_sample.csv` uses a
frozen SHA-256 ordering within season, normalized session scope, and suggested offence-family
strata. The current seed selects 403 of 1,305 proposed exclusions and covers all 223 observed strata.

## First diagnostic and correction

The first generated sample exposed a real false-exclusion mechanism. FIA documents from 2021 use
`Sprint Qualifying` for the Saturday sprint race. The initial normalizer treated the phrase like the
2024-present qualifying session that sets the Sprint grid. That would have excluded, among other
records:

- Car 63 causing a collision with Car 55 during the 2021 British Sprint;
- Car 55 allegedly rejoining unsafely during the same Sprint; and
- Car 11 allegedly leaving the track and gaining an advantage during the 2021 Italian Sprint.

The normalizer is now season-aware: the 2021 label maps to `Sprint`, while the 2024-present label
maps to `Sprint Qualifying`. A regression test freezes both meanings. The source rules and every
seed hash were regenerated after the correction.

The same diagnostic found a wording gap for `left the track ... rejoined and gained a lasting
advantage`. The primary-family screen now recognizes an intervening phrase rather than requiring
“left the track” and “gained an advantage” to be adjacent. Any simultaneous track-limit match is
sent to manual offence review instead of automatic inclusion or exclusion.

## Post-correction screen

The regenerated 403-row sample was joined one-to-one to the parsed Fact, Infringement, Decision,
and Reason fields. A deliberately broader, separately written lexical screen found:

- 61 rows with general driving-incident language;
- 13 rows with one of the six primary-family phrases; and
- 29 rows containing an impeding word form.

The source-level diagnostic of the primary- or secondary-session hits found no additional automatic
rule change:

- Race/Sprint collision phrases came from pit-lane unsafe releases, which are outside the on-track
  primary population, or from a Race Director-instruction decision that explicitly found no unsafe
  rejoin and no gained advantage.
- Collision, track-limit, and unsafe-rejoin allegations in Qualifying remain outside the primary
  Race/Sprint population and do not meet the separately defined qualifying-impeding population.
- Qualifying documents that merely say drivers took steps “not to impede” were SC2-SC1 delta-time
  or Race Director-instruction decisions, not impeding adjudications.
- The Race-session impeding hit concerned equipment obstructing another car in the pit lane, not
  the qualifying-impeding population.

This is a diagnostic result, not independent review agreement. Fifty-nine sampled documents carry
parser warnings and must be inspected from the official PDF before their exclusions can be accepted.
No sample row is promoted to final exclusion merely because the broad screen found no conflict.

## Release rule

Each sampled record must ultimately receive `confirm_exclusion`, `false_exclusion`, or
`needs_discussion`, with a reviewer ID, source URL, and note. A confirmed false exclusion triggers:

1. rule-cause analysis;
2. a configuration or parser correction when the failure is systematic;
3. full seed regeneration and new hashes;
4. rerunning the entire stratified audit; and
5. preserving the superseded audit release in Git history.

The final report will state both the proposed-exclusion population and reviewed audit results. It
will not present the machine suggestion as a measured eligibility error rate.
