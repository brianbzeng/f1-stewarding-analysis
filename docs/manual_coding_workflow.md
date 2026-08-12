# Manual Coding Workflow

The coding queue is generated from parsed official FIA documents; analysts do not select
interesting decisions from memory. One queue row represents one **document version**, not
necessarily one final adjudication. Recalled, corrected, and superseding documents stay visible.

Three files have different purposes:

| File | Meaning |
|---|---|
| `pilot_coding_queue.csv` | machine-generated document-version review queue |
| `pilot_coded_adjudications.csv` | one provisional analytical row per accused driver |
| `pilot_impact_assessments.csv` | one tiered assessment per sanction with a possible competitive effect |

The current coded files are an AI-assisted first pass by `codex_initial_v1`. They are not described
as human-reviewed data. `review_status=single_coded_pending_human` blocks publication of substantive
pilot findings and full-scale collection.

## Workflow

1. Run `f1stewards build-coding-queue` after acquisition, parsing, and FastF1 enrichment.
2. Confirm `incident_group_id` using the fact, event time, lap/turn, and counterparties.
3. Label each document `initial`, `recalled`, `corrected`, `reviewed`, or `final` and link its
   predecessor in `supersedes_document_id`.
4. Confirm or replace the machine-suggested incident and outcome families.
5. Record context only when supported by the official decision, timing data, or a documented
   manual evidence review. Do not infer missing facts from the sanction.
6. Complete `include_primary` and provide an exclusion reason for every excluded row.
7. Run `f1stewards validate-coding` and `f1stewards validate-impact`; validation is necessary but
   does not replace judgment review.
8. An independent person reviews incident grouping, outcome, contextual fields, guideline
   conformance, and every record used in a highlighted case study. Record disagreements rather than
   silently overwriting the first pass.
9. Only after reconciliation should `review_status` become `double_coded` or `adjudicated`.

Blank cells mean “not yet coded,” not “no.” Boolean fields use `true`, `false`, or `unclear`.

## Impact review rule

`mechanical` is reserved for a penalty added after racing where official time can be removed and
same-lap finishers re-ranked. A penalty served during the race changes pit timing, traffic, tyres,
and strategy; a future grid penalty changes a different event. Those cases remain `bounded`,
`modeled`, or `not_estimable` unless an explicit method is validated.

## Version control policy

The small coding CSVs are committed because they are analytical inputs and records of reviewable
judgment. Raw PDFs, extracted full text, telemetry, and generated databases remain ignored. The
queue contains only short Fact/Decision fields, stable identifiers, and official source URLs.
