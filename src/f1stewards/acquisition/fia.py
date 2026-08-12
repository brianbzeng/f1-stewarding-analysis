"""Respectful discovery and retrieval from FIA document archive pages."""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from f1stewards.models import DocumentClass, PilotEvent, SourceDocument

PUBLISHED_RE = re.compile(r"\s*Published\s+on\s+(.+?)\s*$", flags=re.IGNORECASE)
PDF_SUFFIX_RE = re.compile(r"\.pdf(?:$|[?#])", flags=re.IGNORECASE)
RECALLED_RE = re.compile(
    r"(Recalled\s*-\s*Doc\s+(\d+)\s*-\s*.*?)\s+Published\s+on\s+"
    r"(\d{2}\.\d{2}\.\d{2}\s+\d{2}:\d{2}\s+C(?:ET|EST))",
    flags=re.IGNORECASE,
)
DEFAULT_USER_AGENT = "f1-stewards-research/0.1 (portfolio research; low-rate requests)"


def sanitize_transport_url(url: str) -> str:
    """Encode stray percent signs while preserving valid percent-encoded bytes."""

    return re.sub(r"%(?![0-9a-fA-F]{2})", "%25", url)


def classify_document(title: str, class_config: dict[str, dict[str, list[str]]]) -> DocumentClass:
    normalized = " ".join(title.casefold().split())
    for class_name, rules in class_config.items():
        if class_name == DocumentClass.OTHER:
            continue
        includes = rules.get("include", [])
        excludes = rules.get("exclude", [])
        if any(token.casefold() in normalized for token in includes) and not any(
            token.casefold() in normalized for token in excludes
        ):
            return DocumentClass(class_name)
    return DocumentClass.OTHER


def _parse_anchor_text(text: str) -> tuple[str, str | None, datetime | None]:
    normalized = " ".join(text.split())
    match = PUBLISHED_RE.search(normalized)
    if not match:
        return normalized, None, None
    published_raw = match.group(1).strip()
    title = normalized[: match.start()].strip()
    try:
        published_at = date_parser.parse(
            published_raw,
            dayfirst=True,
            tzinfos={"CET": 3600, "CEST": 7200},
        )
    except (ValueError, OverflowError):
        published_at = None
    return title, published_raw, published_at


def _document_id(event: PilotEvent, document_url: str) -> str:
    digest = hashlib.sha256(document_url.encode("utf-8")).hexdigest()[:12]
    return f"fia-{event.pilot_id}-{digest}"


def extract_document_links(
    html: str,
    event: PilotEvent,
    class_config: dict[str, dict[str, list[str]]],
    *,
    discovered_at: datetime | None = None,
) -> list[SourceDocument]:
    """Extract unique document records from an FIA archive HTML response."""

    soup = BeautifulSoup(html, "html.parser")
    discovered_at = discovered_at or datetime.now(UTC)
    records: list[SourceDocument] = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        title, published_raw, published_at = _parse_anchor_text(anchor.get_text(" ", strip=True))
        href = str(anchor.get("href", "")).strip()
        if not href or not title:
            continue
        # FIA document cards consistently carry a publication string. Requiring it avoids
        # misclassifying the site's global navigation as evidence.
        if published_raw is None:
            continue
        document_url = urljoin(str(event.archive_url), href)
        if urlparse(document_url).netloc.casefold() not in {"fia.com", "www.fia.com"}:
            continue
        if document_url in seen_urls:
            continue
        seen_urls.add(document_url)
        records.append(
            SourceDocument(
                document_id=_document_id(event, document_url),
                pilot_id=event.pilot_id,
                season=event.season,
                event_name=event.event_name,
                title=title,
                document_url=document_url,
                archive_url=event.archive_url,
                document_class=classify_document(title, class_config),
                published_at_raw=published_raw,
                published_at=published_at,
                discovered_at=discovered_at,
                is_recalled=title.casefold().startswith("recalled"),
            )
        )

    # Recalled files are sometimes rendered as plain text without an anchor or recoverable PDF.
    # Preserve their existence and archive status rather than silently dropping them.
    page_text = " ".join(soup.stripped_strings)
    for match in RECALLED_RE.finditer(page_text):
        title = " ".join(match.group(1).split())
        document_number = match.group(2)
        published_raw = match.group(3)
        synthetic_url = f"{event.archive_url}#recalled-doc-{document_number}"
        if synthetic_url in seen_urls:
            continue
        seen_urls.add(synthetic_url)
        try:
            published_at = date_parser.parse(
                published_raw,
                dayfirst=True,
                tzinfos={"CET": 3600, "CEST": 7200},
            )
        except (ValueError, OverflowError):
            published_at = None
        records.append(
            SourceDocument(
                document_id=_document_id(event, synthetic_url),
                pilot_id=event.pilot_id,
                season=event.season,
                event_name=event.event_name,
                title=title,
                document_url=synthetic_url,
                archive_url=event.archive_url,
                document_class=classify_document(title, class_config),
                published_at_raw=published_raw,
                published_at=published_at,
                discovered_at=discovered_at,
                is_recalled=True,
                retrieval_error="recalled_document_not_linked_by_source_archive",
            )
        )
    return records


def build_client(user_agent: str = DEFAULT_USER_AGENT) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": user_agent, "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8"},
        follow_redirects=True,
        timeout=httpx.Timeout(30.0),
    )


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    stop=stop_after_attempt(3),
    reraise=True,
)
def fetch_url(client: httpx.Client, url: str) -> httpx.Response:
    response = client.get(url)
    response.raise_for_status()
    return response


def discover_event(
    client: httpx.Client,
    event: PilotEvent,
    class_config: dict[str, dict[str, list[str]]],
) -> list[SourceDocument]:
    response = fetch_url(client, str(event.archive_url))
    return extract_document_links(response.text, event, class_config)


def _resolve_pdf_response(client: httpx.Client, document_url: str) -> httpx.Response:
    response = fetch_url(client, sanitize_transport_url(document_url))
    content_type = response.headers.get("content-type", "").casefold()
    if "application/pdf" in content_type or response.content.startswith(b"%PDF"):
        return response

    soup = BeautifulSoup(response.text, "html.parser")
    candidates: list[str] = []
    for tag, attribute in (("a", "href"), ("iframe", "src"), ("embed", "src"), ("object", "data")):
        for element in soup.find_all(tag):
            value = element.get(attribute)
            if value and PDF_SUFFIX_RE.search(str(value)):
                candidates.append(urljoin(str(response.url), str(value)))
    if not candidates:
        raise ValueError(f"No PDF target found at {document_url}")
    return fetch_url(client, candidates[0])


def _safe_filename(document: SourceDocument) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", document.title.casefold()).strip("-")[:80]
    return f"{document.document_id}-{slug}.pdf"


def download_documents(
    client: httpx.Client,
    documents: Iterable[SourceDocument],
    raw_root: Path,
    *,
    delay_seconds: float = 1.0,
) -> list[SourceDocument]:
    """Download PDFs and return updated immutable lineage records."""

    output: list[SourceDocument] = []
    for index, document in enumerate(documents):
        if index and delay_seconds > 0:
            time.sleep(delay_seconds)
        target_dir = raw_root / "fia" / str(document.season) / document.pilot_id
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            response = _resolve_pdf_response(client, str(document.document_url))
            content = response.content
            sha256 = hashlib.sha256(content).hexdigest()
            target = target_dir / _safe_filename(document)
            target.write_bytes(content)
            output.append(
                document.model_copy(
                    update={
                        "retrieved_at": datetime.now(UTC),
                        "content_sha256": sha256,
                        "local_path": target,
                        "http_status": response.status_code,
                        "content_type": response.headers.get("content-type"),
                    }
                )
            )
        except (httpx.HTTPError, ValueError, OSError) as exc:
            output.append(
                document.model_copy(
                    update={"retrieved_at": datetime.now(UTC), "retrieval_error": str(exc)}
                )
            )
    return output


def write_manifest(documents: Iterable[SourceDocument], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    incoming = pd.DataFrame([document.model_dump(mode="json") for document in documents])
    if path.exists():
        existing = pd.read_parquet(path).set_index("document_id")
        incoming = incoming.set_index("document_id")
        all_columns = list(dict.fromkeys([*existing.columns, *incoming.columns]))
        existing = existing.reindex(columns=all_columns)
        incoming = incoming.reindex(columns=all_columns)
        existing.update(incoming)
        new_rows = incoming.loc[~incoming.index.isin(existing.index)]
        if new_rows.empty:
            frame = existing
        else:
            parts = [part.dropna(axis=1, how="all") for part in (existing, new_rows)]
            frame = pd.concat(parts).reindex(columns=all_columns)
        frame = frame.reset_index()
    else:
        frame = incoming
    frame = frame.sort_values(["season", "pilot_id", "published_at", "document_id"])
    frame.to_parquet(path, index=False)
