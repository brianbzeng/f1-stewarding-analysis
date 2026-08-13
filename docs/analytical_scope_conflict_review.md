# Analytical-Scope Conflict Review

Status: all 18 cross-family/session conflicts are source-coded; independent review remains pending.

## Release identity

The versioned ledger is
`data/manual/review_ledgers/analytical_scope_conflicts_v1.json`, SHA-256
`7e293a52b46b2a93714bbd25b5dc66865c29def3a34df4eabfaf2d1d6b6b3283`.
It is locked to the preceding parser-review workspace SHA-256
`c938b2d25c28493b6593a29156a44c17822a1a68f79342a4ed30b64a92e431d9`.
Applying it produces workspace SHA-256
`c7d62651b6eb7646b1682e616e32666620cdbc6f8a1d3a451d3da9e4d8ceb7ae`.

Reproduce this review round with:

```powershell
f1stewards apply-full-corpus-review-ledger `
  data/manual/full_corpus_review_edits/full-coding-e0192ecbd9e4 `
  data/manual/review_ledgers/analytical_scope_conflicts_v1.json `
  --output-root data/manual/full_corpus_review_rounds/scope_conflicts
```

The resulting workspace passes all 19 protected-lineage and editable-field controls. As with the
preceding ledger, every disposition is `single_coded_pending_human` and contributes no independent
review credit.

## Source-supported results

| Conflict group | Sources | Final coding |
|---|---:|---|
| Qualifying pit-exit/slow-driving cases | 8 | Include as secondary qualifying impeding |
| 2019 Italy Practice 3 track limits | 7 | Exclude: out-of-scope session or superseded version |
| 2019 Italy Qualifying track limits | 1 | Exclude: secondary scope is impeding only |
| 2025 Dutch Practice impeding | 1 | Exclude: out-of-scope session |
| 2025 Abu Dhabi Practice garage release | 1 | Exclude: out-of-scope session and pit-lane procedure |
| **Total** | **18** | **8 secondary inclusions; 10 exclusions** |

The eight secondary inclusions are one 2019 Bahrain case, one 2023 Singapore case, three 2023
Mexico cases, and three 2023 São Paulo cases. The source allegations/findings all concern cars
being unable to proceed normally at the Qualifying pit exit. Procedural slow-driving or Race
Director instruction language explains the mechanism; it does not erase the impeding adjudication.
The Mexico decisions are retained despite no further action because the study denominator includes
official no-action findings.

## Italian version and session controls

Seven Italian records explicitly state Practice 3 and therefore cannot enter the Race/Sprint
primary population. The corrected Car 26 Document 29 is retained as effective; earlier Document 27
is coded superseded because both sources identify Car 26, incident time 12:58, the same Turn 11
fact, and the same deleted lap time, while Document 29 is the later corrected decision. Both remain
in provenance.

The two Car 23 records are not duplicates. Document 24 identifies a 12:30 Practice 3 incident;
Document 30 identifies a distinct 15:11 Qualifying incident. The latter is still excluded because
the frozen secondary population is limited to Qualifying impeding, not track-limit lap deletion.

## Practice conflicts

The 2025 Dutch source explicitly finds Car 63 impeded Car 14, but the incident occurred in Practice;
the team received a fine and the driver a warning. The 2025 Abu Dhabi source adjudicates an unsafe
garage release that caused contact and damage in Practice, fines the team, and expressly states
that no fault was attributable to Car 12's driver. The final family is `pit_lane_procedure`, while
the collision remains visible in protected Fact/Reason evidence for any separate harm audit.

## Analytical boundary

After this round, the chained workspace contains 1,938 document and 1,891 adjudication rows marked
`single_coded_pending_human`, leaving 65 and 61 respectively unstarted; all 486 exclusion-QA rows
remain unstarted. Feature build `features-99c7c3429c01` still has 296 provisional primary rows, 580
driver-role rows, zero reporting-eligible rows, and release status
`blocked_pending_human_review`.
