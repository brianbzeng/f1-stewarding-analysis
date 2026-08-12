# Manual Coding Workflow

The coding queue is generated from parsed official FIA documents; analysts do not select
interesting decisions from memory. One row represents one **document version**, not necessarily
one final adjudication. Recalled, corrected, and superseding documents stay visible.

## Workflow

1. Run `f1stewards build-coding-queue` after acquisition and parsing.
2. Confirm `incident_group_id` using the fact, event time, lap/turn, and counterparties.
3. Label each document `initial`, `recalled`, `corrected`, `reviewed`, or `final` and link its
   predecessor in `supersedes_document_id`.
4. Confirm or replace the machine-suggested incident and outcome families.
5. Record context only when supported by the official decision, timing data, or a documented
   manual evidence review. Do not infer missing facts from the sanction.
6. Complete `include_primary` and provide an exclusion reason for every excluded row.
7. A second pass reviews incident grouping, outcome, contextual fields, guideline conformance,
   and any record used in a highlighted case study.

Blank cells mean “not yet coded,” not “no.” Boolean fields use `true`, `false`, or `unclear`.

## Version control policy

The small coding CSV is committed because it is analytical input and a record of human judgment.
Raw PDFs, extracted full text, telemetry, and generated databases remain ignored. The queue contains
only short Fact/Decision fields, stable identifiers, and official source URLs.
