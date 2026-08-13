# Exclusion Quality-Control Audit

Status: machine-assisted diagnostics complete; independent human disposition pending.

## Objective

The exclusion audit tests a high-risk pipeline failure: an FIA decision that belongs in a planned
analysis could be assigned an out-of-scope suggestion because of changing session terminology,
legacy wording, or an overly broad strict-liability pattern.

The audit population is not chosen by fame or analyst judgment. `exclusion_qa_sample.csv` uses a
frozen SHA-256 ordering within season, normalized session scope, and suggested offence-family
strata. The current v4 seed selects 486 of 1,505 proposed exclusions and covers all 272 observed
strata.

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

## V4 classifier audit

The v4 refinement compared every regenerated suggestion with the prior protected release before any
seed was overwritten. It recovered 35 primary Race/Sprint candidates and eight explicit qualifying-
impeding candidates without losing any previously identified primary or secondary candidate. The
35 primary additions were inspected as a set; they include legacy collision phrasing, the three 2018
Abu Dhabi Alonso advantage decisions, and the 2024 Austrian Sprint forcing-off decision.

That audit also caught a false-positive mechanism in an intermediate preview. Seven qualifying
documents were being labeled as impeding solely because their Reason section said that a driver
“did not impede” another car. Reason-text fallback is now restricted to primary-family recovery;
qualifying impeding must be explicit in the title, Fact, or Infringement text. Regression tests cover
both the negative phrasing and procedural-context cases such as impeding at pit exit.

Known Practice and other out-of-scope sessions now take precedence over family ambiguity, while an
unknown session is never guessed from event context. After these corrections, 59 offence-family
rows and 18 session rows remain manual rather than being forced into or out of scope. The resulting
486-row exclusion sample contains 77 parser-warning documents that must be inspected from the
official PDF before their exclusions can be accepted.

Recovery of the correct 2018 Brazilian archive exposed a different semantic false positive. The
post-race Verstappen–Ocon garage ruling says that one driver made deliberate "physical contact"
with another; a generic `contact with` pattern initially treated it as an on-track collision. The
classifier now assigns explicit driver-to-driver physical contact to procedural/personnel review,
while retaining car-contact and collision language in the primary driving-incident family. A
regression test freezes that distinction. This moved one record out of the provisional primary
population and triggered complete seed, QA-sample, workspace, feature, and notebook regeneration.

This is a machine-assisted diagnostic result, not independent review agreement. No sample row is
promoted to final exclusion merely because the regenerated screen found no conflict.

## Evidence-linked review handoff

All 486 frozen QA rows now join exactly once by `document_id` to their protected adjudication seed.
The full-corpus review console displays the available Fact, Infringement, Decision, and Reason text
next to the proposed exclusion and official FIA link. Section availability is 423 Fact, 424
Infringement, 434 Decision, and 414 Reason records; nonstandard formats remain visibly incomplete.

The content-addressed `exception-packet-e59c0de45246` groups the 486 QA rows with overlapping
document and adjudication exceptions. Eighty-one QA sources appear in all three queues, so one
source investigation can inform all linked decisions without silently copying a QA disposition.
The remaining 405 are QA-only investigations. See
[the exception packet release record](full_corpus_exception_packet.md).

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
