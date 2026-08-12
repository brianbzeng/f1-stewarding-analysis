# Event-Date Regulatory Catalog Method

## Purpose

The analysis must not treat a season label as a regulation version. The FIA can publish several
issues of the Formula One Sporting Regulations during one season, and two revisions can share a
publication date. This catalog turns that versioning problem into an explicit, testable data step.

The machine-readable issue history is in `config/f1_sporting_regulation_issues.yml`. It contains 65
official FIA archive entries covering every season from 2018 through 2025. DuckDB stores the records
in `metadata.sporting_regulation_issues`; the view
`analysis.v_event_sporting_regulation_selection` selects one candidate issue per dated event.

## Selection rule

For event (e), select the issue for the same season with the latest FIA publication date that is not
later than the event date:

\[
r_e = \underset{r}{\operatorname{argmax}}\; (r.publication\_date, r.precedence)
\]

where `r.season = e.season` and `r.publication_date <= e.event_date`. `precedence` resolves same-day
revisions, including the two Issue 6 entries published for 2024 on 30 April.

This is a deterministic candidate-selection rule, not proof that the selected text was in force.
Publication metadata can be incomplete, documents can be replaced at the same URL, and an effective
date can differ from a publication date.

## Two verification levels

| Level | Meaning | Permitted use |
|---|---|---|
| `provisional_by_publication_date` | The issue title and date are transcribed from the official FIA archive | Coverage audits and a queue for binary resolution |
| `event_verified` | The exact official binary applicable to a named event has been resolved | Clause-level interpretation after download, hashing, and effective-date review |

An archive-only record is never silently promoted to event-verified. The data model requires every
`event_verified` record to have a resolved official document URL. Before full analysis, selected
binaries will also receive retrieval timestamps and SHA-256 hashes in the source manifest.

## Pilot validation

The selector reproduces the three manually researched pilot assignments:

| Event | Selected issue | Verification |
|---|---|---|
| 2019 Austrian Grand Prix | 12 March 2019 revision | Exact official PDF resolved |
| 2023 Abu Dhabi Grand Prix | Issue 7, 25 October 2023 | Exact official PDF resolved; Issue 8 was published after the race |
| 2025 Austrian Grand Prix | Issue 5, 30 April 2025 | Exact official PDF resolved |

Automated tests cover these assignments, same-day precedence, complete 2018–2025 season coverage,
and the failure case where no issue had been published by an event date. Release quality checks also
require every dated event to have a selection and every pilot selection to be event-verified.

## Related instruments

The Sporting Regulations are only one layer. A separate nine-record International Sporting Code
catalog covers 2018–2025 in `config/international_sporting_code_issues.yml`. Its effective windows
load to `metadata.international_sporting_code_issues`, and
`analysis.v_event_international_sporting_code_selection` maps each event to the issue whose effective
window contains the event date. This matters in 2020, when the archive lists both the initial annual
edition and a clean version dated 24 April.

The current FIA archive exposes clean annual Code binaries for 2020–2025. The official 2018 clean and
2019 marked-up binaries are also resolved, but their original publication dates are no longer exposed
in the current category view; that limitation is a field in the catalog. The revised April 2020 clean
binary still requires direct-URL resolution, so 2020 events after 23 April remain provisional for
clause-level use.

Appendix L, event Race Director notes, and any public driving or penalty guidelines must be assigned
separately because their publication histories and legal roles differ. The current gaps are tracked
in `reports/regulatory_source_gap_register.csv` rather than being filled with later or unofficial text.

Key official indexes and explanations are maintained in `docs/source_register.md`:

- FIA Formula One Regulations Archive;
- FIA International Sporting Code and Appendices Archive;
- public 2025 F1 Driving Standards Guidelines;
- public 2025 Stewards Penalty Guidelines; and
- FIA explanations of the guidelines' history and non-regulatory status.

## Scale gate

Before an event enters clause-level or guideline-conformance analysis:

1. select candidate versions using the event date;
2. resolve the exact official binary without substituting a later file;
3. verify its effective window and role;
4. download and hash it;
5. link it to the event in the warehouse; and
6. log an explicit gap if any step cannot be completed.

Descriptive decision counts may proceed with a documented source gap. A source gap blocks only the
claim that depends on that source; it does not justify deleting the event or imputing legal text.
