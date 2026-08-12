# ruff: noqa: E501
"""Static, auditable evidence explorer for reviewed or provisional adjudications."""

from __future__ import annotations

import html
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

FILTER_COLUMNS = (
    "season",
    "event_id",
    "session_type",
    "incident_family",
    "outcome_family",
    "guideline_regime",
    "conformance_status",
    "review_status",
)


def apply_explorer_filters(
    frame: pd.DataFrame,
    filters: dict[str, set[Any]],
) -> pd.DataFrame:
    """Apply exact-match multi-select filters used by the browser and reference tests."""

    selected = frame.copy()
    for column, values in filters.items():
        if column not in FILTER_COLUMNS:
            raise ValueError(f"Unsupported explorer filter: {column}")
        if values:
            selected = selected[selected[column].isin(values)]
    return selected


def _sanction_label(row: pd.Series) -> str:
    if row["outcome_family"] == "no_further_action":
        return "No further action"
    parts = [str(row["outcome_family"]).replace("_", " ").title()]
    if pd.notna(row.get("penalty_seconds")):
        parts.append(f"{float(row['penalty_seconds']):g} seconds")
    if pd.notna(row.get("grid_places")):
        parts.append(f"{int(row['grid_places'])} grid places")
    if pd.notna(row.get("penalty_points")):
        parts.append(f"{int(row['penalty_points'])} penalty points")
    return " · ".join(parts)


def _rule_url(row: pd.Series) -> str:
    clause = str(row.get("guideline_clause") or "")
    if clause.startswith("DSG_"):
        return str(row.get("driving_guideline_url") or "")
    if clause.startswith("Penalty_"):
        return str(row.get("penalty_guideline_url") or "")
    return str(row.get("appendix_l_url") or row.get("sporting_regulation_url") or "")


def assemble_adjudications(
    coded: pd.DataFrame,
    events: pd.DataFrame,
    texts: pd.DataFrame,
    results: pd.DataFrame,
    classifications: pd.DataFrame,
    regulatory_links: pd.DataFrame,
) -> pd.DataFrame:
    """Assemble one evidence-rich explorer row per candidate adjudication."""

    frame = coded.merge(events, on="event_id", how="left", validate="many_to_one")
    frame = frame.merge(
        texts,
        left_on="source_document_id",
        right_on="document_id",
        how="left",
        validate="one_to_one",
    )
    accused = results.rename(
        columns={
            "driver_number": "accused_driver_number",
            "driver_name": "accused_driver_name",
        }
    )[["event_id", "accused_driver_number", "accused_driver_name"]]
    affected = results.rename(
        columns={
            "driver_number": "affected_driver_number",
            "driver_name": "affected_driver_name",
        }
    )[["event_id", "affected_driver_number", "affected_driver_name"]]
    frame = frame.merge(
        accused,
        on=["event_id", "accused_driver_number"],
        how="left",
        validate="many_to_one",
    )
    frame = frame.merge(
        affected,
        on=["event_id", "affected_driver_number"],
        how="left",
        validate="many_to_one",
    )
    frame = frame.merge(classifications, on="event_id", how="left", validate="many_to_one")
    frame = frame.merge(regulatory_links, on="event_id", how="left", validate="many_to_one")
    frame["sanction_label"] = frame.apply(_sanction_label, axis=1)
    frame["rule_url"] = frame.apply(_rule_url, axis=1)
    return frame


def _query_frames(
    connection: duckdb.DuckDBPyConnection,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = connection.sql(
        """
        SELECT event_id, season, event_name, event_date
        FROM metadata.events
        """
    ).df()
    texts = connection.sql(
        """
        SELECT document_id, fact_text, decision_text, reason_text
        FROM raw.document_text
        """
    ).df()
    results = connection.sql(
        """
        SELECT event_id, driver_number, driver_name
        FROM raw.fastf1_results
        """
    ).df()
    classifications = connection.sql(
        """
        SELECT event_id, min(document_url) AS classification_url
        FROM raw.source_documents
        WHERE document_class = 'final_classification'
          AND content_sha256 IS NOT NULL
        GROUP BY event_id
        """
    ).df()
    regulatory_links = connection.sql(
        """
        SELECT
            l.event_id,
            max(s.source_url) FILTER (
                WHERE s.document_type = 'f1_sporting_regulations'
            ) AS sporting_regulation_url,
            max(s.source_url) FILTER (
                WHERE s.document_type = 'appendix_l_driving_conduct'
            ) AS appendix_l_url,
            max(s.source_url) FILTER (
                WHERE s.document_type = 'f1_driving_standards_guidelines'
            ) AS driving_guideline_url,
            max(s.source_url) FILTER (
                WHERE s.document_type = 'stewards_penalty_guidelines'
            ) AS penalty_guideline_url
        FROM metadata.event_regulatory_sources AS l
        JOIN metadata.regulatory_sources AS s USING (source_id)
        GROUP BY l.event_id
        """
    ).df()
    return events, texts, results, classifications, regulatory_links


def load_explorer_adjudications(
    connection: duckdb.DuckDBPyConnection,
    coding_path: Path,
) -> pd.DataFrame:
    coded = pd.read_csv(coding_path)
    return assemble_adjudications(coded, *_query_frames(connection))


def load_explorer_impacts(
    connection: duckdb.DuckDBPyConnection,
    impact_path: Path,
) -> pd.DataFrame:
    impacts = pd.read_csv(impact_path)
    documents = connection.sql(
        """
        SELECT document_id, document_url
        FROM raw.source_documents
        """
    ).df()
    decision_urls = documents.rename(
        columns={"document_id": "source_document_id", "document_url": "decision_url"}
    )
    classification_urls = documents.rename(
        columns={
            "document_id": "classification_source_document_id",
            "document_url": "classification_url",
        }
    )
    return impacts.merge(
        decision_urls, on="source_document_id", how="left", validate="many_to_one"
    ).merge(
        classification_urls,
        on="classification_source_document_id",
        how="left",
        validate="many_to_one",
    )


def load_explorer_harms(
    connection: duckdb.DuckDBPyConnection,
    harm_path: Path,
) -> pd.DataFrame:
    harms = pd.read_csv(harm_path)
    documents = connection.sql(
        """
        SELECT document_id, document_url
        FROM raw.source_documents
        """
    ).df()
    decision_urls = documents.rename(
        columns={"document_id": "source_document_id", "document_url": "decision_url"}
    )
    classification_urls = documents.rename(
        columns={
            "document_id": "classification_source_document_id",
            "document_url": "classification_url",
        }
    )
    return harms.merge(
        decision_urls, on="source_document_id", how="left", validate="many_to_one"
    ).merge(
        classification_urls,
        on="classification_source_document_id",
        how="left",
        validate="many_to_one",
    )


def _quality_summary(
    connection: duckdb.DuckDBPyConnection,
    adjudications: pd.DataFrame,
    impacts: pd.DataFrame,
    harms: pd.DataFrame,
    locations: pd.DataFrame,
    relations: pd.DataFrame,
    cross_event_effects: pd.DataFrame,
    review_frame: pd.DataFrame,
) -> dict[str, Any]:
    active_failures, recalled, metadata_only, source_as_of, timing_as_of = connection.sql(
        """
        SELECT
            (SELECT count(*) FROM raw.source_documents
             WHERE retrieval_error IS NOT NULL AND NOT is_recalled),
            (SELECT count(*) FROM raw.source_documents WHERE is_recalled),
            (SELECT count(*) FROM metadata.regulatory_sources
             WHERE applicability_status LIKE '%metadata_only%'),
            (SELECT max(retrieved_at) FROM raw.source_documents),
            (SELECT max(retrieved_at) FROM raw.fastf1_results)
        """
    ).fetchone()
    missing_core = adjudications[
        adjudications[["fact_text", "decision_text", "reason_text"]].isna().any(axis=1)
    ]["adjudication_id"].tolist()
    resolved_review_statuses = {"agree", "correct"}
    release_ready_statuses = {"double_coded", "adjudicated"}
    review_complete = int(
        review_frame.review_status.isin(resolved_review_statuses).sum()
    )
    curated_statuses = pd.concat(
        [
            adjudications.review_status,
            impacts.review_status,
            harms.review_status,
            locations.review_status,
            relations.review_status,
            cross_event_effects.review_status,
        ],
        ignore_index=True,
    )
    return {
        "active_retrieval_failures": int(active_failures),
        "recalled_source_records": int(recalled),
        "metadata_only_regulatory_sources": int(metadata_only),
        "missing_core_text_ids": missing_core,
        "review_complete": review_complete,
        "review_unresolved": int(len(review_frame) - review_complete),
        "review_total": int(len(review_frame)),
        "curated_review_ready": int(
            curated_statuses.isin(release_ready_statuses).sum()
        ),
        "curated_review_total": int(len(curated_statuses)),
        "source_data_as_of": source_as_of.isoformat() if source_as_of else None,
        "timing_data_as_of": timing_as_of.isoformat() if timing_as_of else None,
    }


def _git_commit(project_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _json_records(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, Any]]:
    return json.loads(frame[columns].to_json(orient="records", date_format="iso"))


def explorer_release_status(quality: dict[str, Any]) -> str:
    """Return reviewed only after both review and reconciliation gates pass."""

    return (
        "reviewed"
        if (
            quality["review_unresolved"] == 0
            and quality["curated_review_ready"] == quality["curated_review_total"]
        )
        else "provisional"
    )


def build_explorer_payload(
    connection: duckdb.DuckDBPyConnection,
    project_root: Path,
    coding_path: Path,
    impact_path: Path,
    harm_path: Path,
    location_path: Path,
    relation_path: Path,
    cross_event_path: Path,
    review_path: Path,
) -> dict[str, Any]:
    adjudications = load_explorer_adjudications(connection, coding_path)
    impacts = load_explorer_impacts(connection, impact_path)
    harms = load_explorer_harms(connection, harm_path)
    locations = pd.read_csv(location_path)
    relations = pd.read_csv(relation_path)
    cross_event_effects = pd.read_csv(cross_event_path)
    reviews = pd.read_csv(review_path)
    quality = _quality_summary(
        connection,
        adjudications,
        impacts,
        harms,
        locations,
        relations,
        cross_event_effects,
        reviews,
    )
    release_status = explorer_release_status(quality)
    adjudication_columns = [
        "adjudication_id",
        "incident_id",
        "event_id",
        "season",
        "event_name",
        "event_date",
        "session_type",
        "lap_number",
        "turn_number",
        "incident_family",
        "outcome_family",
        "sanction_label",
        "accused_driver_number",
        "accused_driver_name",
        "affected_driver_number",
        "affected_driver_name",
        "guideline_regime",
        "guideline_clause",
        "guideline_expected_outcome",
        "conformance_status",
        "review_status",
        "fact_text",
        "decision_text",
        "reason_text",
        "coding_notes",
        "source_url",
        "classification_url",
        "rule_url",
    ]
    impact_columns = [
        "impact_assessment_id",
        "adjudication_id",
        "event_id",
        "driver_number",
        "sanction_type",
        "sanction_application",
        "impact_level",
        "official_finish_position",
        "counterfactual_finish_position",
        "positions_gained_without_penalty",
        "official_points",
        "counterfactual_points",
        "points_gained_without_penalty",
        "podium_changed",
        "win_changed",
        "calculation_method",
        "assumptions",
        "review_status",
        "decision_url",
        "classification_url",
    ]
    harm_columns = [
        "harm_assessment_id",
        "adjudication_id",
        "event_id",
        "affected_driver_number",
        "counterparty_driver_number",
        "responsibility_status",
        "harm_evidence_level",
        "damage_evidence",
        "damage_type",
        "repair_stop_required",
        "pit_lap",
        "pit_response_status",
        "pit_lane_loss_seconds",
        "repair_stationary_seconds",
        "retirement_status",
        "position_before",
        "position_after",
        "net_positions_lost_observed",
        "position_window_start_lap",
        "position_window_end_lap",
        "relative_time_comparator_driver_number",
        "affected_relative_time_loss_seconds",
        "relative_time_window_start_lap",
        "relative_time_window_end_lap",
        "post_incident_clean_laps",
        "persistent_pace_status",
        "persistent_delta_per_lap_seconds",
        "persistent_laps_exposed",
        "persistent_loss_seconds_lower",
        "persistent_loss_seconds_estimate",
        "persistent_loss_seconds_upper",
        "net_effect_direction",
        "benefit_mechanism",
        "calculation_method",
        "assumptions",
        "review_status",
        "decision_url",
        "classification_url",
    ]
    location_columns = list(locations.columns)
    relation_columns = list(relations.columns)
    cross_event_columns = list(cross_event_effects.columns)
    return {
        "metadata": {
            "title": "The Cost of Discretion — Evidence Explorer",
            "release_status": release_status,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "git_commit": _git_commit(project_root),
            "adjudication_count": len(adjudications),
            "event_count": int(adjudications.event_id.nunique()),
            "incident_count": int(adjudications.incident_id.nunique()),
        },
        "adjudications": _json_records(adjudications, adjudication_columns),
        "impacts": _json_records(impacts, impact_columns),
        "harms": _json_records(harms, harm_columns),
        "locations": _json_records(locations, location_columns),
        "relations": _json_records(relations, relation_columns),
        "cross_event_effects": _json_records(cross_event_effects, cross_event_columns),
        "quality": quality,
    }


def validate_explorer_payload(payload: dict[str, Any]) -> None:
    """Enforce public-product invariants before writing HTML."""

    adjudications = payload.get("adjudications", [])
    if not adjudications:
        raise ValueError("Explorer requires at least one adjudication")
    for row in adjudications:
        if not row.get("source_url"):
            raise ValueError(f"Missing official decision URL: {row.get('adjudication_id')}")
        if (
            row.get("season") == 2025
            and row.get("conformance_status") not in {"not_applicable", "unclear"}
            and (not row.get("guideline_clause") or not row.get("rule_url"))
        ):
            raise ValueError(
                f"Missing 2025 guideline lineage: {row.get('adjudication_id')}"
            )
    for row in payload.get("cross_event_effects", []):
        if not row.get("application_grid_url") or not row.get(
            "application_classification_url"
        ):
            raise ValueError(
                "Missing application-event evidence: "
                f"{row.get('cross_event_effect_id')}"
            )
    if any("nationality" in key.casefold() for row in adjudications for key in row):
        raise ValueError("Default explorer payload cannot contain nationality ranking fields")


def _option_values(records: list[dict[str, Any]], key: str) -> list[Any]:
    values = {record.get(key) for record in records if record.get(key) is not None}
    return sorted(values, key=lambda value: str(value))


def render_explorer_html(payload: dict[str, Any]) -> str:
    """Render a dependency-free, accessible, client-filtered HTML explorer."""

    validate_explorer_payload(payload)
    metadata = payload["metadata"]
    status = str(metadata["release_status"])
    status_class = "reviewed" if status == "reviewed" else "provisional"
    overview_warning = (
        "<strong>Reviewed release:</strong> the displayed inputs have passed independent "
        "review and reconciliation. Model-based claims still require their separate "
        "validation and support gates."
        if status == "reviewed"
        else "<strong>Provisional pilot:</strong> candidate coding has not completed "
        "independent review and reconciliation. Counts demonstrate the pipeline; they "
        "are not final findings about FIA consistency."
    )
    safe_payload = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    options = {
        key: _option_values(payload["adjudications"], key)
        for key in (
            "season",
            "event_id",
            "incident_family",
            "outcome_family",
            "conformance_status",
            "review_status",
        )
    }
    safe_options = html.escape(json.dumps(options), quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Auditable Formula One stewarding evidence explorer">
  <title>{html.escape(metadata['title'])}</title>
  <style>
    :root {{ --ink:#14202b; --muted:#536270; --paper:#f5f7f8; --panel:#fff;
      --navy:#12324a; --blue:#176b87; --gold:#a66508; --line:#ced7dd; --focus:#ffbf47; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; color:var(--ink); background:var(--paper);
      font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
    a {{ color:#075985; }} a:focus,button:focus,select:focus {{ outline:3px solid var(--focus); outline-offset:2px; }}
    header {{ background:var(--navy); color:#fff; padding:2rem max(1rem,calc((100% - 1180px)/2)); }}
    header p {{ max-width:820px; margin:.5rem 0 0; color:#e6eef3; }}
    .status {{ display:inline-block; margin-top:1rem; padding:.4rem .7rem; border-radius:.25rem;
      font-weight:700; text-transform:uppercase; letter-spacing:.04em; }}
    .status.provisional {{ background:#fff1cf; color:#5c3900; }} .status.reviewed {{ background:#d8f3dc; color:#164b24; }}
    nav {{ background:#fff; border-bottom:1px solid var(--line); position:sticky; top:0; z-index:2; }}
    .tabs {{ max-width:1180px; margin:auto; display:flex; gap:.25rem; padding:.5rem 1rem; overflow:auto; }}
    .tabs button {{ border:0; background:transparent; color:var(--navy); padding:.7rem .9rem; font-weight:650; cursor:pointer; }}
    .tabs button[aria-selected="true"] {{ background:#e7f1f5; border-bottom:3px solid var(--blue); }}
    main {{ max-width:1180px; margin:0 auto; padding:1.5rem 1rem 4rem; }}
    [role="tabpanel"][hidden] {{ display:none; }} h2 {{ color:var(--navy); margin-top:0; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:1rem; margin:1rem 0 1.5rem; }}
    .card,.panel {{ background:var(--panel); border:1px solid var(--line); border-radius:.4rem; padding:1rem; }}
    .card strong {{ display:block; font-size:1.7rem; color:var(--navy); }} .card span {{ color:var(--muted); }}
    .filters {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:.75rem; margin:1rem 0; }}
    label {{ display:block; font-weight:650; }} select {{ width:100%; padding:.55rem; margin-top:.25rem; border:1px solid #7a8994; background:#fff; }}
    button.action {{ background:var(--blue); color:#fff; border:0; padding:.65rem .9rem; border-radius:.25rem; cursor:pointer; }}
    .table-wrap {{ overflow-x:auto; background:#fff; border:1px solid var(--line); }}
    table {{ width:100%; border-collapse:collapse; }} caption {{ text-align:left; font-weight:700; padding:.8rem; }}
    th,td {{ text-align:left; vertical-align:top; padding:.65rem; border-bottom:1px solid var(--line); }}
    th {{ background:#eaf0f3; color:var(--navy); }} details {{ min-width:270px; }} summary {{ cursor:pointer; font-weight:650; color:#075985; }}
    .evidence-block {{ margin:.7rem 0; }} .evidence-block strong {{ display:block; }}
    .warning {{ border-left:5px solid var(--gold); background:#fff8e6; padding:1rem; margin:1rem 0; }}
    .empty {{ padding:1.5rem; color:var(--muted); }} .muted {{ color:var(--muted); }}
    .bar-row {{ display:grid; grid-template-columns:minmax(145px,1fr) 3fr auto; gap:.6rem; align-items:center; margin:.4rem 0; }}
    .bar {{ height:1rem; background:#dce8ed; }} .bar > span {{ display:block; height:100%; background:var(--blue); }}
    footer {{ border-top:1px solid var(--line); padding:1.5rem 1rem; color:var(--muted); text-align:center; }}
    @media (max-width:650px) {{ th:nth-child(3),td:nth-child(3) {{ display:none; }} }}
  </style>
</head>
<body>
<header>
  <h1>The Cost of Discretion</h1>
  <p>An evidence-first explorer for formally documented Formula One stewarding decisions. It is a review tool, not a ranking of drivers, nationalities, or alleged errors.</p>
  <span class="status {status_class}">{html.escape(status)}</span>
</header>
<nav aria-label="Explorer views"><div class="tabs" role="tablist">
  <button role="tab" aria-selected="true" aria-controls="overview" id="tab-overview">Overview</button>
  <button role="tab" aria-selected="false" aria-controls="decisions" id="tab-decisions">Decision search</button>
  <button role="tab" aria-selected="false" aria-controls="comparables" id="tab-comparables">Comparable cases</button>
  <button role="tab" aria-selected="false" aria-controls="impact" id="tab-impact">Competitive impact</button>
  <button role="tab" aria-selected="false" aria-controls="harm" id="tab-harm">Victim harm</button>
  <button role="tab" aria-selected="false" aria-controls="context" id="tab-context">Incident context</button>
  <button role="tab" aria-selected="false" aria-controls="carried" id="tab-carried">Carried sanctions</button>
  <button role="tab" aria-selected="false" aria-controls="quality" id="tab-quality">Data quality</button>
</div></nav>
<main>
  <section id="overview" role="tabpanel" aria-labelledby="tab-overview">
    <h2>Population and evidence status</h2>
    <div class="warning">{overview_warning}</div>
    <div class="cards" id="overview-cards"></div>
    <div class="panel"><h3>Adjudications by outcome</h3><div id="outcome-bars" aria-label="Outcome count chart"></div></div>
    <p><a href="../docs/project_protocol.md">Protocol</a> · <a href="../docs/decision_codebook.md">Codebook</a> · <a href="../docs/analysis_acceptance_criteria.md">Acceptance criteria and limitations</a></p>
  </section>
  <section id="decisions" role="tabpanel" aria-labelledby="tab-decisions" hidden>
    <h2>Decision search</h2><p>Filters use exact controlled values. Every row retains stable identifiers and official evidence links.</p>
    <div class="filters" id="filters" data-options="{safe_options}"></div>
    <p><button class="action" id="reset-filters">Reset filters</button> <button class="action" id="download-csv">Download filtered CSV</button></p>
    <p id="filter-status" role="status" aria-live="polite"></p><div class="table-wrap" id="decision-table"></div>
  </section>
  <section id="comparables" role="tabpanel" aria-labelledby="tab-comparables" hidden>
    <h2>Comparable cases</h2>
    <div class="warning"><strong>Not released yet.</strong> Nearest-case comparisons require a reviewed full corpus, grouped model validation, and the frozen minimum-support threshold. The interface will not rank provisional pilot cases or manufacture a model result.</div>
    <p>The released view will show observed context differences, expected outcome, residual, support score, model version, and an unavailable-evidence warning.</p>
  </section>
  <section id="impact" role="tabpanel" aria-labelledby="tab-impact" hidden>
    <h2>Competitive impact</h2><p>Mechanical arithmetic is displayed separately from strategy-dependent or non-estimable effects.</p>
    <div class="table-wrap" id="impact-table"></div>
  </section>
  <section id="harm" role="tabpanel" aria-labelledby="tab-harm" hidden>
    <h2>Victim harm and lasting consequences</h2><p>Observed harm, damage evidence, forced stops, and modeled persistent pace loss remain separate from responsibility and sanction burden. The table is a proportionality review input, not an automatic verdict that a penalty was wrong.</p>
    <div class="table-wrap" id="harm-table"></div>
  </section>
  <section id="context" role="tabpanel" aria-labelledby="tab-context" hidden>
    <h2>Incident location and causal context</h2><p>Turn ranges and directed multi-car edges preserve official context without assigning blame to every participant.</p>
    <div class="table-wrap" id="location-table"></div>
    <div class="table-wrap" id="relation-table"></div>
  </section>
  <section id="carried" role="tabpanel" aria-labelledby="tab-carried" hidden>
    <h2>Carried-over sanction effects</h2><p>Exact starting-grid displacement is separated from uncertain race-finish and points counterfactuals.</p>
    <div class="table-wrap" id="carried-table"></div>
  </section>
  <section id="quality" role="tabpanel" aria-labelledby="tab-quality" hidden>
    <h2>Data quality and lineage</h2><div class="cards" id="quality-cards"></div>
    <div class="panel"><h3>Build lineage</h3><dl id="build-lineage"></dl></div>
  </section>
</main>
<footer>Official FIA evidence and public FastF1 timing enrichment. Generated from commit <span id="footer-commit"></span>.</footer>
<script id="explorer-data" type="application/json">{safe_payload}</script>
<script>
const DATA=JSON.parse(document.getElementById('explorer-data').textContent); let filtered=[...DATA.adjudications];
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
const label=v=>String(v??'Not recorded').replaceAll('_',' ').replace(/\\b\\w/g,c=>c.toUpperCase());
function setTab(button){{document.querySelectorAll('[role=tab]').forEach(b=>{{const on=b===button;b.setAttribute('aria-selected',on);document.getElementById(b.getAttribute('aria-controls')).hidden=!on;}});button.focus();}}
document.querySelectorAll('[role=tab]').forEach(b=>{{b.addEventListener('click',()=>setTab(b));b.addEventListener('keydown',e=>{{const tabs=[...document.querySelectorAll('[role=tab]')];let i=tabs.indexOf(b);if(e.key==='ArrowRight')i=(i+1)%tabs.length;else if(e.key==='ArrowLeft')i=(i-1+tabs.length)%tabs.length;else return;e.preventDefault();setTab(tabs[i]);}});}});
function cards(){{const m=DATA.metadata,q=DATA.quality;document.getElementById('overview-cards').innerHTML=`<div class="card"><strong>${{m.adjudication_count}}</strong><span>candidate adjudications</span></div><div class="card"><strong>${{m.incident_count}}</strong><span>underlying incidents</span></div><div class="card"><strong>${{m.event_count}}</strong><span>pilot events</span></div><div class="card"><strong>${{q.review_complete}} / ${{q.review_total}}</strong><span>independent reviews complete</span></div>`;}}
function bars(){{const counts={{}};DATA.adjudications.forEach(r=>counts[r.outcome_family]=(counts[r.outcome_family]||0)+1);const max=Math.max(...Object.values(counts),1);document.getElementById('outcome-bars').innerHTML=Object.entries(counts).sort((a,b)=>b[1]-a[1]).map(([k,n])=>`<div class="bar-row"><span>${{esc(label(k))}}</span><div class="bar" role="img" aria-label="${{esc(label(k))}}: ${{n}} adjudications"><span style="width:${{100*n/max}}%"></span></div><strong>${{n}}</strong></div>`).join('');}}
const filterKeys=['season','event_id','incident_family','outcome_family','conformance_status','review_status'];
function makeFilters(){{const host=document.getElementById('filters'),opts=JSON.parse(host.dataset.options);host.innerHTML=filterKeys.map(k=>`<label>${{esc(label(k))}}<select data-filter="${{k}}"><option value="">All</option>${{opts[k].map(v=>`<option value="${{esc(v)}}">${{esc(label(v))}}</option>`).join('')}}</select></label>`).join('');host.querySelectorAll('select').forEach(s=>s.addEventListener('change',filterRows));}}
function filterRows(){{const values={{}};document.querySelectorAll('[data-filter]').forEach(s=>values[s.dataset.filter]=s.value);filtered=DATA.adjudications.filter(r=>filterKeys.every(k=>!values[k]||String(r[k])===values[k]));renderDecisions();}}
function renderDecisions(){{const host=document.getElementById('decision-table');document.getElementById('filter-status').textContent=`Showing ${{filtered.length}} of ${{DATA.adjudications.length}} adjudications.`;if(!filtered.length){{host.innerHTML='<p class="empty">No adjudications match the selected filters.</p>';return;}}host.innerHTML=`<table><caption>Filtered adjudications — ${{filtered.length}} rows</caption><thead><tr><th scope="col">Event / incident</th><th scope="col">Drivers</th><th scope="col">Outcome</th><th scope="col">Evidence and reasoning</th></tr></thead><tbody>${{filtered.map(r=>`<tr><td><strong>${{esc(r.event_name)}}</strong><br>${{esc(r.session_type)}} · lap ${{esc(r.lap_number)}}${{r.turn_number?' · turn '+esc(r.turn_number):''}}<br><code>${{esc(r.adjudication_id)}}</code></td><td>Car ${{esc(r.accused_driver_number)}} ${{esc(r.accused_driver_name)}}<br><span class="muted">Counterpart: Car ${{esc(r.affected_driver_number)}} ${{esc(r.affected_driver_name)}}</span></td><td>${{esc(r.sanction_label)}}<br><span class="muted">${{esc(label(r.incident_family))}} · ${{esc(label(r.conformance_status))}}</span></td><td><details><summary>Inspect evidence</summary><div class="evidence-block"><strong>Fact</strong>${{esc(r.fact_text||'Not available')}}</div><div class="evidence-block"><strong>Decision</strong>${{esc(r.decision_text||'Not available')}}</div><div class="evidence-block"><strong>Reason</strong>${{esc(r.reason_text||'Not available')}}</div><div class="evidence-block"><strong>Coding note</strong>${{esc(r.coding_notes)}}</div><p><a href="${{esc(r.source_url)}}">Official decision</a>${{r.classification_url?' · <a href="'+esc(r.classification_url)+'">Official classification</a>':''}}${{r.rule_url?' · <a href="'+esc(r.rule_url)+'">Applicable rule/guideline</a>':''}}</p></details></td></tr>`).join('')}}</tbody></table>`;}}
function renderImpact(){{const rows=DATA.impacts,host=document.getElementById('impact-table');host.innerHTML=`<table><caption>Impact assessments — ${{rows.length}} rows; evidence tiers are not aggregated together</caption><thead><tr><th scope="col">Assessment</th><th scope="col">Tier</th><th scope="col">Observed arithmetic</th><th scope="col">Method and evidence</th></tr></thead><tbody>${{rows.map(r=>`<tr><td><code>${{esc(r.impact_assessment_id)}}</code><br>Car ${{esc(r.driver_number)}} · ${{esc(label(r.sanction_type))}}</td><td><strong>${{esc(label(r.impact_level))}}</strong><br>${{esc(label(r.sanction_application))}}</td><td>${{r.impact_level==='mechanical'?`Position ${{esc(r.official_finish_position)}} → ${{esc(r.counterfactual_finish_position)}}; ${{esc(r.positions_gained_without_penalty)}} positions; ${{esc(r.points_gained_without_penalty)}} points`:'No deterministic alternate classification'}}</td><td>${{esc(r.calculation_method)}}<br><span class="muted">Assumptions: ${{esc(r.assumptions)}}</span><br><a href="${{esc(r.decision_url)}}">Decision</a> · <a href="${{esc(r.classification_url)}}">Classification</a></td></tr>`).join('')}}</tbody></table>`;}}
function renderHarm(){{const rows=DATA.harms,host=document.getElementById('harm-table');host.innerHTML=`<table><caption>Harm assessments - ${{rows.length}} rows; responsibility, harm, and sanction cost are not collapsed into one score</caption><thead><tr><th scope="col">Assessment</th><th scope="col">Evidence</th><th scope="col">Observed consequence</th><th scope="col">Method and evidence</th></tr></thead><tbody>${{rows.map(r=>`<tr><td><code>${{esc(r.harm_assessment_id)}}</code><br>Affected Car ${{esc(r.affected_driver_number)}} &middot; counterparty Car ${{esc(r.counterparty_driver_number)}}</td><td><strong>${{esc(label(r.harm_evidence_level))}}</strong><br>${{esc(label(r.responsibility_status))}}<br><span class="muted">${{esc(label(r.damage_evidence))}} &middot; ${{esc(label(r.damage_type))}}</span></td><td>${{r.position_before?`Position ${{esc(r.position_before)}} to ${{esc(r.position_after)}}; ${{esc(r.net_positions_lost_observed)}} net lost`:''}}${{r.affected_relative_time_loss_seconds!=null?`<br>${{esc(r.affected_relative_time_loss_seconds)}}s relative swing`:''}}<br>Repair stop: ${{esc(label(r.repair_stop_required))}}<br>Persistent pace: ${{esc(label(r.persistent_pace_status))}}<br>Net effect: ${{esc(label(r.net_effect_direction))}}</td><td>${{esc(r.calculation_method)}}<br><span class="muted">Assumptions: ${{esc(r.assumptions)}}</span><br><a href="${{esc(r.decision_url)}}">Decision</a> &middot; <a href="${{esc(r.classification_url)}}">Classification</a></td></tr>`).join('')}}</tbody></table>`;}}
function renderContext(){{const locations=DATA.locations,relations=DATA.relations;document.getElementById('location-table').innerHTML=`<table><caption>Supplemental locations - ${{locations.length}} rows</caption><thead><tr><th>Incident</th><th>Location</th><th>Evidence</th></tr></thead><tbody>${{locations.map(r=>`<tr><td><code>${{esc(r.incident_id)}}</code><br>Lap ${{esc(r.lap_number)}}</td><td><strong>${{esc(r.location_text)}}</strong><br>${{esc(label(r.location_type))}}</td><td>${{esc(r.coding_notes)}}<br><a href="${{esc(String(r.evidence_urls).split(';')[0])}}">Official decision</a></td></tr>`).join('')}}</tbody></table>`;document.getElementById('relation-table').innerHTML=`<table><caption>Directed incident relations - ${{relations.length}} edges</caption><thead><tr><th>Sequence</th><th>Driver relation</th><th>Scope and evidence</th></tr></thead><tbody>${{relations.map(r=>`<tr><td>${{esc(r.sequence)}}</td><td>Car ${{esc(r.source_driver_number)}} &rarr; Car ${{esc(r.target_driver_number)}}<br><strong>${{esc(label(r.relation_type))}}</strong></td><td>${{esc(label(r.relation_scope))}} &middot; ${{esc(label(r.evidence_level))}}<br>Fault attributed: ${{esc(r.fault_attributed)}}<br><span class="muted">${{esc(r.coding_notes)}}</span></td></tr>`).join('')}}</tbody></table>`;}}
function renderCarried(){{const rows=DATA.cross_event_effects,host=document.getElementById('carried-table');host.innerHTML=`<table><caption>Cross-event sanction effects - ${{rows.length}} rows</caption><thead><tr><th>Sanction</th><th>Realized grid effect</th><th>Race-outcome scope</th><th>Evidence</th></tr></thead><tbody>${{rows.map(r=>`<tr><td><code>${{esc(r.cross_event_effect_id)}}</code><br>Car ${{esc(r.driver_number)}} &middot; ${{esc(r.nominal_grid_places)}} places</td><td>Qualified P${{esc(r.qualifying_position)}} &rarr; started P${{esc(r.starting_grid_position)}}<br><strong>${{esc(r.realized_grid_places_lost)}} places lost</strong></td><td>${{esc(label(r.finish_effect_level))}}<br>${{esc(label(r.race_status))}} &middot; ${{esc(r.official_points)}} points<br><span class="muted">${{esc(r.assumptions)}}</span></td><td><a href="${{esc(r.application_grid_url)}}">Starting grid</a> &middot; <a href="${{esc(r.application_classification_url)}}">Classification</a></td></tr>`).join('')}}</tbody></table>`;}}
function renderQuality(){{const q=DATA.quality,m=DATA.metadata;document.getElementById('quality-cards').innerHTML=`<div class="card"><strong>${{q.active_retrieval_failures}}</strong><span>active retrieval failures</span></div><div class="card"><strong>${{q.recalled_source_records}}</strong><span>recalled source records retained</span></div><div class="card"><strong>${{q.metadata_only_regulatory_sources}}</strong><span>metadata-only regulatory gaps</span></div><div class="card"><strong>${{q.missing_core_text_ids.length}}</strong><span>candidate rows missing core text</span></div><div class="card"><strong>${{q.review_unresolved}}</strong><span>review targets unresolved</span></div><div class="card"><strong>${{q.curated_review_ready}} / ${{q.curated_review_total}}</strong><span>curated rows release-ready</span></div>`;document.getElementById('build-lineage').innerHTML=`<dt>Git commit</dt><dd>${{esc(m.git_commit)}}</dd><dt>Generated UTC</dt><dd>${{esc(m.generated_at_utc)}}</dd><dt>FIA sources as of</dt><dd>${{esc(q.source_data_as_of)}}</dd><dt>FastF1 timing as of</dt><dd>${{esc(q.timing_data_as_of)}}</dd>`;document.getElementById('footer-commit').textContent=m.git_commit;}}
function csv(){{const keys=['adjudication_id','incident_id','event_id','season','session_type','incident_family','outcome_family','sanction_label','review_status','source_url'];const lines=[keys.join(','),...filtered.map(r=>keys.map(k=>'"'+String(r[k]??'').replaceAll('"','""')+'"').join(','))];const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{{type:'text/csv'}}));a.download='filtered_f1_adjudications.csv';a.click();URL.revokeObjectURL(a.href);}}
document.getElementById('reset-filters').addEventListener('click',()=>{{document.querySelectorAll('[data-filter]').forEach(s=>s.value='');filterRows();}});document.getElementById('download-csv').addEventListener('click',csv);cards();bars();makeFilters();renderDecisions();renderImpact();renderHarm();renderContext();renderCarried();renderQuality();
</script>
</body></html>"""


def write_explorer(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_explorer_html(payload), encoding="utf-8")
