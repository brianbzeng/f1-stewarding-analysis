# Parser-Format Source Review

Status: all 17 remaining parser/nonstandard-format investigations are source-coded;
independent review remains pending.

## Release identity

The versioned review ledger is
`data/manual/review_ledgers/parser_format_triage_v1.json`, SHA-256
`913c3f2e7d2f0ac1512d9d66d2b5e43458ea0ef9789534b29b3e441e65c1aba7`.
It is locked to machine-assisted workspace SHA-256
`de816c98622f6b429529041ad616fe706cbfdf17e82d169d598aff45b6e7bca9`.
Applying it produces edited-workspace SHA-256
`c938b2d25c28493b6593a29156a44c17822a1a68f79342a4ed30b64a92e431d9`.

Reproduce the source-reviewed layer with:

```powershell
f1stewards apply-full-corpus-review-ledger `
  data/manual/full_corpus_first_pass/full-coding-e0192ecbd9e4 `
  data/manual/review_ledgers/parser_format_triage_v1.json
```

The command writes `data/manual/full_corpus_review_edits/full-coding-e0192ecbd9e4`
and passes all 19 protected-lineage and editable-workspace controls. The ledger changes only final
fields; every source field, FIA URL, parser warning, seed identity, and timing field remains
protected.

## Dispositions

| Source-supported disposition | Documents | Analytical result |
|---|---:|---|
| Start or grid permission | 10 | Exclude |
| Technical/scrutineering administration | 2 | Exclude |
| Event personnel or session administration | 3 | Exclude |
| Protest/governance decision | 1 | Exclude |
| Alleged forcing off track | 1 | Include as primary no further action |
| **Total** | **17** | **16 exclusions; 1 inclusion** |

The ten permission sources include legacy approvals to start after no qualifying time, grid or
pit-lane placement after qualifying disqualification, and Lewis Hamilton's permission to start the
2021 São Paulo Sprint Qualifying session. These decisions affect participation or starting order;
they do not adjudicate an alleged collision, forcing off track, gaining an advantage off track,
moving under braking, or qualifying impeding.

The other exclusions cover survival-cell re-scrutineering, a Mercedes technical-compliance ruling,
a Renault technical protest against Haas, a Practice 1 driver-lineup request, replacement of the
Deputy Medical Delegate, and cancellation of Practice 3 for weather. The 2018 British document
combining re-scrutineering and pit-lane start permission does not require two analytical rows:
neither matter has an accused driver or enters an in-scope incident population, and both receive
the same controlled exclusion.

## Hungarian inclusion

The 2025 Hungarian decision `fia-2025-hun-f1ff0743742b` is retained because the study denominator
includes official no-action adjudications, not only findings of an offence. The final source-coded
fields are:

| Field | Coded value |
|---|---|
| Accused / affected | Car 1 Max Verstappen / Car 44 Lewis Hamilton |
| Session | Race |
| Lap / location | Lap 29 / Turn 4 |
| Incident family | `forcing_off_track` |
| Outcome | `no_further_action` |
| Written responsibility | `no_conclusion` |

The FIA reason states that there was no contact, Hamilton chose not to remain on track, and the
incident did not qualify as forcing another car off track. FastF1 independently supports the event
location in time: its race-control feed records Car 44's Turn 4 lap-time deletion at 15:42:56 on
lap 29, matching the decision's 15:42 incident time, while both drivers' lap table begins lap 29 at
approximately 15:42 local time. This timing link locates the adjudication; it does not override the
stewards' no-action finding or infer competitive harm.

## Analytical boundary

All 34 edited worklist rows use reviewer/coder `codex_source_review_v1` and status
`single_coded_pending_human`. They therefore remain incomplete for reporting and do not count as
independent agreement. Feature build `features-8f34710dfddc` retains all 296 primary candidates as
`incomplete_human_coding`, has zero reporting-eligible rows, and keeps the analytical release
blocked. The next reviewer must confirm or disagree with the ledger rather than treating its
source-supported dispositions as final findings.
