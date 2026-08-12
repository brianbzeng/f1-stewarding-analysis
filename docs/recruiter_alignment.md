# HHS OIG Recruiter Alignment

The project is an F1 domain analysis, but its delivery is tailored to the HHS OIG Office of the Chief Data Officer's published work patterns.

## Evaluated competency evidence

| Competency | Repository evidence |
|---|---|
| Customer Service | Planned user stories, evidence-explorer acceptance criteria, plain-language guide, and documented usability feedback |
| Data Analysis | Implemented pilot EDA and tiered impact arithmetic; planned calibrated models, adjusted associations, and sensitivity analysis |
| Data Extraction and Transformation | Implemented versioned FIA PDF/web ingestion, FastF1 enrichment, normalized DuckDB model, and SQL quality checks |
| Technology Application | Implemented Python package, executed Jupyter notebooks, DuckDB, Parquet, Git, tests, and CI; optional Snowflake deployment follows model freeze |

## Duty alignment

- Queries, models, charts, and tables are delivered with interpretation notes.
- Anomaly scores prioritize evidence for human review rather than determine wrongdoing.
- The evidence explorer is a self-service product whose filter logic is tested against SQL reference queries.
- The report has an executive brief, analytical narrative, and technical appendix for different audiences.
- Source provenance, data integrity, and rule versioning make every finding auditable.
- Requirements and acceptance criteria link user needs to application behavior.

## GS-12 portfolio signals already visible

- The command-line workflow is restartable and distinguishes acquisition, parsing, enrichment,
  validation, and audit operations.
- Pydantic contracts reject invalid adjudication and impact combinations at the analytical boundary.
- Twelve zero-row SQL controls compensate for DuckDB's cross-schema foreign-key limitation and catch
  missing lineage, impossible values, incomplete mechanical arithmetic, and invalid rule windows.
- Event-date rule versions are data, not prose-only citations; an archive-link drift is represented as
  a controlled source exception.
- A 65-issue regulation catalog, event-date SQL selector, and measured scale-readiness command turn
  research governance into reproducible application behavior.
- The executed notebooks lead with scope, evidence status, and interpretation instead of presenting
  charts without decision context.
- Competitive impact separates exact arithmetic from strategy-dependent speculation.

## Honest qualification boundary

This project supports technical and communication competencies. It does not replace the announcement's required duration of healthcare-data experience or establish senior organizational leadership. Those claims must come from genuine paid, unpaid, or volunteer experience.
