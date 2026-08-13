# Full-Corpus Exception Investigation Packet

Status: content-addressed investigation packet generated; source review and independent disposition
remain pending.

## Purpose

The first-pass worklists contain 682 deliberately unstarted queue rows, but many refer to the same
official FIA decision. The exception packet makes the source document—not a duplicated spreadsheet
row—the investigation unit. It preserves every queue ID in a linkage table so no denominator or QA
obligation disappears.

Generate or byte-verify it with:

```powershell
f1stewards build-full-corpus-exception-packet `
  data/manual/full_corpus_first_pass/full-coding-e0192ecbd9e4
```

The current packet is `exception-packet-b4c076afb79f`, schema
`full-corpus-exception-packet-v1`, derived from `first-pass-5aa88d7f05b2` and workspace SHA-256
`de816c98622f6b429529041ad616fe706cbfdf17e82d169d598aff45b6e7bca9`.

| Output | Rows | SHA-256 |
|---|---:|---|
| `investigation_queue.csv` | 582 | `a077ab241fc0da4508fcb6b1a417a0e1f20e4cdec2ec5e061922dcbf1feae28b` |
| `queue_linkage.csv` | 682 | `7aed62bcab3493c87293204297ee536de2adfeb643f948e15c8e400ec534a8f2` |

The derived files remain local under
`data/manual/full_corpus_exception_packets/exception-packet-b4c076afb79f`; the committed generator,
tests, and this release record reproduce them from the protected first-pass workspace.

## Workload de-duplication

| Queue membership | Unique FIA documents |
|---|---:|
| Exclusion QA only | 482 |
| Document and adjudication exception | 92 |
| Document, adjudication, and exclusion QA | 4 |
| Document-only recalled label | 4 |
| **Total unique investigations** | **582** |

The linkage preserves 100 document rows, 96 adjudication rows, and 486 QA rows. Collapsing them by
`document_id` removes 100 duplicate source reviews without removing any review obligation.

## Priority and evidence

| Priority bucket | Investigations |
|---|---:|
| Unresolved recalled version | 4 |
| Analytical-scope conflict | 18 |
| Parser or multi-decision format | 17 |
| Manual session/offence scope | 61 |
| Exclusion quality control | 482 |

| Evidence status | Investigations |
|---|---:|
| Full standard Fact/Infringement/Decision/Reason sections | 484 |
| Partial sections | 30 |
| Linked source without core labeled sections | 64 |
| Archive label only | 4 |

Each investigation carries the official FIA URL, source metadata, queue memberships and row IDs,
root causes, review priority, driver/outcome suggestions, available source text, missing-section
flags, review questions, and a proposed next action. The packet never fills an editable review
field.

## First bounded source diagnostic

The 18 analytical-scope conflicts all have full source sections and were inspected as a diagnostic
batch:

- Eight 2019 Italian track-limit decisions describe leaving Turn 11 and gaining a lasting advantage.
  Seven occurred in Practice 3 and one in Qualifying; none alleges qualifying impeding. Their
  out-of-scope suggestions are supported by the frozen session/offence design.
- Eight qualifying pit-exit/slow-driving cases from 2019 Bahrain, 2023 Singapore, Mexico, and São
  Paulo explicitly allege impeding and support the secondary qualifying population. Their competing
  slow-driving/race-direction language is context, not a reason to remove the impeding allegation.
- The 2025 Dutch pit-entry case occurred in Practice and supports session exclusion despite an
  explicit impeding finding.
- The 2025 Abu Dhabi garage-release collision occurred in Practice and imposed a team fine while
  stating that no fault was attributable to the driver; it supports session exclusion and requires
  no driver-fault inference.

These are disclosed machine-assisted first-pass diagnostics, not reconciled codes. The 18 worklist
rows remain unstarted until their final fields are recorded and independently reviewed.

## Parser-format triage

The initial parser/multi-decision bucket contained 224 sources. Source-family and warning-pattern
inspection showed that 207 were already deterministically outside the frozen collision,
forcing-off-track, gaining-advantage, moving-under-braking, and qualifying-impeding populations.
Most were bulk deleted-lap-time notices, administrative permissions, protest/governance decisions,
or other strict-liability procedures that legitimately omit one or more modern section headings.

First-pass schema v3 routes those 207 sources to disclosed pending-human exclusions without
clearing their parser warnings or their sampled QA obligations. It never routes a warning-bearing
source to inclusion. The remaining 17 are the useful investigation set: 15 nonstandard legacy
administrative decisions with unresolved session labels, the 2021 São Paulo permission for Car 44
to start Sprint Qualifying, and the 2025 Hungarian no-further-action decision concerning alleged
forcing off track. Their official text has been recovered and inspected, but their worklist final
fields remain unstarted pending recorded source disposition and independent review.

## Interpretation boundary

The packet is an operational review control. It does not recover the four recalled Belgian source
binaries, confirm any of the 486 proposed exclusions, resolve multi-driver splits, or authorize
consistency, nationality, competitive-impact, proportionality, or fairness findings. A reviewer must
still record dispositions in the protected workspace and pass reconciliation and analytical-release
controls.
