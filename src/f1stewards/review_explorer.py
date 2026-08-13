# ruff: noqa: E501
"""Portable full-corpus review console with content-addressed edit ledgers."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from f1stewards.coding_queue import (
    FINAL_ADJUDICATION_FIELDS,
    FINAL_DOCUMENT_FIELDS,
    FINAL_EXCLUSION_QA_FIELDS,
)
from f1stewards.coding_workspace import (
    WORKSPACE_ADJUDICATION_FILENAME,
    WORKSPACE_DOCUMENT_FILENAME,
    WORKSPACE_EXCLUSION_QA_FILENAME,
    WORKSPACE_MANIFEST_FILENAME,
)

REVIEW_EXPLORER_SCHEMA_VERSION = "full-corpus-review-explorer-v1"
REVIEW_LEDGER_SCHEMA_VERSION = "full-corpus-review-ledger-v1"
REVIEW_CHAIN_SCHEMA_VERSION = "full-corpus-review-chain-v1"
REVIEW_CHAIN_MANIFEST_FILENAME = "review_chain_manifest.json"
FIRST_PASS_MANIFEST_FILENAME = "first_pass_manifest.json"
FIRST_PASS_AUDIT_FILENAME = "first_pass_audit.csv"
COMPLETE_REVIEW_STATUSES = {"double_coded", "adjudicated"}
QA_EVIDENCE_FIELDS = [
    "driver_number_suggestion",
    "driver_name_suggestion",
    "participant_driver_numbers_suggestion",
    "affected_driver_numbers_suggestion",
    "candidate_action_suggestion",
    "outcome_family_suggestion",
    "penalty_seconds_suggestion",
    "penalty_points_suggestion",
    "grid_places_suggestion",
    "fact_text",
    "infringement_text",
    "decision_text",
    "reason_text",
]

QUEUE_SPECS: dict[str, dict[str, Any]] = {
    "documents": {
        "filename": WORKSPACE_DOCUMENT_FILENAME,
        "id_field": "document_review_id",
        "editable_fields": FINAL_DOCUMENT_FIELDS,
        "display_fields": [
            "document_review_id",
            "workspace_review_order",
            "workspace_priority_bucket",
            "season",
            "event_name",
            "title",
            "source_url",
            "version_state_suggestion",
            "session_scope_suggestion",
            "offence_family_suggestion",
            "eligibility_suggestion",
            "eligibility_basis",
            "parser_review_required",
            "parser_warnings_json",
            *FINAL_DOCUMENT_FIELDS,
        ],
    },
    "adjudications": {
        "filename": WORKSPACE_ADJUDICATION_FILENAME,
        "id_field": "adjudication_instance_id",
        "editable_fields": FINAL_ADJUDICATION_FIELDS,
        "display_fields": [
            "adjudication_instance_id",
            "adjudication_seed_id",
            "document_id",
            "workspace_review_order",
            "workspace_priority_bucket",
            "season",
            "event_name",
            "title",
            "source_url",
            "driver_number_suggestion",
            "driver_name_suggestion",
            "participant_driver_numbers_suggestion",
            "affected_driver_numbers_suggestion",
            "multi_party_suggestion",
            "session_type_suggestion",
            "lap_numbers_suggestion",
            "turn_numbers_suggestion",
            "offence_family_suggestion",
            "outcome_family_suggestion",
            "penalty_seconds_suggestion",
            "penalty_points_suggestion",
            "grid_places_suggestion",
            "eligibility_suggestion",
            "eligibility_basis",
            "candidate_action_suggestion",
            "parser_review_required",
            "fact_text",
            "infringement_text",
            "decision_text",
            "reason_text",
            "timing_session_loaded",
            "timing_ingestion_status",
            "timing_missing_within_rows",
            "timing_fallback_rows",
            "accused_driver_result_present_suggestion",
            "accused_driver_missing_within_rows",
            *FINAL_ADJUDICATION_FIELDS,
        ],
    },
    "exclusion_qa": {
        "filename": WORKSPACE_EXCLUSION_QA_FILENAME,
        "id_field": "exclusion_qa_id",
        "editable_fields": FINAL_EXCLUSION_QA_FIELDS,
        "derived_fields": QA_EVIDENCE_FIELDS,
        "display_fields": [
            "exclusion_qa_id",
            "document_id",
            "workspace_review_order",
            "workspace_priority_bucket",
            "season",
            "event_name",
            "title",
            "source_url",
            "version_state_suggestion",
            "session_type_suggestion",
            "session_scope_suggestion",
            "offence_family_suggestion",
            "eligibility_basis",
            "qa_stratum_id",
            "qa_stratum_size",
            "qa_selection_rank",
            "qa_selection_sha256",
            *QA_EVIDENCE_FIELDS,
            *FINAL_EXCLUSION_QA_FIELDS,
        ],
    },
}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def project_git_commit(project_root: Path) -> str:
    """Return the short commit used to build a portable review artifact."""

    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def workspace_input_sha256(workspace_directory: Path) -> str:
    """Hash the protected manifest and current editable worklists in a stable order."""

    names = [
        WORKSPACE_MANIFEST_FILENAME,
        WORKSPACE_DOCUMENT_FILENAME,
        WORKSPACE_ADJUDICATION_FILENAME,
        WORKSPACE_EXCLUSION_QA_FILENAME,
    ]
    missing = [name for name in names if not (workspace_directory / name).exists()]
    if missing:
        raise ValueError(f"Workspace is missing required files: {', '.join(missing)}")
    return _sha256(
        b"\n".join(
            name.encode("utf-8") + b":" + (workspace_directory / name).read_bytes()
            for name in names
        )
    )


def _load_queue(workspace_directory: Path, queue_name: str) -> pd.DataFrame:
    spec = QUEUE_SPECS[queue_name]
    frame = pd.read_csv(
        workspace_directory / spec["filename"],
        dtype=str,
        keep_default_na=False,
    )
    required = set(spec["display_fields"]) - set(spec.get("derived_fields", []))
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{queue_name} queue is missing columns: {sorted(missing)}")
    key = spec["id_field"]
    if frame[key].eq("").any() or frame[key].duplicated().any():
        raise ValueError(f"{queue_name} queue has blank or duplicate {key} values")
    return frame


def enrich_exclusion_qa_evidence(
    exclusion_qa: pd.DataFrame,
    adjudications: pd.DataFrame,
) -> pd.DataFrame:
    """Attach protected decision evidence to every QA row by exact document ID."""

    required = {"document_id", "adjudication_instance_id", *QA_EVIDENCE_FIELDS}
    missing = required - set(adjudications.columns)
    if missing:
        raise ValueError(f"Adjudication evidence is missing columns: {sorted(missing)}")
    evidence = adjudications[
        ["document_id", "adjudication_instance_id", *QA_EVIDENCE_FIELDS]
    ].copy()
    duplicate_documents = evidence["document_id"].duplicated(keep=False)
    if duplicate_documents.any():
        inconsistent = []
        for document_id, group in evidence.loc[duplicate_documents].groupby("document_id"):
            if any(group[field].nunique(dropna=False) > 1 for field in QA_EVIDENCE_FIELDS):
                inconsistent.append(document_id)
        if inconsistent:
            raise ValueError(
                "Split adjudication instances disagree on protected QA evidence: "
                + ", ".join(sorted(inconsistent))
            )
    evidence = (
        evidence.sort_values("adjudication_instance_id", kind="stable")
        .drop_duplicates("document_id", keep="first")
        .drop(columns="adjudication_instance_id")
    )
    base = exclusion_qa.drop(columns=QA_EVIDENCE_FIELDS, errors="ignore")
    enriched = base.merge(evidence, on="document_id", how="left", validate="many_to_one")
    missing_documents = enriched.loc[enriched["fact_text"].isna(), "document_id"].tolist()
    if missing_documents:
        raise ValueError(
            "Exclusion-QA rows lack linked adjudication evidence: "
            + ", ".join(missing_documents)
        )
    enriched[QA_EVIDENCE_FIELDS] = enriched[QA_EVIDENCE_FIELDS].fillna("")
    return enriched


def _review_summary(frame: pd.DataFrame) -> dict[str, int]:
    statuses = frame["review_status"].str.strip()
    complete = statuses.isin(COMPLETE_REVIEW_STATUSES)
    first_pass = statuses.eq("single_coded_pending_human")
    return {
        "total": int(len(frame)),
        "review_complete": int(complete.sum()),
        "first_pass_pending_human": int(first_pass.sum()),
        "unstarted": int(statuses.eq("").sum()),
        "other_unresolved": int((~complete & ~first_pass & statuses.ne("")).sum()),
    }


def _records(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, str]]:
    return frame[columns].astype(str).to_dict(orient="records")


def build_review_explorer_payload(
    workspace_directory: Path,
    *,
    validation: pd.DataFrame | None = None,
    git_commit: str = "unavailable",
) -> dict[str, Any]:
    """Build a source-linked payload for the complete review workspace."""

    manifest_path = workspace_directory / WORKSPACE_MANIFEST_FILENAME
    if not manifest_path.exists():
        raise ValueError(f"Missing workspace manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("workspace_id") != workspace_directory.name:
        raise ValueError(
            "Workspace directory name does not match the protected workspace manifest"
        )

    frames = {name: _load_queue(workspace_directory, name) for name in QUEUE_SPECS}
    frames["exclusion_qa"] = enrich_exclusion_qa_evidence(
        frames["exclusion_qa"], frames["adjudications"]
    )
    summaries = {name: _review_summary(frame) for name, frame in frames.items()}
    total = sum(item["total"] for item in summaries.values())
    complete = sum(item["review_complete"] for item in summaries.values())
    current_digest = workspace_input_sha256(workspace_directory)

    controls: list[dict[str, str]] = []
    if validation is not None:
        controls = validation.astype(str).to_dict(orient="records")
    payload = {
        "metadata": {
            "schema_version": REVIEW_EXPLORER_SCHEMA_VERSION,
            "title": "F1 Stewarding Full-Corpus Review Console",
            "release_status": (
                "workspace_review_complete_pending_feature_controls"
                if complete == total
                else "blocked_pending_human_review"
            ),
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "git_commit": git_commit,
            "workspace_id": manifest["workspace_id"],
            "workspace_schema_version": manifest.get("schema_version", ""),
            "protected_seed_manifest_sha256": manifest.get(
                "protected_seed_manifest_sha256", ""
            ),
            "timing_context_sha256": manifest.get("timing_context_sha256", ""),
            "starter_workspace_content_sha256": manifest.get(
                "workspace_content_sha256", ""
            ),
            "current_workspace_sha256": current_digest,
            "review_target_count": total,
            "review_complete_count": complete,
            "interpretation_boundary": manifest.get("interpretation_boundary", ""),
        },
        "queue_summaries": summaries,
        "queue_specs": {
            name: {
                "id_field": spec["id_field"],
                "editable_fields": spec["editable_fields"],
            }
            for name, spec in QUEUE_SPECS.items()
        },
        "queues": {
            name: _records(frame, QUEUE_SPECS[name]["display_fields"])
            for name, frame in frames.items()
        },
        "validation_controls": controls,
    }
    validate_review_explorer_payload(payload)
    return payload


def validate_review_explorer_payload(payload: dict[str, Any]) -> None:
    """Fail closed on incomplete source lineage or unsafe analytical claims."""

    metadata = payload.get("metadata", {})
    if metadata.get("schema_version") != REVIEW_EXPLORER_SCHEMA_VERSION:
        raise ValueError("Unexpected review explorer schema version")
    if metadata.get("release_status") not in {
        "blocked_pending_human_review",
        "workspace_review_complete_pending_feature_controls",
    }:
        raise ValueError("Review explorer cannot publish an analytical release status")
    if any("nationality" in key.casefold() for key in metadata):
        raise ValueError("Nationality effect fields are not permitted in the review console")

    for queue_name, rows in payload.get("queues", {}).items():
        spec = QUEUE_SPECS.get(queue_name)
        if spec is None:
            raise ValueError(f"Unknown review queue: {queue_name}")
        seen: set[str] = set()
        for row in rows:
            row_id = str(row.get(spec["id_field"], ""))
            if not row_id or row_id in seen:
                raise ValueError(f"Blank or duplicate review row ID in {queue_name}")
            seen.add(row_id)
            source_url = str(row.get("source_url", ""))
            if not source_url.startswith("https://www.fia.com/"):
                raise ValueError(f"Missing official FIA source URL for {row_id}")
            if any("nationality" in key.casefold() for key in row):
                raise ValueError("Nationality fields are not permitted in review queue rows")


def _safe_json(payload: dict[str, Any]) -> str:
    return (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def render_review_explorer_html(payload: dict[str, Any]) -> str:
    """Render a dependency-free, keyboard-accessible review console."""

    validate_review_explorer_payload(payload)
    data = _safe_json(payload)
    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>F1 Stewarding Full-Corpus Review Console</title>
<style>
:root{--ink:#182026;--muted:#5d6871;--paper:#f5f2eb;--panel:#fff;--line:#d7d2c7;--red:#c9362b;--blue:#183a5a;--gold:#c08b2d;--focus:#087ea4}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--paper);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}a{color:#0b5c8e}a:focus,button:focus,input:focus,select:focus,textarea:focus,summary:focus{outline:3px solid var(--focus);outline-offset:2px}.mast{padding:32px max(24px,calc((100vw - 1440px)/2));color:white;background:linear-gradient(120deg,var(--blue),#0c253b)}.eyebrow{letter-spacing:.12em;text-transform:uppercase;color:#f4ca76;font-weight:800}.mast h1{margin:.25rem 0;font-size:clamp(1.9rem,4vw,3rem)}.mast p{max-width:900px}.status{display:inline-block;padding:.3rem .65rem;border:1px solid #f4ca76;border-radius:999px;color:#ffe4aa;font-weight:800}.shell{max-width:1440px;margin:auto;padding:24px}.warning{padding:16px 18px;border-left:6px solid var(--gold);background:#fff8e9}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:18px 0}.card{padding:16px;background:var(--panel);border:1px solid var(--line);border-radius:8px}.card strong{display:block;font-size:1.6rem}.card span{color:var(--muted)}.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:24px 0 12px}.tabs button{border:1px solid var(--line);background:white;padding:10px 14px;border-radius:6px;font-weight:700}.tabs button[aria-selected=true]{background:var(--blue);color:white}.toolbar{display:grid;grid-template-columns:minmax(240px,2fr) repeat(3,minmax(130px,1fr));gap:10px;padding:14px;background:white;border:1px solid var(--line);border-radius:8px}.toolbar label{font-weight:700}.toolbar input,.toolbar select{display:block;width:100%;margin-top:4px;padding:8px;border:1px solid #aaa;border-radius:4px}.actions{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.actions button,.pager button{padding:8px 12px;border:1px solid var(--blue);border-radius:5px;background:white;color:var(--blue);font-weight:700}.actions button.primary{background:var(--blue);color:white}.actions button:disabled{opacity:.5}.count{font-weight:700}.table-wrap{overflow:auto;background:white;border:1px solid var(--line);border-radius:8px}table{border-collapse:collapse;width:100%;min-width:980px}th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{position:sticky;top:0;background:#ece8df;z-index:1}code{font-size:.8rem;overflow-wrap:anywhere}.pill{display:inline-block;padding:.15rem .45rem;border-radius:999px;background:#e7edf2;font-size:.8rem;font-weight:700}.muted{color:var(--muted)}details{max-width:740px}summary{cursor:pointer;font-weight:800}.evidence{margin:10px 0;padding:10px;background:#f7f8fa;border-left:3px solid #8ca0af;white-space:pre-wrap}.evidence b{display:block;margin-bottom:4px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}.field{padding:8px;background:#f8f5ef;border:1px solid var(--line);border-radius:5px}.field b{display:block;font-size:.8rem;color:var(--muted)}.edit-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;padding:12px;margin-top:12px;border:2px solid #acc1d1;border-radius:7px;background:#f4f9fc}.edit-grid label{font-weight:700}.edit-grid input,.edit-grid select,.edit-grid textarea{display:block;width:100%;padding:7px;margin-top:3px;border:1px solid #9ba8b0;border-radius:4px}.edit-grid textarea{min-height:80px}.drafted{box-shadow:inset 4px 0 var(--gold)}.pager{display:flex;align-items:center;justify-content:space-between;margin:12px 0}.empty{padding:32px;text-align:center;color:var(--muted)}.lineage{display:grid;grid-template-columns:minmax(220px,1fr) 3fr;gap:0;background:white;border:1px solid var(--line)}.lineage dt,.lineage dd{margin:0;padding:10px;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.lineage dt{font-weight:800;background:#ece8df}.pass{color:#176d3b}.fail{color:#a61f18}.screen-reader{position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden}@media(max-width:800px){.toolbar{grid-template-columns:1fr 1fr}.lineage{grid-template-columns:1fr}.shell{padding:14px}}
</style>
</head>
<body>
<header class="mast"><div class="eyebrow">Oversight-style evidence review</div><h1>F1 Stewarding Full-Corpus Review Console</h1><span class="status" id="release-status"></span><p>Official FIA evidence, machine suggestions, timing-quality context, and protected final-coding fields for the 2018–2025 study population.</p></header>
<main class="shell">
<section class="warning"><strong>This is a review instrument, not a results release.</strong> Machine suggestions do not establish fault, harm, consistency, nationality effects, or fairness. Drafts stay in this browser until exported as a ledger and applied through the validated command-line workflow.</section>
<section class="cards" id="summary-cards" aria-label="Review progress"></section>
<nav class="tabs" role="tablist" aria-label="Review queues">
<button role="tab" aria-selected="true" data-tab="documents">Document dispositions</button>
<button role="tab" aria-selected="false" data-tab="adjudications">Adjudication coding</button>
<button role="tab" aria-selected="false" data-tab="exclusion_qa">Exclusion QA</button>
<button role="tab" aria-selected="false" data-tab="lineage">Lineage &amp; controls</button>
<button role="tab" aria-selected="false" data-tab="instructions">Workflow</button>
</nav>
<section id="queue-panel" role="tabpanel">
<div class="toolbar">
<label>Search<input id="search" type="search" placeholder="ID, event, driver, title, evidence…"></label>
<label>Season<select id="season"><option value="">All</option></select></label>
<label>Priority<select id="priority"><option value="">All</option></select></label>
<label>Review status<select id="review-status"><option value="">All</option></select></label>
</div>
<div class="actions"><button id="reset">Reset filters</button><button id="download-csv">Download filtered CSV</button><button class="primary" id="download-ledger">Export draft ledger (<span id="draft-count">0</span>)</button><span class="count" id="filter-count" aria-live="polite"></span></div>
<div class="table-wrap" id="review-table"></div><div class="pager" id="pager"></div>
</section>
<section id="lineage-panel" role="tabpanel" hidden><h2>Content-addressed lineage</h2><dl class="lineage" id="lineage"></dl><h2>Workspace validation</h2><div class="table-wrap" id="controls"></div></section>
<section id="instructions-panel" role="tabpanel" hidden><h2>Controlled review sequence</h2><ol><li>Filter by the frozen review order and open the official FIA source.</li><li>Compare the source with the protected suggestion and evidence text.</li><li>Complete only the final fields. Use <code>single_coded_pending_human</code> for a first pass; use <code>double_coded</code> or <code>adjudicated</code> only under the documented independent-review protocol.</li><li>Export the draft ledger. It contains only changed editable fields and is locked to this workspace hash.</li><li>Apply it with <code>f1stewards apply-full-corpus-review-ledger</code>. The command writes a separate workspace and runs protected-lineage validation.</li><li>Rebuild this console from the edited workspace. Analytical release remains separately gated by <code>build-analysis-features</code>.</li></ol><p><strong>Multi-decision documents:</strong> the browser ledger edits existing instances only. Use the documented CSV split procedure for a source that requires <code>-02</code> or later instances, then validate and rebuild the console.</p></section>
</main>
<script id="review-data" type="application/json">__PAYLOAD__</script>
<script>
const DATA=JSON.parse(document.getElementById('review-data').textContent);const PAGE_SIZE=50;let queue='documents',page=1,filtered=[];
const Q={documents:{name:'Document dispositions',id:'document_review_id',cols:['workspace_review_order','event_name','title','eligibility_suggestion','review_status']},adjudications:{name:'Adjudication coding',id:'adjudication_instance_id',cols:['workspace_review_order','event_name','driver_name_suggestion','offence_family_suggestion','outcome_family_suggestion','review_status']},exclusion_qa:{name:'Exclusion QA',id:'exclusion_qa_id',cols:['workspace_review_order','event_name','qa_stratum_id','eligibility_basis','review_status']}};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const label=v=>String(v??'').replaceAll('_',' ');const draftKey='f1stewards-review:'+DATA.metadata.workspace_id+':'+DATA.metadata.current_workspace_sha256;
let EDITS={};try{EDITS=JSON.parse(localStorage.getItem(draftKey)||'{}')}catch(e){EDITS={}};
function saveDrafts(){try{localStorage.setItem(draftKey,JSON.stringify(EDITS))}catch(e){}draftCount()}
function draftCount(){let n=0;Object.values(EDITS).forEach(rows=>Object.values(rows).forEach(fields=>n+=Object.keys(fields).length));document.getElementById('draft-count').textContent=n;document.getElementById('download-ledger').disabled=n===0}
function cards(){const s=DATA.queue_summaries,m=DATA.metadata;document.getElementById('release-status').textContent=label(m.release_status);document.getElementById('summary-cards').innerHTML=Object.entries(s).map(([k,v])=>`<div class="card"><strong>${v.review_complete} / ${v.total}</strong><span>${esc(Q[k].name)} independently complete<br>${v.first_pass_pending_human} first-pass pending · ${v.unstarted} unstarted</span></div>`).join('')+`<div class="card"><strong>${m.review_complete_count} / ${m.review_target_count}</strong><span>all review targets complete</span></div>`}
function setTab(button){document.querySelectorAll('[role=tab]').forEach(b=>{const on=b===button;b.setAttribute('aria-selected',on);b.tabIndex=on?0:-1});const tab=button.dataset.tab;document.getElementById('queue-panel').hidden=!Q[tab];document.getElementById('lineage-panel').hidden=tab!=='lineage';document.getElementById('instructions-panel').hidden=tab!=='instructions';if(Q[tab]){queue=tab;page=1;makeFilters();render()}}
document.querySelectorAll('[role=tab]').forEach(b=>{b.addEventListener('click',()=>setTab(b));b.addEventListener('keydown',e=>{const tabs=[...document.querySelectorAll('[role=tab]')],i=tabs.indexOf(b);let j;if(e.key==='ArrowRight')j=(i+1)%tabs.length;else if(e.key==='ArrowLeft')j=(i-1+tabs.length)%tabs.length;else return;e.preventDefault();setTab(tabs[j]);tabs[j].focus()})});
function makeOptions(id,values){const el=document.getElementById(id),first=el.options[0];el.innerHTML='';el.append(first);[...new Set(values.filter(Boolean))].sort().forEach(v=>el.add(new Option(label(v),v)))}
function makeFilters(){const rows=DATA.queues[queue];document.getElementById('search').value='';makeOptions('season',rows.map(r=>r.season));makeOptions('priority',rows.map(r=>r.workspace_priority_bucket));makeOptions('review-status',rows.map(r=>r.review_status||'(blank)'))}
function fieldValue(row,field){return EDITS[queue]?.[row[Q[queue].id]]?.[field]??row[field]??''}
function inputFor(row,field){const id=row[Q[queue].id],value=fieldValue(row,field),attrs=`data-row="${esc(id)}" data-field="${esc(field)}"`;if(field==='review_status')return `<select ${attrs}><option value=""></option>${['single_coded_pending_human','double_coded','adjudicated'].map(v=>`<option value="${v}" ${value===v?'selected':''}>${label(v)}</option>`).join('')}</select>`;if(field==='fault_language_final')return `<select ${attrs}><option value=""></option>${['wholly_to_blame','predominantly_to_blame','mainly_at_fault','shared_fault','racing_incident','no_conclusion','not_applicable'].map(v=>`<option value="${v}" ${value===v?'selected':''}>${label(v)}</option>`).join('')}</select>`;if(['include_primary_final','include_secondary_final'].includes(field))return `<select ${attrs}><option value=""></option>${['true','false'].map(v=>`<option value="${v}" ${String(value).toLowerCase()===v?'selected':''}>${v}</option>`).join('')}</select>`;if(field.includes('notes')||field.includes('reason'))return `<textarea ${attrs}>${esc(value)}</textarea>`;return `<input ${attrs} value="${esc(value)}">`}
function evidence(row){if(!['adjudications','exclusion_qa'].includes(queue))return '';return ['fact_text','infringement_text','decision_text','reason_text'].map(k=>`<div class="evidence"><b>${label(k)}</b>${esc(row[k]||'Not available')}</div>`).join('')}
function fields(row){const omit=new Set([Q[queue].id,'source_url','title','event_name','season','workspace_review_order','review_status','fact_text','infringement_text','decision_text','reason_text',...DATA.queue_specs[queue].editable_fields]);return Object.entries(row).filter(([k,v])=>!omit.has(k)&&v!=='').map(([k,v])=>`<div class="field"><b>${esc(label(k))}</b>${esc(v)}</div>`).join('')}
function details(row){const id=row[Q[queue].id],editable=DATA.queue_specs[queue].editable_fields;return `<details><summary>Inspect evidence and final fields</summary><p><a href="${esc(row.source_url)}" target="_blank" rel="noreferrer">Open official FIA source</a> · <code>${esc(id)}</code></p><div class="grid">${fields(row)}</div>${evidence(row)}<div class="edit-grid">${editable.map(f=>`<label>${esc(label(f))}${inputFor(row,f)}</label>`).join('')}</div></details>`}
function activeRows(){const search=document.getElementById('search').value.trim().toLowerCase(),season=document.getElementById('season').value,priority=document.getElementById('priority').value,status=document.getElementById('review-status').value;return DATA.queues[queue].filter(r=>(!search||Object.values(r).some(v=>String(v).toLowerCase().includes(search)))&&(!season||r.season===season)&&(!priority||r.workspace_priority_bucket===priority)&&(!status||(status==='(blank)'?!r.review_status:r.review_status===status)))}
function render(){filtered=activeRows();const pages=Math.max(1,Math.ceil(filtered.length/PAGE_SIZE));page=Math.min(page,pages);const rows=filtered.slice((page-1)*PAGE_SIZE,page*PAGE_SIZE),config=Q[queue];document.getElementById('filter-count').textContent=`Showing ${rows.length} on page ${page} of ${pages}; ${filtered.length} of ${DATA.queues[queue].length} rows match.`;if(!rows.length){document.getElementById('review-table').innerHTML='<p class="empty">No rows match the selected filters.</p>'}else{document.getElementById('review-table').innerHTML=`<table><caption class="screen-reader">${esc(config.name)} review rows</caption><thead><tr>${config.cols.map(c=>`<th scope="col">${esc(label(c))}</th>`).join('')}<th scope="col">Evidence and coding</th></tr></thead><tbody>${rows.map(r=>`<tr class="${EDITS[queue]?.[r[config.id]]?'drafted':''}">${config.cols.map(c=>`<td>${c==='review_status'?`<span class="pill">${esc(label(fieldValue(r,c)||'unstarted'))}</span>`:esc(r[c])}</td>`).join('')}<td>${details(r)}</td></tr>`).join('')}</tbody></table>`}document.querySelectorAll('[data-field]').forEach(el=>el.addEventListener('change',edit));document.getElementById('pager').innerHTML=`<button id="prev" ${page===1?'disabled':''}>Previous</button><span>Page ${page} of ${pages}</span><button id="next" ${page===pages?'disabled':''}>Next</button>`;document.getElementById('prev').onclick=()=>{page--;render();scrollTo(0,document.querySelector('.tabs').offsetTop)};document.getElementById('next').onclick=()=>{page++;render();scrollTo(0,document.querySelector('.tabs').offsetTop)}}
function edit(e){const id=e.target.dataset.row,field=e.target.dataset.field,row=DATA.queues[queue].find(r=>r[Q[queue].id]===id),value=e.target.value,base=row[field]??'';EDITS[queue]??={};EDITS[queue][id]??={};if(value===base)delete EDITS[queue][id][field];else EDITS[queue][id][field]=value;if(!Object.keys(EDITS[queue][id]).length)delete EDITS[queue][id];if(!Object.keys(EDITS[queue]).length)delete EDITS[queue];saveDrafts()}
['search','season','priority','review-status'].forEach(id=>document.getElementById(id).addEventListener(id==='search'?'input':'change',()=>{page=1;render()}));document.getElementById('reset').onclick=()=>{makeFilters();page=1;render()};
function download(name,text,type){const a=document.createElement('a'),url=URL.createObjectURL(new Blob([text],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),0)}
document.getElementById('download-csv').onclick=()=>{if(!filtered.length)return;const keys=Object.keys(filtered[0]),lines=[keys.join(','),...filtered.map(r=>keys.map(k=>'"'+String(fieldValue(r,k)??'').replaceAll('"','""')+'"').join(','))];download(`${queue}_filtered_review_rows.csv`,lines.join('\n'),'text/csv')};
document.getElementById('download-ledger').onclick=()=>{const changes={};Object.entries(EDITS).forEach(([q,rows])=>changes[q]=Object.entries(rows).map(([row_id,fields])=>({row_id,fields})));const ledger={schema_version:'full-corpus-review-ledger-v1',workspace_id:DATA.metadata.workspace_id,source_workspace_sha256:DATA.metadata.current_workspace_sha256,exported_at_utc:new Date().toISOString(),changes};download(`${DATA.metadata.workspace_id}_review_ledger.json`,JSON.stringify(ledger,null,2)+'\n','application/json')};
function lineage(){const m=DATA.metadata,items=[['Workspace ID',m.workspace_id],['Review-console schema',m.schema_version],['Workspace schema',m.workspace_schema_version],['Current workspace SHA-256',m.current_workspace_sha256],['Starter content SHA-256',m.starter_workspace_content_sha256],['Protected seed manifest SHA-256',m.protected_seed_manifest_sha256],['Timing context SHA-256',m.timing_context_sha256],['Git commit',m.git_commit],['Generated UTC',m.generated_at_utc],['Interpretation boundary',m.interpretation_boundary]];document.getElementById('lineage').innerHTML=items.map(([k,v])=>`<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');const rows=DATA.validation_controls;document.getElementById('controls').innerHTML=rows.length?`<table><thead><tr><th>Control</th><th>Status</th><th>Detail</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.control)}</td><td class="${r.status==='pass'?'pass':'fail'}">${esc(r.status)}</td><td>${esc(r.detail||r.actual_sha256||'')}</td></tr>`).join('')}</tbody></table>`:'<p class="empty">No external validation controls were supplied to this build.</p>'}
cards();makeFilters();render();lineage();draftCount();
</script>
</body>
</html>
"""
    return template.replace("__PAYLOAD__", data)


def write_review_explorer(payload: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_review_explorer_html(payload), encoding="utf-8")


def apply_review_ledger(
    workspace_directory: Path,
    ledger_path: Path,
    output_root: Path,
) -> tuple[Path, dict[str, int]]:
    """Apply editable-field deltas to a separate workspace copy with stale-input protection."""

    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if ledger.get("schema_version") != REVIEW_LEDGER_SCHEMA_VERSION:
        raise ValueError("Unexpected review-ledger schema version")
    if ledger.get("workspace_id") != workspace_directory.name:
        raise ValueError("Review ledger workspace ID does not match the source workspace")
    current_digest = workspace_input_sha256(workspace_directory)
    if ledger.get("source_workspace_sha256") != current_digest:
        raise ValueError("Review ledger is stale for the current workspace content")

    changes = ledger.get("changes", {})
    unknown_queues = set(changes) - set(QUEUE_SPECS)
    if unknown_queues:
        raise ValueError(f"Review ledger contains unknown queues: {sorted(unknown_queues)}")

    output_directory = output_root / workspace_directory.name
    if output_directory.exists():
        raise FileExistsError(f"Refusing to overwrite review workspace: {output_directory}")
    output_directory.mkdir(parents=True)
    for filename in (
        WORKSPACE_MANIFEST_FILENAME,
        WORKSPACE_DOCUMENT_FILENAME,
        WORKSPACE_ADJUDICATION_FILENAME,
        WORKSPACE_EXCLUSION_QA_FILENAME,
    ):
        shutil.copy2(workspace_directory / filename, output_directory / filename)

    # A review workspace is still a descendant of the machine-assisted first pass. Carry its
    # immutable audit and manifest through every edit round so downstream exception packets can
    # reconstruct why an unresolved row was originally withheld. The chain manifest records each
    # content-addressed delta without changing the protected workspace digest definition.
    for filename in (FIRST_PASS_MANIFEST_FILENAME, FIRST_PASS_AUDIT_FILENAME):
        source = workspace_directory / filename
        if source.exists():
            shutil.copy2(source, output_directory / filename)

    applied: dict[str, int] = {name: 0 for name in QUEUE_SPECS}
    try:
        for queue_name, modifications in changes.items():
            spec = QUEUE_SPECS[queue_name]
            path = output_directory / spec["filename"]
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
            key = spec["id_field"]
            lookup = {value: index for index, value in frame[key].items()}
            seen: set[str] = set()
            for change in modifications:
                row_id = str(change.get("row_id", ""))
                if not row_id or row_id in seen:
                    raise ValueError(f"Blank or duplicate ledger row ID in {queue_name}")
                seen.add(row_id)
                if row_id not in lookup:
                    raise ValueError(f"Unknown {queue_name} review row ID: {row_id}")
                fields = change.get("fields", {})
                unknown_fields = set(fields) - set(spec["editable_fields"])
                if unknown_fields:
                    raise ValueError(
                        f"Ledger attempts protected-field edits in {queue_name}: "
                        f"{sorted(unknown_fields)}"
                    )
                for field, value in fields.items():
                    if isinstance(value, (dict, list)):
                        raise ValueError(f"Ledger field {field} must contain a scalar value")
                    frame.at[lookup[row_id], field] = "" if value is None else str(value)
                    applied[queue_name] += 1
            frame.to_csv(path, index=False, lineterminator="\n")

        chain_path = workspace_directory / REVIEW_CHAIN_MANIFEST_FILENAME
        first_pass_path = workspace_directory / FIRST_PASS_MANIFEST_FILENAME
        chain: dict[str, Any] | None = None
        if chain_path.exists():
            chain = json.loads(chain_path.read_text(encoding="utf-8"))
            if chain.get("schema_version") != REVIEW_CHAIN_SCHEMA_VERSION:
                raise ValueError("Unexpected review-chain schema version")
            if chain.get("workspace_id") != workspace_directory.name:
                raise ValueError("Review-chain workspace ID does not match source workspace")
            if chain.get("current_workspace_sha256") != current_digest:
                raise ValueError("Review chain is stale for the current source workspace")
        elif first_pass_path.exists():
            first_pass = json.loads(first_pass_path.read_text(encoding="utf-8"))
            base_digest = str(first_pass.get("output_workspace_sha256", ""))
            if base_digest != current_digest:
                raise ValueError("First-pass manifest is stale for the review source workspace")
            chain = {
                "schema_version": REVIEW_CHAIN_SCHEMA_VERSION,
                "workspace_id": workspace_directory.name,
                "first_pass_id": first_pass.get("first_pass_id"),
                "base_workspace_sha256": base_digest,
                "steps": [],
            }
        if chain is not None:
            output_digest = workspace_input_sha256(output_directory)
            chain["steps"] = [
                *chain.get("steps", []),
                {
                    "parent_workspace_sha256": current_digest,
                    "ledger_sha256": _sha256(ledger_path.read_bytes()),
                    "output_workspace_sha256": output_digest,
                    "applied_field_counts": applied,
                },
            ]
            chain["current_workspace_sha256"] = output_digest
            (output_directory / REVIEW_CHAIN_MANIFEST_FILENAME).write_text(
                json.dumps(chain, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    except Exception:
        shutil.rmtree(output_directory)
        raise
    return output_directory, applied
