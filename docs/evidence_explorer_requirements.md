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

Build only after the curated schema and analytical queries stabilize. A small Streamlit or static
Plotly/Dash-style application is sufficient; product quality comes from reliable filters, evidence
links, state handling, and documentation rather than framework complexity.
