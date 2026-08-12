"""Conservative text extraction for FIA decision PDFs."""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from f1stewards.models import DecisionSections

SECTION_RE = re.compile(
    r"(?im)^\s*(FACT|OFFENCE|INFRINGEMENT|DECISION|REASON(?:S)?)\b[ \t]*(?:[:\-][ \t]*)?"
)
FOOTER_RE = re.compile(
    r"(?im)^\s*(?:Competitors are reminded|Decisions of the Stewards are taken independently|"
    r"The Stewards\s*$)"
)
SECTION_FIELDS = {
    "FACT": "fact_text",
    "OFFENCE": "infringement_text",
    "INFRINGEMENT": "infringement_text",
    "DECISION": "decision_text",
    "REASON": "reason_text",
    "REASONS": "reason_text",
}
DRIVER_RE = re.compile(r"(?im)^\s*No\s*/\s*Driver\s+(\d+)\s*-\s*(.+?)\s*$")
SESSION_RE = re.compile(r"(?im)^\s*Session\s+(.+?)\s*$")
TIME_RE = re.compile(r"(?im)^\s*Time\s+(\d{1,2}:\d{2})\s*$")


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


def parse_decision_pdf(path: Path, document_id: str) -> DecisionSections:
    reader = PdfReader(path)
    page_text = [page.extract_text() or "" for page in reader.pages]
    raw_text = normalize_pdf_text("\n\n".join(page_text))
    sections = split_sections(raw_text)
    header_fields = parse_header_fields(raw_text)
    warnings: list[str] = []
    if not raw_text:
        warnings.append("no_text_extracted")
    for expected in ("fact_text", "decision_text", "reason_text"):
        if expected not in sections:
            warnings.append(f"missing_{expected}")
    return DecisionSections(
        document_id=document_id,
        page_count=len(reader.pages),
        raw_text=raw_text,
        parser_warnings=warnings,
        **header_fields,
        **sections,
    )
