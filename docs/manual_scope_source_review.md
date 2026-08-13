# Manual-Scope Source Review

Status: all 61 targeted FIA-source investigations coded once; independent verification remains
pending.

The versioned ledger `data/manual/review_ledgers/manual_scope_v1.json` resolves the cases that could
not be assigned safely by the parser and frozen scope rules alone. It is locked to source workspace
SHA-256 `c7d62651b6eb7646b1682e616e32666620cdbc6f8a1d3a451d3da9e4d8ceb7ae`; the ledger SHA-256 is
`dbddce05e43f71a84cc213953b804a49778c59b903576aeb20cae78e053f5f76`.

## Dispositions

| Disposition | Count |
|---|---:|
| Primary inclusions | 52 |
| Controlled exclusions | 9 |
| Causing-collision inclusions | 43 |
| Forcing-off-track inclusions | 7 |
| Gaining-advantage inclusions | 2 |

The ledger corrects affected-driver roles, sanctions, sessions, laps, and locations only where the
official decision supports them. Mirrored decisions share an incident ID, and multi-car records
retain every supported affected role rather than being reduced to a two-driver assumption. The
2024 Miami Sprint chain, for example, remains one four-car incident represented by three
driver-side adjudications.

Scope exclusions remain evidence-bearing records. The 2025 Monaco Stroll/Leclerc collision is
excluded because it occurred in Practice 1, but its future one-place grid penalty and penalty point
are preserved. The 2025 Belgian Hülkenberg/Stroll record is excluded from the secondary population
because the driver incident was a Qualifying collision, while the separately documented competitor
reprimand concerned pit-lane procedure.

Every changed record is labeled `single_coded_pending_human`. The ledger is a source-coding pass,
not an independent review or analytical release.

## Unavailable recalled versions

The separate `unresolved_recalled_versions_v1.json` ledger records the four 2024 Belgian
pit-lane-speeding labels that the official archive marks recalled without exposing a live PDF or
successor. It codes `recalled_unavailable`, preserves the pit-lane-speeding family, excludes the
records from analysis, and does not impute a session, decision, or sanction. Its ledger SHA-256 is
`81976e4db17d52c58ccdbdfe1b79de41e828eb92cf2edb3a08b37201e019969d`.
