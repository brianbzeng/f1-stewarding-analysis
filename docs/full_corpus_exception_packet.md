# Full-Corpus Exception Investigation Packet

Status: content-addressed investigation packet generated; source review and independent disposition
remain pending.

## Purpose

The first-pass worklists contain 1,096 deliberately unstarted queue rows, but many refer to the same
official FIA decision. The exception packet makes the source document—not a duplicated spreadsheet
row—the investigation unit. It preserves every queue ID in a linkage table so no denominator or QA
obligation disappears.

Generate or byte-verify it with:

```powershell
f1stewards build-full-corpus-exception-packet `
  data/manual/full_corpus_first_pass/full-coding-e0192ecbd9e4
```

The current packet is `exception-packet-e59c0de45246`, schema
`full-corpus-exception-packet-v1`, derived from `first-pass-29113bebd312` and workspace SHA-256
`17188e95a22bdfcad8c4dac9985cbe4c3babc494734e2348811748a1e7ab9b09`.

| Output | Rows | SHA-256 |
|---|---:|---|
| `investigation_queue.csv` | 712 | `a9ddb375dfeacaca9af8fe23dbce595d27c35c10c2a772b2cd26b37882ead7ab` |
| `queue_linkage.csv` | 1,096 | `1c59ba0a7f88084cf51e3ec6aab7a23a5244d75bfd7eb3216464168779e924f8` |

The derived files remain local under
`data/manual/full_corpus_exception_packets/exception-packet-e59c0de45246`; the committed generator,
tests, and this release record reproduce them from the protected first-pass workspace.

## Workload de-duplication

| Queue membership | Unique FIA documents |
|---|---:|
| Exclusion QA only | 405 |
| Document and adjudication exception | 222 |
| Document, adjudication, and exclusion QA | 81 |
| Document-only recalled label | 4 |
| **Total unique investigations** | **712** |

The linkage preserves 307 document rows, 303 adjudication rows, and 486 QA rows. Collapsing them by
`document_id` removes 384 duplicate source reviews without removing any review obligation.

## Priority and evidence

| Priority bucket | Investigations |
|---|---:|
| Unresolved recalled version | 4 |
| Analytical-scope conflict | 18 |
| Parser or multi-decision format | 224 |
| Manual session/offence scope | 61 |
| Exclusion quality control | 405 |

| Evidence status | Investigations |
|---|---:|
| Full standard Fact/Infringement/Decision/Reason sections | 484 |
| Partial sections | 105 |
| Linked source without core labeled sections | 119 |
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

## Interpretation boundary

The packet is an operational review control. It does not recover the four recalled Belgian source
binaries, confirm any of the 486 proposed exclusions, resolve multi-driver splits, or authorize
consistency, nationality, competitive-impact, proportionality, or fairness findings. A reviewer must
still record dispositions in the protected workspace and pass reconciliation and analytical-release
controls.
