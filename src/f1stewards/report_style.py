"""Style controls for the public portfolio report."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

FORBIDDEN_TERMS = (
    "as we navigate",
    "beacon",
    "comprehensive",
    "delve",
    "dynamic",
    "it is important to note",
    "multifaceted",
    "revolutionize",
    "tapestry",
    "testament",
)
FORBIDDEN_DASHES = (chr(0x2013), chr(0x2014))
SENTENCE_END = re.compile(r"[.!?](?:[\"')\]]*)?(?=\s|$)")


def _clean_text(node: object) -> str:
    get_text = node.get_text  # type: ignore[attr-defined]
    return " ".join(get_text(" ", strip=True).split())


def _sentence_count(text: str) -> int:
    return len(SENTENCE_END.findall(text))


def audit_report_style(report_path: Path) -> list[str]:
    """Return all detected style-rule violations."""

    soup = BeautifulSoup(report_path.read_text(encoding="utf-8"), "html.parser")
    for node in soup(["script", "style", "pre", "code"]):
        node.decompose()

    visible_text = _clean_text(soup)
    visible_lower = visible_text.casefold()
    violations: list[str] = []

    for dash in FORBIDDEN_DASHES:
        if dash in visible_text:
            violations.append(f"forbidden dash U+{ord(dash):04X} appears in visible text")
    for term in FORBIDDEN_TERMS:
        if re.search(rf"\b{re.escape(term)}\b", visible_lower):
            violations.append(f"forbidden term appears in visible text: {term}")

    title = _clean_text(soup.title) if soup.title else ""
    if any(dash in title for dash in FORBIDDEN_DASHES):
        violations.append("forbidden dash appears in the HTML title")

    for image in soup.find_all("img"):
        alt_text = str(image.get("alt", ""))
        if any(dash in alt_text for dash in FORBIDDEN_DASHES):
            violations.append(f"forbidden dash appears in image alt text: {alt_text[:100]}")

    checked_nodes = list(soup.find_all("p"))
    checked_nodes.extend(soup.select("div.report-answer, div.report-note, div.report-method"))
    for node in checked_nodes:
        text = _clean_text(node)
        if not text:
            continue
        sentence_count = _sentence_count(text)
        if sentence_count > 2:
            violations.append(f"paragraph has {sentence_count} sentences: {text[:160]}")
        if len(text.split()) > 80:
            violations.append(f"paragraph has {len(text.split())} words: {text[:160]}")

    for node in soup.find_all("li"):
        text = _clean_text(node)
        sentence_count = _sentence_count(text)
        if sentence_count > 1:
            violations.append(f"list item has {sentence_count} sentences: {text[:160]}")
        if len(text.split()) > 45:
            violations.append(f"list item has {len(text.split())} words: {text[:160]}")

    return violations
