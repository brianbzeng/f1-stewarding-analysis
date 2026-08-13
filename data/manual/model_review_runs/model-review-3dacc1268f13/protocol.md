# GPT-5.6 Sol Full-Corpus Review Protocol

Status: approved model-review protocol. It does not claim independent human review.

## Purpose

The original release gate required 4,441 independent human actions. Those actions represent 2,003
unique FIA source records: 2,003 document dispositions, 1,952 adjudication codings linked to those
documents, and 486 exclusion checks sampled from the same document population. This protocol uses
GPT-5.6 Sol to complete a disclosed second review of the full local record set while retaining human
review as a separate and unfinished assurance tier. It uses extracted FIA evidence, cross-field
checks, targeted source inspection, and deterministic reconciliation. It does not claim that the
model independently re-read every original PDF line by line.

## Review rules

1. Preserve the protected source columns, workspace identity, and first-pass coding unchanged.
2. Write the model-reviewed rows to a separate content-addressed workspace.
3. Check every queue obligation and preserve one audit row for each of the 4,441 obligations.
4. Treat the official FIA decision text as authoritative for the outcome and sanction.
5. Code written responsibility only from the reason text. Do not infer fault severity from the
   size of a penalty. Use `no_conclusion` when the decision does not state a controlled degree of
   responsibility; this does not mean no fault was found.
6. Confirm exclusion-QA rows only when the linked, source-coded document remains outside the frozen
   study scope. Any false exclusion blocks release and requires a rule audit.
7. Keep missing evidence visible. A recalled record whose binary is unavailable may receive only a
   metadata-supported version disposition, never an imputed incident outcome.
8. Record every agreement and correction with the source-record hash, prior value, final value,
   rationale, reviewer/model identifier, and model-review status.
9. Leave ambiguous analytical inclusions unresolved rather than guess. Any unresolved inclusion
   blocks the model-reviewed release.
10. Run protected-lineage, completeness, identity, panel, outcome-mapping, grouped-validation, and
    automated test controls before using a model-reviewed finding.

## Assurance labels

- `model_reviewed_agree`: GPT-5.6 Sol agreed with the source-coded first pass.
- `model_reviewed_corrected`: GPT-5.6 Sol changed one or more final fields and recorded the change.
- `source_unavailable_model_review`: the model checked an archive-metadata disposition because the
  source binary was unavailable. This status cannot be used for an analytical inclusion.
- `model_review_unresolved`: evidence was insufficient. These rows cannot enter a released model
  population.

Model-reviewed analytical rows use `model_reviewed_final` and a release status of
`reportable_model_reviewed`. The labels `double_coded`, `adjudicated`, `human_reviewed_final`, and
`reportable_human_reviewed` remain reserved for genuine human review.

## Required disclosure

Any report using this tier must state the model name, run ID, coverage, corrections, unavailable
sources, and the fact that independent human review was not performed. Model review reduces manual
work and catches structured inconsistencies, but correlated errors remain possible because Codex
also assisted with the first pass.
