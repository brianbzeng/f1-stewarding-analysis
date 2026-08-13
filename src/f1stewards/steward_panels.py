"""Source-preserving FIA steward signature parsing and document-panel lineage."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from f1stewards.config import PROJECT_ROOT

STEWARD_ALIAS_PATH = PROJECT_ROOT / "config" / "steward_name_aliases.csv"
PANEL_PARSER_VERSION = "fia-signature-panel-v1"
ALIAS_COLUMNS = ["steward_id", "canonical_name", "observed_name", "alias_status"]
STEWARD_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class ParsedSignature:
    steward_ids: tuple[str, ...]
    raw_signature_lines: tuple[str, ...]


@dataclass(frozen=True)
class StewardPanelFrames:
    aliases: pd.DataFrame
    stewards: pd.DataFrame
    panels: pd.DataFrame
    panel_members: pd.DataFrame
    document_panels: pd.DataFrame


def load_steward_name_aliases(path: Path = STEWARD_ALIAS_PATH) -> pd.DataFrame:
    """Load reviewed FIA signature spellings and stable steward identities."""

    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != ALIAS_COLUMNS:
        raise ValueError(f"Unexpected columns in {path.name}")
    if frame.empty or frame.eq("").any().any():
        raise ValueError(f"{path.name} must contain complete alias records")
    if frame["observed_name"].duplicated().any():
        raise ValueError("observed steward aliases must be unique")
    if not frame["steward_id"].map(
        lambda value: bool(STEWARD_ID_PATTERN.fullmatch(value))
    ).all():
        raise ValueError("steward_id values must be stable lowercase identifiers")
    canonical_counts = frame["alias_status"].eq("canonical").groupby(frame["steward_id"]).sum()
    if not canonical_counts.eq(1).all():
        raise ValueError("Every steward must have exactly one canonical alias")
    name_counts = frame.groupby("steward_id")["canonical_name"].nunique()
    if not name_counts.eq(1).all():
        raise ValueError("Every steward_id must map to one canonical name")
    canonical = frame.loc[frame["alias_status"].eq("canonical")]
    if not canonical["canonical_name"].eq(canonical["observed_name"]).all():
        raise ValueError("Canonical aliases must equal the canonical name")
    return frame


def _normalized_line(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def _line_members(
    line: str,
    alias_lookup: dict[str, str],
    aliases_longest_first: list[str],
) -> list[str]:
    normalized = _normalized_line(line)
    if normalized in alias_lookup:
        return [alias_lookup[normalized]]
    for first_name in aliases_longest_first:
        prefix = first_name + " "
        if normalized.startswith(prefix):
            second_name = normalized[len(prefix) :]
            if second_name in alias_lookup:
                return [alias_lookup[first_name], alias_lookup[second_name]]
    return []


def parse_steward_signature(
    raw_text: str | None,
    aliases: pd.DataFrame,
    *,
    tail_lines: int = 20,
) -> ParsedSignature | None:
    """Parse three-to-five unique signature members from the end of an FIA decision."""

    alias_lookup = dict(zip(aliases["observed_name"], aliases["steward_id"], strict=True))
    aliases_longest_first = sorted(alias_lookup, key=len, reverse=True)
    lines = (raw_text or "").splitlines()[-tail_lines:]
    steward_ids: list[str] = []
    signature_lines: list[str] = []
    for line in lines:
        members = _line_members(line, alias_lookup, aliases_longest_first)
        if not members:
            continue
        signature_lines.append(_normalized_line(line))
        for steward_id in members:
            if steward_id not in steward_ids:
                steward_ids.append(steward_id)
    if not 3 <= len(steward_ids) <= 5:
        return None
    return ParsedSignature(tuple(steward_ids), tuple(signature_lines))


def load_decision_signature_population(
    connection: duckdb.DuckDBPyConnection,
) -> pd.DataFrame:
    """Load every live, content-confirmed FIA decision at document grain."""

    return connection.sql(
        """
        SELECT
            document.document_id,
            document.event_id,
            text.raw_text
        FROM raw.source_documents AS document
        JOIN raw.document_text AS text USING (document_id)
        JOIN analysis.v_source_documents_typed AS typed USING (document_id)
        WHERE typed.content_document_class = 'steward_decision'
          AND document.is_recalled = FALSE
        ORDER BY document.event_id, document.document_id
        """
    ).df()


def _panel_id(event_id: str, steward_ids: tuple[str, ...]) -> str:
    identity = event_id + "|" + "|".join(sorted(steward_ids))
    return f"panel-{event_id}-{hashlib.sha256(identity.encode()).hexdigest()[:10]}"


def build_steward_panel_frames(
    population: pd.DataFrame,
    aliases: pd.DataFrame,
) -> StewardPanelFrames:
    """Build exact document assignments plus only unambiguous event-consensus fallbacks."""

    required = {"document_id", "event_id", "raw_text"}
    if missing := required - set(population.columns):
        raise ValueError(f"Decision signature population is missing: {', '.join(sorted(missing))}")
    if population.empty or population["document_id"].duplicated().any():
        raise ValueError("Decision signature population must have unique document rows")

    extracted: dict[str, ParsedSignature] = {}
    document_event: dict[str, str] = {}
    event_panels: dict[str, set[str]] = {}
    panel_members_by_id: dict[str, tuple[str, ...]] = {}
    panel_event_by_id: dict[str, str] = {}
    panel_source_documents: dict[str, list[str]] = {}
    for row in population.itertuples(index=False):
        document_id = str(row.document_id)
        event_id = str(row.event_id)
        document_event[document_id] = event_id
        signature = parse_steward_signature(row.raw_text, aliases)
        if signature is None:
            continue
        extracted[document_id] = signature
        members = tuple(sorted(signature.steward_ids))
        panel_id = _panel_id(event_id, members)
        event_panels.setdefault(event_id, set()).add(panel_id)
        panel_members_by_id[panel_id] = members
        panel_event_by_id[panel_id] = event_id
        panel_source_documents.setdefault(panel_id, []).append(document_id)

    panel_rows = []
    member_rows = []
    for panel_id, member_ids in sorted(panel_members_by_id.items()):
        panel_rows.append(
            {
                "panel_id": panel_id,
                "event_id": panel_event_by_id[panel_id],
                "chair_steward_id": None,
                "driver_steward_id": None,
                "panel_size": len(member_ids),
                "panel_source_document_id": min(panel_source_documents[panel_id]),
            }
        )
        member_rows.extend(
            {
                "panel_id": panel_id,
                "steward_id": steward_id,
                "role": "member_role_not_inferred",
                "member_sequence": sequence,
            }
            for sequence, steward_id in enumerate(member_ids, start=1)
        )

    assignment_rows = []
    for row in population.itertuples(index=False):
        document_id = str(row.document_id)
        event_id = document_event[document_id]
        signature = extracted.get(document_id)
        if signature is not None:
            panel_id = _panel_id(event_id, tuple(sorted(signature.steward_ids)))
            basis = "document_signature_exact"
            status = "exact"
            extracted_count = len(signature.steward_ids)
            raw_lines = " || ".join(signature.raw_signature_lines)
        elif len(event_panels.get(event_id, set())) == 1:
            panel_id = next(iter(event_panels[event_id]))
            basis = "single_event_panel_consensus"
            status = "event_consensus"
            extracted_count = 0
            raw_lines = None
        else:
            panel_id = None
            basis = "unresolved"
            status = "unresolved"
            extracted_count = 0
            raw_lines = None
        assignment_rows.append(
            {
                "document_id": document_id,
                "event_id": event_id,
                "panel_id": panel_id,
                "assignment_basis": basis,
                "signature_parse_status": status,
                "extracted_member_count": extracted_count,
                "raw_signature_lines": raw_lines,
                "parser_version": PANEL_PARSER_VERSION,
            }
        )

    canonical = aliases.loc[aliases["alias_status"].eq("canonical")]
    stewards = canonical[["steward_id", "canonical_name"]].rename(
        columns={"canonical_name": "full_name"}
    )
    stewards = stewards.assign(nationality=None, nationality_source_url=None)
    return StewardPanelFrames(
        aliases=aliases.copy(),
        stewards=stewards.reset_index(drop=True),
        panels=pd.DataFrame(
            panel_rows,
            columns=[
                "panel_id",
                "event_id",
                "chair_steward_id",
                "driver_steward_id",
                "panel_size",
                "panel_source_document_id",
            ],
        ),
        panel_members=pd.DataFrame(
            member_rows,
            columns=["panel_id", "steward_id", "role", "member_sequence"],
        ),
        document_panels=pd.DataFrame(
            assignment_rows,
            columns=[
                "document_id",
                "event_id",
                "panel_id",
                "assignment_basis",
                "signature_parse_status",
                "extracted_member_count",
                "raw_signature_lines",
                "parser_version",
            ],
        ),
    )


def replace_steward_panel_frames(
    connection: duckdb.DuckDBPyConnection,
    frames: StewardPanelFrames,
) -> None:
    """Replace active panel lineage without overwriting sourced nationalities."""

    batches = {
        "steward_alias_batch": frames.aliases,
        "steward_batch": frames.stewards,
        "panel_batch": frames.panels,
        "panel_member_batch": frames.panel_members,
        "document_panel_batch": frames.document_panels,
    }
    for name, frame in batches.items():
        connection.register(name, frame)
    try:
        connection.execute("BEGIN TRANSACTION")
        connection.execute("DELETE FROM curated.document_panels")
        connection.execute("DELETE FROM curated.panel_members")
        connection.execute("DELETE FROM metadata.steward_name_aliases")
        connection.execute(
            """
            INSERT INTO metadata.steward_name_aliases BY NAME
            SELECT * FROM steward_alias_batch
            """
        )
        connection.execute(
            """
            INSERT INTO curated.stewards BY NAME
            SELECT * FROM steward_batch
            ON CONFLICT (steward_id) DO UPDATE SET
                full_name = EXCLUDED.full_name
            """
        )
        connection.execute(
            """
            INSERT INTO curated.panels BY NAME
            SELECT * FROM panel_batch
            ON CONFLICT (panel_id) DO UPDATE SET
                event_id = EXCLUDED.event_id,
                chair_steward_id = EXCLUDED.chair_steward_id,
                driver_steward_id = EXCLUDED.driver_steward_id,
                panel_size = EXCLUDED.panel_size,
                panel_source_document_id = EXCLUDED.panel_source_document_id
            """
        )
        connection.execute(
            "INSERT INTO curated.panel_members BY NAME SELECT * FROM panel_member_batch"
        )
        connection.execute(
            "INSERT INTO curated.document_panels BY NAME SELECT * FROM document_panel_batch"
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    else:
        active_panel_ids = set(frames.panels["panel_id"].astype(str))
        stored_panel_ids = {
            row[0] for row in connection.sql("SELECT panel_id FROM curated.panels").fetchall()
        }
        for panel_id in sorted(stored_panel_ids - active_panel_ids):
            adjudication_references = connection.execute(
                "SELECT count(*) FROM curated.adjudications WHERE panel_id = ?", [panel_id]
            ).fetchone()[0]
            if adjudication_references:
                raise ValueError(
                    f"Cannot remove stale panel {panel_id}: referenced by "
                    f"{adjudication_references} curated adjudications"
                )
            # DuckDB 1.4.x can raise an internal optional-pointer error even when this
            # foreign-key parent has no remaining references. Retain the dormant key,
            # clear its obsolete source pointer, and derive every active panel measure
            # from current document assignments.
            connection.execute(
                "UPDATE curated.panels SET panel_source_document_id = NULL "
                "WHERE panel_id = ?",
                [panel_id],
            )
    finally:
        for name in batches:
            connection.unregister(name)


def steward_panel_audit(connection: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return extraction controls separately from the nationality-analysis release gate."""

    metrics = connection.sql(
        """
        SELECT
            (SELECT count(*) FROM curated.document_panels) AS documents,
            (SELECT count(*) FROM curated.document_panels
             WHERE signature_parse_status = 'exact') AS exact_documents,
            (SELECT count(*) FROM curated.document_panels
             WHERE signature_parse_status = 'event_consensus') AS consensus_documents,
            (SELECT count(*) FROM curated.document_panels
             WHERE signature_parse_status = 'unresolved') AS unresolved_documents,
            (SELECT count(DISTINCT event_id) FROM curated.document_panels) AS events,
            (SELECT count(DISTINCT event_id) FROM curated.document_panels
             WHERE signature_parse_status = 'exact') AS events_with_exact,
            (SELECT count(DISTINCT panel_id) FROM curated.document_panels
             WHERE panel_id IS NOT NULL) AS panels,
            (SELECT count(*)
             FROM curated.panels AS panel
             WHERE panel.panel_id IN (
                 SELECT panel_id FROM curated.document_panels WHERE panel_id IS NOT NULL
             ) AND panel.panel_size NOT BETWEEN 3 AND 5)
                AS invalid_panel_sizes,
            (SELECT count(*) FROM (
                SELECT event_id
                FROM curated.document_panels
                WHERE panel_id IS NOT NULL
                GROUP BY event_id
                HAVING count(DISTINCT panel_id) > 1
             )) AS multi_panel_events,
            (SELECT count(DISTINCT panel_id) FROM curated.document_panels
             WHERE signature_parse_status = 'exact') AS exact_distinct_panels,
            (SELECT count(DISTINCT member.steward_id)
             FROM curated.panel_members AS member
             JOIN curated.stewards AS steward USING (steward_id)
             WHERE steward.nationality IS NULL OR steward.nationality_source_url IS NULL)
                AS unsourced_stewards,
            (SELECT count(DISTINCT steward_id) FROM curated.panel_members) AS panel_stewards
        """
    ).fetchone()
    (
        documents,
        exact_documents,
        consensus_documents,
        unresolved_documents,
        events,
        events_with_exact,
        panels,
        invalid_panel_sizes,
        multi_panel_events,
        exact_distinct_panels,
        unsourced_stewards,
        panel_stewards,
    ) = metrics
    controls = [
        ("extraction", "decision_population_nonempty", documents > 0, documents, "> 0"),
        (
            "extraction",
            "exact_signature_rate_at_least_95pct",
            exact_documents / documents >= 0.95 if documents else False,
            f"{exact_documents / documents:.6f}" if documents else "0",
            ">= 0.95",
        ),
        (
            "extraction",
            "every_event_has_exact_signature",
            events_with_exact == events,
            events_with_exact,
            events,
        ),
        (
            "extraction",
            "document_assignment_complete",
            unresolved_documents == 0,
            unresolved_documents,
            0,
        ),
        (
            "extraction",
            "panel_sizes_valid",
            invalid_panel_sizes == 0,
            invalid_panel_sizes,
            0,
        ),
        (
            "extraction",
            "exact_panel_dimension_complete",
            exact_distinct_panels == panels,
            exact_distinct_panels,
            panels,
        ),
        (
            "extraction",
            "multi_panel_structure_retained",
            multi_panel_events > 0,
            multi_panel_events,
            "> 0",
        ),
        (
            "analysis_release",
            "steward_nationalities_sourced",
            unsourced_stewards == 0,
            unsourced_stewards,
            0,
        ),
        (
            "analysis_release",
            "panel_nationality_analysis_release",
            unresolved_documents == 0 and unsourced_stewards == 0,
            f"unresolved={unresolved_documents}; unsourced={unsourced_stewards}",
            "unresolved=0; unsourced=0",
        ),
    ]
    return pd.DataFrame(
        [
            {
                "gate_type": gate_type,
                "control": control,
                "status": "pass" if passed else "fail",
                "observed": str(observed),
                "expected": str(expected),
                "detail": (
                    f"documents={documents}; exact={exact_documents}; "
                    f"consensus={consensus_documents}; panels={panels}; "
                    f"multi_panel_events={multi_panel_events}; panel_stewards={panel_stewards}"
                ),
            }
            for gate_type, control, passed, observed, expected in controls
        ]
    )
