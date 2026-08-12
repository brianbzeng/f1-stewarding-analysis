# Pilot Reconciliation Workflow

## Purpose

Reconciliation creates a new analytical version after independent review. It never edits the
AI-assisted first-pass CSVs or the reviewer’s original decisions. The result is a content-addressed
directory whose identity is derived from SHA-256 hashes of all three inputs.

## Preconditions

- `f1stewards review-status` reports 13/13 complete.
- Every review decision is `agree` or `correct`.
- No row remains `pending` or `needs_discussion`.
- Every correction contains evidence notes and a non-empty JSON object.

## Command

```powershell
f1stewards reconcile-pilot
```

The command validates target coverage, applies permitted corrections in memory, validates the full
result against the Pydantic adjudication or impact contract, and then writes:

```text
data/manual/reconciled/pilot-<input digest>/
  adjudications.csv
  impact_assessments.csv
  reconciliation_audit.csv
  manifest.json
```

Identical inputs resolve to the same directory and bytes. A repeat run verifies the existing files.
It never overwrites a mismatch; any changed or missing artifact is treated as possible tampering.

## Correction rules

The reviewer may correct substantive analytical fields, including incident grouping, drivers,
context, outcome, sanction, conformance, and impact arithmetic. The corrected whole record must
still pass every impossible-combination rule.

The patch cannot change record identity, event/source lineage, initial coder identity, or
`review_status`. If one of those is wrong, stop and document a structural adjudication instead of
forcing it through a field patch. The reconciliation process itself sets the new copies to
`double_coded`.

A `correct` decision must change at least one value. Listing a field whose value is unchanged is an
error because it creates a misleading audit history.

## Audit and lineage

`reconciliation_audit.csv` records one row per corrected field plus the status transition for every
target. Each row retains review ID, target ID/type, initial and reconciled JSON values, reviewer,
timestamp, notes, and evidence URLs.

`manifest.json` records:

- reconciliation and schema/method versions;
- hashes for the adjudication, impact, and review inputs;
- hashes for all three output tables;
- reviewer IDs, decision counts, record counts, and correction count;
- the latest recorded review timestamp as the deterministic reconciliation timestamp.

## Post-reconciliation checks

Use the paths printed by the command:

```powershell
f1stewards validate-coding --coding-path <directory>\adjudications.csv
f1stewards validate-impact --coding-path <directory>\adjudications.csv `
  --impact-path <directory>\impact_assessments.csv
f1stewards scale-readiness --coding-path <directory>\adjudications.csv `
  --impact-path <directory>\impact_assessments.csv
f1stewards build-explorer --coding-path <directory>\adjudications.csv `
  --impact-path <directory>\impact_assessments.csv
```

The go/no-go decision for full collection remains human. Reconciliation proves review completion and
data lineage; it does not decide whether pilot yield and measured review burden justify scaling.
