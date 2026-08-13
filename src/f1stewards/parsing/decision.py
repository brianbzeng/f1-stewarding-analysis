"""Conservative text extraction for FIA decision PDFs."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from f1stewards.models import DecisionSections, DocumentClass

SECTION_RE = re.compile(
    r"(?m)^\s*(FACT|Fact|OFFENCE|Offence|INFRINGEMENT|Infringement|"
    r"INFRINGMENT|Infringment|DECISION|Decision|REASON(?:S)?|Reason(?:s)?)\b"
    r"[ \t]*(?:[:\-][ \t]*)?"
)
FOOTER_RE = re.compile(
    r"(?im)^\s*(?:Competitors are reminded|Decisions of the Stewards are taken independently|"
    r"The Stewards\s*$)"
)
SECTION_FIELDS = {
    "FACT": "fact_text",
    "OFFENCE": "infringement_text",
    "INFRINGEMENT": "infringement_text",
    "INFRINGMENT": "infringement_text",
    "DECISION": "decision_text",
    "REASON": "reason_text",
    "REASONS": "reason_text",
}
DRIVER_RE = re.compile(r"(?im)^\s*No\s*/\s*Driver\s+(\d+)\s*-\s*(.+?)\s*$")
SESSION_RE = re.compile(r"(?im)^\s*Session\s+(.+?)\s*$")
TIME_RE = re.compile(r"(?im)^\s*Time\s+(\d{1,2}:\d{2})\s*$")
SUMMONS_LANGUAGE_RE = re.compile(
    r"(?is)\b(?:is|are)\s+required\s+to\s+report\s+to\s+the\s+Stewards\b"
)
RACE_DIRECTOR_ISSUER_RE = re.compile(
    r"(?is)^\s*From\s+The\s+FIA\s+Formula\s+One\s+Race\s+Director\b"
)
TECHNICAL_DELEGATE_ISSUER_RE = re.compile(
    r"(?is)^\s*From\s+The\s+FIA\s+Formula\s+One\s+Technical\s+Delegate\b"
)


def normalize_pdf_text(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_sections(text: str) -> dict[str, str]:
    matches = list(SECTION_RE.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        field = SECTION_FIELDS[match.group(1).upper()]
        value = text[start:end].strip()
        if field == "reason_text":
            value = FOOTER_RE.split(value, maxsplit=1)[0].strip()
        if value:
            sections[field] = value
    return sections


def parse_header_fields(text: str) -> dict[str, str | int]:
    fields: dict[str, str | int] = {}
    driver = DRIVER_RE.search(text)
    if driver:
        fields["driver_number"] = int(driver.group(1))
        fields["driver_name"] = driver.group(2).strip()
    session = SESSION_RE.search(text)
    if session:
        fields["session_type"] = session.group(1).strip()
    times = TIME_RE.findall(text)
    if times:
        # The document timestamp appears first; the adjudicated incident time appears last.
        fields["incident_time_raw"] = times[-1]
    return fields


def infer_content_document_class(text: str) -> tuple[DocumentClass | None, str]:
    """Type a retrieved steward-labelled PDF without erasing its archive classification."""

    if not text.strip():
        return None, "empty_text_no_content_classification"
    if RACE_DIRECTOR_ISSUER_RE.search(text):
        return DocumentClass.RACE_DIRECTOR_NOTES, "issuer_race_director"
    if TECHNICAL_DELEGATE_ISSUER_RE.search(text):
        return DocumentClass.OTHER, "issuer_technical_delegate"
    if SUMMONS_LANGUAGE_RE.search(text):
        return DocumentClass.SUMMONS, "required_to_report_to_stewards"
    return DocumentClass.STEWARD_DECISION, "steward_document_fallback"


def parse_decision_pdf(path: Path, document_id: str) -> DecisionSections:
    reader = PdfReader(path)
    page_text = [page.extract_text() or "" for page in reader.pages]
    raw_text = normalize_pdf_text("\n\n".join(page_text))
    sections = split_sections(raw_text)
    header_fields = parse_header_fields(raw_text)
    content_document_class, content_classification_basis = infer_content_document_class(raw_text)
    warnings: list[str] = []
    if not raw_text:
        warnings.append("no_text_extracted")
    if content_document_class == DocumentClass.STEWARD_DECISION:
        for expected in ("fact_text", "decision_text", "reason_text"):
            if expected not in sections:
                warnings.append(f"missing_{expected}")
    return DecisionSections(
        document_id=document_id,
        page_count=len(reader.pages),
        raw_text=raw_text,
        content_document_class=content_document_class,
        content_classification_basis=content_classification_basis,
        parser_warnings=warnings,
        **header_fields,
        **sections,
    )
