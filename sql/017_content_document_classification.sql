ALTER TABLE raw.document_text
    ADD COLUMN IF NOT EXISTS content_document_class VARCHAR;

ALTER TABLE raw.document_text
    ADD COLUMN IF NOT EXISTS content_classification_basis VARCHAR;

CREATE OR REPLACE VIEW analysis.v_source_documents_typed AS
SELECT
    d.*,
    t.content_document_class,
    t.content_classification_basis,
    coalesce(t.content_document_class, d.document_class) AS effective_document_class
FROM raw.source_documents AS d
LEFT JOIN raw.document_text AS t USING (document_id);
