# Study v2 Strict Model Audit Protocol

Status: frozen on 13 August 2026 before the strict case audit was run.

## Purpose and disclosure

GPT-5.6 Sol reviews every included decision and every source in the frozen exclusion-audit
population. This is a source-cited model audit. It is not independent human annotation, does not
fill the Reviewer A or Reviewer B ledgers, and cannot be described as inter-rater human agreement.

The audit contains 920 unique FIA sources:

- 346 primary Race/Sprint decisions;
- 72 secondary decisions; and
- 502 sampled exclusions receiving version and scope review.

The two human-review arms contain 654 assignments but only 560 unique sources because 94 sources
overlap. Repeating those 94 rows with the same model would not create independence, so the strict
model audit reviews each source once and uses a separate adversarial pass for material exceptions.

The terminal content-addressed run is `strict-model-audit-0fe15fd6b052`. It records 884 source
confirmations, 32 source-cited corrections, and four archive labels whose public source remains
unavailable. No adversarial exception is unresolved. The four unavailable labels remain explicitly
bounded as unavailable evidence rather than being counted as confirmations.

## Source and citation contract

Every record must cite an exact official FIA source URL. Every included decision must also preserve
a short evidence span from the decision. A rule or guideline assessment must cite the applicable
rule or guideline source separately. Search-result URLs do not count. Missing or unresolved source
evidence blocks completion instead of being converted to agreement.

The terminal run passes this gate for 920 of 920 records. All 418 included decisions have an FIA
decision URL and evidence span. Thirty-three included decisions receive a contemporaneous public
Penalty Guideline comparison and therefore also cite that guideline. Two ambiguous session/scope
exclusions use an additional official event-context source, and 32 version predecessors link to the
cited successor decision.

Citation roles remain separate:

1. the FIA decision supports what the stewards found and imposed;
2. an event-date regulation, Code, Appendix, or guideline supports a rule comparison;
3. official timing and classification support observed race sequence and position;
4. team or Formula 1 reporting may support attributed damage or repair evidence; and
5. public video may support only the visible facts at the cited timestamp and angle.

## Review order

For each included decision, the model records:

1. source version, source completeness, and exact citation;
2. session, incident family, accused driver, affected drivers, lap, and location;
3. FIA finding, sanction, written fault language, and evidence span;
4. applicable event-date Sporting Regulations and International Sporting Code issue;
5. whether public contemporaneous Driving or Penalty Guidelines are available;
6. public-evidence assessability, without pretending to have unavailable steward footage;
7. sanction-guideline status where a public contemporaneous guideline exists;
8. consequence evidence in a separate layer; and
9. confidence, exceptions, and adversarial-review status.

The first source-led pass is reconciled against the prior model-reviewed fields only after the
source checks are recorded. The adversarial pass targets corrections, parser warnings, family
conflicts, multi-car incidents, sparse reasons, potential guideline tensions, close-case outcome
contrasts, and material harm cases. It searches for an alternative interpretation and records why
the initial decision was retained, corrected, or left unresolved.

The correction ledger changes seven fault-language fields and 25 affected-driver lists. It stores
the parent value, reviewed value, exact source evidence, rationale, and decision citation. It does
not modify the protected parent workspace or either human-review ledger. A separate analysis adapter
applies only these reviewed included-decision fields so downstream screening cannot silently keep
using the superseded values.

The 502 exclusion checks are not copied from the parent disposition. Each is independently
classified from the official source body, session, and investigated offence wording. Version cases
receive predecessor-successor pair review. The final exclusion audit consists of 465 source-body
or session confirmations, 32 version-pair confirmations, two confirmations using a second official
context source, and four unavailable archive labels.

## Historical rule boundary

The public 2025 documents say they are guidelines rather than regulations. Driving Standards were
introduced internally in 2022, while Penalty Guidelines existed internally earlier, but the exact
historical issues are not fully public. The audit therefore:

- never applies the 2025 or 2026 guidelines retrospectively;
- uses the event-date regulation and Code catalogs;
- labels unavailable historical guideline comparisons explicitly;
- distinguishes archive-metadata selection from an event-verified official binary; and
- does not call a pre-2025 sanction a guideline departure without the contemporaneous document.

## Decision language

The audit does not force `fair` or `unfair`. Its public-evidence assessment uses bounded language:

- `fia_reasoning_documented`;
- `fia_reasoning_documented_visual_basis_not_independently_verified`;
- `limited_public_reasoning`;
- `public_evidence_tension`; or
- `not_independently_assessable`.

Sanction assessment is separate:

- `within_contemporaneous_public_guideline`;
- `within_guideline_with_documented_mitigation`;
- `substitution_or_escalation_requires_context`;
- `potential_public_guideline_tension`;
- `no_public_contemporaneous_penalty_guideline`; or
- `not_applicable_no_breach_finding`.

No large consequence can back-fill fault. No absence of a public visual can prove that the FIA
finding was wrong. An unresolved case remains visible and blocks any stronger claim that depends on
it.
