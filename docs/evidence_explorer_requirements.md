# Evidence Explorer Requirements

## Product purpose

The explorer is a self-service review tool for an analyst or recruiter who wants to inspect the data
behind the report without reading code. It is not a public accusation leaderboard.

## Primary users

- oversight analyst reviewing comparable decisions;
- technical reviewer tracing a result to official evidence;
- report reader testing a chart or headline;
- project maintainer triaging data-quality exceptions.

## Required views

### Overview

- population and evidence-completeness cards;
- adjudications by season, rule regime, incident family, and outcome;
- visible banner with review and release status;
- links to protocol, codebook, and limitations.

### Decision search

- filters for season, event, session, incident family, outcome, sanction, driver, counterpart,
  guideline regime, conformance, evidence tier, and review status;
- one row per final accused-driver adjudication;
- expandable Fact, Decision, Reason, coding notes, and version lineage;
- official decision, classification, and rule URLs.

### Comparable cases

- selected case plus nearest comparable adjudications;
- observed context differences and unavailable-evidence warning;
- expected outcome, residual, support score, and model version;
- no rank ordering when comparable support is below the frozen threshold.

### Competitive impact

- separate tabs or facets for mechanical, bounded, modeled, and not estimable;
- visible arithmetic and assumptions;
- official and counterfactual classification only for mechanical rows;
- aggregate totals never mix tiers silently.

### Data quality

- missing source, checksum, linkage, rule-version, and review exceptions;
- recalled and corrected documents;
- pipeline run, commit, and data-as-of timestamp;
- downloadable filtered CSV with stable identifiers and source URLs.

## Acceptance criteria

- Default state contains no nationality or driver accusation ranking.
- Every displayed adjudication resolves to an official decision URL.
- Every 2025 conformance label resolves to the applicable guideline source and clause.
- Every mechanical impact reproduces the reference SQL/Python result.
- Filter counts equal DuckDB reference queries for a fixed test fixture.
- Empty, loading, invalid-filter, and no-evidence states are explicit.
- Keyboard navigation, focus order, contrast, chart descriptions, and table headers meet WCAG AA
  expectations.
- All user-facing numbers state unit and denominator.
- The explorer displays `provisional` until all relevant inputs are independently reviewed.

## Implementation decision

The pilot uses a generated, dependency-free static HTML application. This keeps the review artifact
portable for a recruiter while preserving DuckDB and Python as the tested source of truth. Product
quality comes from reliable filters, evidence links, state handling, and documentation rather than
framework complexity.

## Pilot implementation status

| Requirement | Pilot status | Evidence |
|---|---|---|
| Visible release state | Implemented | Header status and provisional overview warning |
| Evidence-linked decision search | Implemented | Expandable Fact, Decision, Reason, notes, and official URLs |
| Comparable-case findings | Intentionally gated | Unavailable until reviewed full corpus and model validation |
| Competitive impact | Implemented provisionally | Mechanical and non-estimable rows remain visibly separated |
| Data quality and lineage | Implemented | Retrieval, recall, rule-gap, review, timestamp, and commit fields |
| Filtered export | Implemented | Client-side CSV with stable IDs and FIA source URLs |
| Nationality ranking exclusion | Enforced | Payload validator and filter allowlist |
| 2025 guideline lineage | Enforced | Build fails when an applicable label lacks clause or rule URL |
| Accessibility baseline | Implemented and test-covered | Semantic tabs/table, keyboard tab navigation, focus styles, live count |

The pilot is not a model-results release. Its primary purpose is to prove traceability and make the
manual review packet inspectable before collection expands to 2018-2025.

## Full-corpus operational console

The full-corpus console is deliberately separate from the substantive evidence explorer. Its job is
to move the protected 2018–2025 worklists through human review, not to display model outputs before
the release gates pass.

| Operational requirement | Status | Evidence |
|---|---|---|
| All review queues visible | Implemented | 2,003 document, 1,952 adjudication, and 486 exclusion-QA rows |
| Official source on every row | Enforced | Payload validation requires an FIA URL for all 4,441 targets |
| Protected source lineage | Enforced | Build requires the edited-workspace validator to pass |
| Search, queue filters, paging | Implemented | Dependency-free client-side interface with 50-row pages |
| Draft final fields | Implemented | Browser-local edits are restricted to the documented editable fields |
| Portable change handoff | Implemented | Content-addressed JSON ledger and filtered CSV downloads |
| Stale/protected edit rejection | Enforced | Ledger importer checks workspace hash, queue, row ID, and field allowlists |
| Analytical claims gated | Enforced | Console can report review completion only, never model release |
| Multi-row source splits | Documented manual step | CSV split procedure remains necessary before console rebuild |

The console remains `blocked_pending_human_review` at 0 of 4,441 completed targets. Even when every
review row is complete, its strongest permitted state is
`workspace_review_complete_pending_feature_controls`; the separate feature builder owns analytical
release authority.
