# Steward-Panel Extraction and Release Gate

Status: full 2018–2025 document-panel lineage extracted; panel-nationality analysis remains
blocked pending source-backed steward nationalities.

## Purpose

FIA decision signatures identify the people who issued a decision. Preserving that composition at
the document level is necessary because a Grand Prix weekend can use more than one panel: a steward
may be substituted between decisions, and treating the event as one fixed panel would assign the
wrong decision-maker exposure.

The extraction is run with:

```powershell
f1stewards load-steward-panels --strict-extraction
```

`--strict-extraction` evaluates signature and assignment controls only. It does not bypass the
separate nationality-analysis release gate.

## Source and identity method

The population is every live, content-confirmed `steward_decision` in
`analysis.v_source_documents_typed`. The parser reads only the final 20 text lines, where FIA
decision signatures occur, and matches exact reviewed spellings from
`config/steward_name_aliases.csv`. A line may contain one name or two concatenated names. Accent,
OCR, abbreviated-name, and historical source-spelling variants map to stable steward IDs, but fuzzy
matching is not used.

An exact document parse must identify three to five unique registered stewards. Panel identity is a
content hash of the event ID and the sorted steward IDs, so PDF line order cannot create a false new
panel. The original matched signature lines and parser version remain on the document assignment.

If a document cannot be parsed directly, it receives an event-consensus assignment only when exact
documents establish exactly one panel for that event. An unreadable document at an event with two
or more observed panels remains unresolved. This rule prevents a substitution from being smoothed
away for coverage.

Signature order is not interpreted as authority. `chair_steward_id`, `driver_steward_id`, and
specific member roles remain null or `member_role_not_inferred` until a source explicitly supports
them.

## Full-corpus result

| Control or diagnostic | Result |
|---|---:|
| Live decision documents | 1,951 |
| Direct exact signature parses | 1,935 |
| Direct parse rate | 99.18% |
| Single-panel event-consensus assignments | 16 |
| Unresolved document assignments | 0 |
| Events represented | 173 |
| Events with direct panel evidence | 173 |
| Distinct document-linked panels | 181 |
| Four-member panels | 173 |
| Five-member panels | 8 |
| Stable steward identities | 83 |
| Events with multiple observed panels | 7 |

The seven multi-panel events are China 2018, Mexico 2018, Portugal 2020, Turkey 2020, Spain 2023,
Abu Dhabi 2023, and Canada 2025. Canada 2025 contains three observed panel compositions. All are
retained as separate identities and assigned at document grain.

The 16 consensus assignments occur only in events with one directly observed panel. They are
distributed across Abu Dhabi 2018; Japan 2019; Italy, São Paulo, and Singapore 2022; Japan, São
Paulo, and the United States 2024; and Azerbaijan, Las Vegas, Saudi Arabia, and Singapore 2025.
Consensus is therefore transparent, bounded, and reproducible rather than a general imputation.

## Warehouse lineage

- `metadata.steward_name_aliases`: reviewed observed spelling to stable steward ID;
- `curated.stewards`: one identity, with nationality fields preserved across panel rebuilds;
- `curated.panels`: one distinct event-panel composition;
- `curated.panel_members`: one steward membership in one panel, without inferred authority;
- `curated.document_panels`: one exact, consensus, or unresolved assignment per decision document;
- `analysis.v_document_panel_composition`: evidence-oriented document and panel summary.

The loader refreshes active document assignments and panel memberships while upserting steward
identities. It intentionally does not overwrite `nationality` or `nationality_source_url`, so later
source research remains intact on a reproducible panel rebuild.

## Release controls and interpretation

Seven extraction controls pass: nonempty population, at least 95% direct parsing, direct evidence
in every event, complete document assignment, valid three-to-five-member panels, a complete exact
panel dimension, and retention of multi-panel event structure. Two analysis-release controls fail
by design because the dated evidence has not yet been promoted to conflict-resolved assignments for
all 83 panel stewards.

The dated source register and its first observed conflict are documented in
[`steward_country_evidence.md`](steward_country_evidence.md). This replaces the unsafe assumption
that one unqualified static nationality can be assigned directly from an FIA country code.

Until that source register is complete, this layer supports panel fixed/group effects, decision
lineage inspection, and substitution diagnostics, but not same-nationality, British-panel, or
panel-nationality conclusions. Even after release, an association with panel composition will not
by itself establish bias: cases are not randomly assigned to stewards, panels cluster by event, and
unobserved evidence may affect decisions.
