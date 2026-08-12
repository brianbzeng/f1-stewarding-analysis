# Feasibility Pilot

## Events

### 2019 Austrian Grand Prix

Purpose:

- pre-driving-guideline era;
- older naming and PDF format;
- paired decisions from the same incident;
- no-further-action outcome;
- classification and summons linkage.

### 2023 Abu Dhabi Grand Prix

Purpose:

- modern but pre-public-guideline structure;
- penalty and no-action outcomes;
- race and qualifying documents;
- Race Director event notes;
- multiple decision families on one weekend.

### 2025 Austrian Grand Prix

Purpose:

- public penalty/driving-guideline era;
- recalled and replacement documents;
- several comparable on-track allegations;
- guideline-conformance fields;
- multiple potential competitive-impact calculations.

These events test the pipeline. They are not selected as evidence for the final conclusions.

## Required pilot outputs

1. Event-page source manifest with titles, URLs, document classes, and retrieval time.
2. SHA-256 hash and local path for every downloaded pilot document.
3. Extracted text and structured fields for relevant steward decisions.
4. Explicit penalty/no-action classification.
5. Recalled/corrected document lineage.
6. Discovery of final classification and championship points.
7. Initial mapping to applicable regulation and guideline regime.
8. FastF1 session availability and join diagnostic.
9. Manual-review rate and unresolved parsing exceptions.

## Pass criteria

- 100% of relevant visible event-page documents are represented in the manifest.
- At least 95% of downloaded PDFs extract non-empty text without OCR.
- Fact, decision, and reason are parsed or visibly flagged for manual review.
- No-action decisions remain explicit values.
- No recalled document is treated as final.
- Final classifications are discoverable for all three events.
- FastF1 identifies the correct race session for all three events.
- Every analytical pilot row has an official source URL.

## Stop/revise criteria

Revise the pipeline before full collection if:

- the FIA page requires an undocumented API or browser rendering that the collector cannot reproduce;
- corrected-document lineage cannot be reconstructed reliably;
- more than 25% of primary decisions require full manual transcription;
- event or driver joins rely on ambiguous fuzzy matches;
- the expected number of comparable driving adjudications is too small for adjusted nationality models.
