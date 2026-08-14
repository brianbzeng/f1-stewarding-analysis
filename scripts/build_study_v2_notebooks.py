"""Build the six executable Study v2 notebooks and integrated status report."""

# ruff: noqa: E501

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import nbformat

from f1stewards.integrated_report_notebook import build_integrated_report_cells

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS = ROOT / "notebooks"
STUDY_V2_NOTEBOOKS = [
    NOTEBOOKS / f"{number:02d}_{name}.ipynb"
    for number, name in (
        (7, "study_v2_protocol_and_review"),
        (8, "study_v2_referral_and_context"),
        (9, "study_v2_close_cases"),
        (10, "study_v2_damage_and_harm"),
        (11, "study_v2_nationality"),
        (12, "study_v2_report"),
    )
]


def markdown(source: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_markdown_cell(source.strip())


def code(source: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_code_cell(source.strip())


SETUP = """
# ruff: noqa: E402
import json
import os
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "pyproject.toml").exists():
    ROOT = ROOT.parent
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".jupyter" / "mplconfig"))

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import HTML, Markdown, display

STRICT = ROOT / "data/manual/study_v2_strict_model_audit/strict-model-audit-0fe15fd6b052"
REVIEW = ROOT / "data/manual/study_v2_review_packets/study-v2-review-7cb1b29b5251"
REFERRAL = ROOT / "data/manual/study_v2_referrals/referrals-a4f9bd038101"
CLOCK = ROOT / "data/manual/study_v2_incident_clock/incident-clock-3dc8bb350308"
CONTEXT = ROOT / "data/manual/study_v2_incident_context/incident-context-707a44aafeb4"
CLOSE = ROOT / "data/manual/study_v2_close_cases/close-cases-b175fe03fa80"
DAMAGE = ROOT / "data/manual/study_v2_damage/damage-screening-23c77a57134e"
LAYERS = ROOT / "data/manual/study_v2_layers/study-v2-layers-eed6774fb6c5"
NATIONALITY = ROOT / "data/manual/study_v2_nationality/nationality-diagnostic-2b1b0ffdd961"
GENERATED = ROOT / "reports/generated/study_v2"
GENERATED.mkdir(parents=True, exist_ok=True)
"""


def write(name: str, cells: list[nbformat.NotebookNode]) -> None:
    for index, cell in enumerate(cells):
        cell["id"] = hashlib.sha256(
            f"{name}:{index}:{cell.cell_type}".encode()
        ).hexdigest()[:8]
    notebook = nbformat.v4.new_notebook(
        cells=cells,
        metadata={
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11"},
        },
    )
    nbformat.write(notebook, NOTEBOOKS / name)


def build() -> None:
    write(
        "07_study_v2_protocol_and_review.ipynb",
        [
            markdown(
                """
# Study v2: protocol and source audit

This notebook checks the frozen design, the strict GPT-5.6 Sol source audit, and the separate packet
reserved for a future independent human audit. The model audit never writes into the human ledgers
and is not presented as inter-rater agreement.
"""
            ),
            code(SETUP),
            code(
                """
strict_manifest = json.loads((STRICT / "manifest.json").read_text(encoding="utf-8"))
strict_cases = pd.read_csv(STRICT / "strict_model_case_audit.csv", keep_default_na=False)
manifest = json.loads((REVIEW / "manifest.json").read_text(encoding="utf-8"))
review_summary = pd.DataFrame(
    [
        {"packet": "Strict model audit: included decisions", "rows": strict_manifest["included_decisions"]},
        {"packet": "Strict model audit: exclusion checks", "rows": strict_manifest["exclusion_sources"]},
        {"packet": "Strict model audit: corrected included rows", "rows": strict_manifest["corrected_included_rows"]},
        {"packet": "Strict model audit: unavailable public sources", "rows": strict_manifest["model_status_counts"]["model_unresolved_public_evidence"]},
        {"packet": "Reviewer A", "rows": manifest["reviewer_a_rows"]},
        {"packet": "Reviewer B", "rows": manifest["reviewer_b_rows"]},
        {"packet": "Reconciliation queue", "rows": len(pd.read_csv(REVIEW / "reconciliation_queue.csv"))},
    ]
)
display(review_summary)
assert manifest["blind_to_model_final_fields"] is True
assert manifest.get("independent_human_review_complete", False) is False
assert strict_manifest["records_with_fia_citation"] == 920
assert strict_manifest["pending_adversarial"] == 0
assert strict_cases["review_disclosure"].eq("model_led_source_review_not_independent_human_annotation").all()
"""
            ),
            markdown(
                """
The strict audit covers all 418 included decisions and 502 sampled exclusions. Every record carries
an exact FIA source URL. Thirty-two included rows changed after source review: seven fault labels
and 25 affected-driver lists. Four archive labels remain publicly unavailable and are kept as
unresolved evidence rather than guessed.

Reviewer A and Reviewer B remain blank, blind packets for anyone who later wants independent human
validation. They are not a hidden requirement for reading this model-led portfolio report.
"""
            ),
        ],
    )
    write(
        "08_study_v2_referral_and_context.ipynb",
        [
            markdown(
                """
# Study v2: referral funnel and incident timing

Formal decisions show what reached the stewards. Public Race Control messages add part of the path
from noted, to investigated, to decided. The feed is still not the universe of every on-track act.
"""
            ),
            code(SETUP),
            code(
                """
referral_manifest = json.loads((REFERRAL / "manifest.json").read_text(encoding="utf-8"))
clock_manifest = json.loads((CLOCK / "manifest.json").read_text(encoding="utf-8"))
context_manifest = json.loads((CONTEXT / "manifest.json").read_text(encoding="utf-8"))
funnel = pd.read_csv(REFERRAL / "referral_funnel.csv")
display(funnel)
display(pd.DataFrame([referral_manifest, clock_manifest, context_manifest]).T)
assert referral_manifest["high_confidence_link_count"] == 177
assert clock_manifest["known_validation_contained_count"] == 31
assert clock_manifest["known_validation_case_count"] == 31
"""
            ),
            code(
                """
plot = funnel.sort_values("count", ascending=True)
ax = plot.plot.barh(x="stage", y="count", legend=False, figsize=(8, 4.8))
ax.set(title="Visible Race Control funnel", xlabel="Records")
plt.tight_layout()
plt.savefig(GENERATED / "referral_funnel.png", dpi=160, bbox_inches="tight")
plt.show()
"""
            ),
            markdown(
                """
The clock mapping resolves 338 of 346 FIA incident times to a lap window. It contains all 31 cases
with a previously known lap. It produces 174 single-lap candidates and keeps wider windows as
uncertain. High-confidence referral links are usable descriptively; weaker links wait for review.
"""
            ),
        ],
    )
    write(
        "09_study_v2_close_cases.ipynb",
        [
            markdown(
                """
# Study v2: close-case matching

Close cases are matched without using fault, penalty, damage, retirement, or finishing position.
This avoids defining similarity with the outcome the study wants to compare.
"""
            ),
            code(SETUP),
            code(
                """
manifest = json.loads((CLOSE / "manifest.json").read_text(encoding="utf-8"))
summary = pd.read_csv(CLOSE / "conduct_neighbor_summary.csv")
edges = pd.read_csv(LAYERS / "close_case_outcome_contrasts.csv")
coverage = pd.DataFrame(
    [{
        "cases": len(summary),
        "cases_with_at_least_five_neighbors": int((summary["neighbor_count"] >= 5).sum()),
        "neighbor_edges": len(edges),
        "edges_with_different_sanction_outcome": int(edges["different_sanction_outcome"].sum()),
    }]
)
display(coverage)
display(edges.sort_values(["distance", "adjudication_instance_id"]).head(20))
assert "sanction_outcome" in manifest["outcome_fields_excluded_from_primary_match"]
"""
            ),
            markdown(
                """
There are 1,655 neighbor links, and 317 of 346 cases reach the five-neighbor support rule. Different
outcomes inside a matched pair are review leads, not proof of inconsistent stewarding. The context
fields and the pair itself still need human confirmation.
"""
            ),
        ],
    )
    write(
        "10_study_v2_damage_and_harm.ipynb",
        [
            markdown(
                """
# Study v2: damage and participant harm

The unit is one driver in one incident. A multi-car collision therefore has a separate record for
each participant. Timing decides what to research; it does not prove damage.
"""
            ),
            code(SETUP),
            code(
                """
damage_manifest = json.loads((DAMAGE / "manifest.json").read_text(encoding="utf-8"))
layer_manifest = json.loads((LAYERS / "manifest.json").read_text(encoding="utf-8"))
screen = pd.read_csv(DAMAGE / "harm_screening.csv")
pace = pd.read_csv(LAYERS / "persistent_pace_screen.csv")
evidence = pd.read_csv(DAMAGE / "damage_evidence_review_worklist.csv")
summary = pd.DataFrame([{
    "collision decision rows": damage_manifest["collision_decision_rows"],
    "candidate incidents": damage_manifest["candidate_incident_count"],
    "participant records": len(screen),
    "single-lap participant mappings": damage_manifest["participant_rows_with_incident_lap"],
    "pace candidates": len(pace),
    "estimable teammate-relative screens": layer_manifest["pace_screen_estimable_rows"],
    "model-researched sources awaiting review": len(evidence),
    "reviewed proportionality records": layer_manifest["proportionality_release_rows"],
}])
display(summary.T.rename(columns={0: "count"}))
display(evidence[["event_id", "participant_driver_number", "source_owner", "source_grade", "source_url", "independent_review_status"]])
"""
            ),
            code(
                """
estimated = pace.loc[pace["pace_screen_status"].str.startswith("estimable")].copy()
ax = estimated["pace_change_seconds_per_lap"].plot.hist(bins=12, figsize=(8, 4.5))
ax.axvline(0, color="black", linewidth=1)
ax.set(title="Teammate-relative pace changes are screening results", xlabel="Seconds per lap after minus before")
plt.tight_layout()
plt.savefig(GENERATED / "pace_screen_distribution.png", dpi=160, bbox_inches="tight")
plt.show()
"""
            ),
            markdown(
                """
Only 28 of 52 pace candidates have enough clean laps matched on the same lap to a teammate. Traffic,
tyres, strategy, weather, and hidden damage can still explain those changes. The four researched
source examples remain pending human confirmation. No population damage rate or proportionality
claim is released.
"""
            ),
        ],
    )
    write(
        "11_study_v2_nationality.ipynb",
        [
            markdown(
                """
# Study v2: gated nationality diagnostic

This notebook shows sample structure and power. It does not fit or release an adjusted nationality
effect because the prespecified release gate fails.
"""
            ),
            code(SETUP),
            code(
                """
gate = pd.read_csv(NATIONALITY / "release_gate.csv")
rates = pd.read_csv(NATIONALITY / "descriptive_rates.csv")
power = pd.read_csv(NATIONALITY / "simulation_power.csv")
overlap = pd.read_csv(NATIONALITY / "overlap_summary.csv")
display(rates)
display(gate.T.rename(columns={0: "value"}))
display(overlap.T.rename(columns={0: "value"}))
assert bool(gate.loc[0, "formal_effect_release_gate"]) is False
"""
            ),
            code(
                """
fig, ax = plt.subplots(figsize=(8, 4.8))
for baseline, group in power.groupby("baseline_probability"):
    ax.plot(group["target_risk_difference"] * 100, group["detection_power"] * 100, marker="o", label=f"Baseline {baseline:.0%}")
ax.axhline(80, color="black", linestyle="--", linewidth=1, label="80% target")
ax.set(title="Nationality design power", xlabel="Assumed sanction-rate difference (points)", ylabel="Power (%)", ylim=(0, 100))
ax.legend()
plt.tight_layout()
plt.savefig(GENERATED / "nationality_power_v2.png", dpi=160, bbox_inches="tight")
plt.show()
"""
            ),
            markdown(
                """
Measured overlap is usable, but there are only 44 British-accused cases versus the frozen minimum
of 98. At the target 15-point difference, simulated power ranges from 37.8% to 53.6%. Independent
review is also incomplete. The correct result is **inconclusive**, not evidence for or against bias.
"""
            ),
        ],
    )
    write(
        "12_study_v2_report.ipynb",
        [
            markdown(
                """
# The Cost of Discretion — Study v2

## A stronger way to study Formula 1 stewarding

Formal FIA decisions do not contain enough common detail to label every ruling fair or unfair.
Study v2 builds the missing structure: a source audit, a public Race Control funnel, incident-lap
windows, close-case matching, and one harm record per driver in a collision.

GPT-5.6 Sol reviewed every included decision and every sampled exclusion under a frozen protocol.
That is a model-led source audit, not independent human annotation. The report is ready as a
reproducible model-reviewed study, but it still withholds claims that need confirmed damage,
counterfactual race effects, or human inter-rater evidence.
"""
            ),
            code(SETUP),
            code(
                """
strict = json.loads((STRICT / "manifest.json").read_text(encoding="utf-8"))
strict_cases = pd.read_csv(STRICT / "strict_model_case_audit.csv", keep_default_na=False)
review = json.loads((REVIEW / "manifest.json").read_text(encoding="utf-8"))
referral = json.loads((REFERRAL / "manifest.json").read_text(encoding="utf-8"))
clock = json.loads((CLOCK / "manifest.json").read_text(encoding="utf-8"))
close = json.loads((CLOSE / "manifest.json").read_text(encoding="utf-8"))
damage = json.loads((DAMAGE / "manifest.json").read_text(encoding="utf-8"))
layers = json.loads((LAYERS / "manifest.json").read_text(encoding="utf-8"))
nationality = json.loads((NATIONALITY / "manifest.json").read_text(encoding="utf-8"))

status = pd.DataFrame([
    {"part": "Strict source audit", "built": f"{strict['included_decisions']} decisions + {strict['exclusion_sources']} exclusions", "release": "Complete; model-led and disclosed"},
    {"part": "Independent human packet", "built": f"{review['reviewer_a_rows']} A / {review['reviewer_b_rows']} B assignments", "release": "Optional future validation; still blank"},
    {"part": "Race Control referral links", "built": f"{referral['high_confidence_link_count']} high-confidence links", "release": "Descriptive"},
    {"part": "Incident clock mapping", "built": f"{clock['mapped_case_count']} of {clock['case_count']} cases", "release": "Validated candidate context"},
    {"part": "Close-case support", "built": f"{close['pre_review_minimum_support_count']} of {close['case_count']} cases", "release": "Review leads only"},
    {"part": "Collision harm records", "built": f"{damage['participant_record_count']} driver records", "release": "Screening only"},
    {"part": "Persistent pace", "built": f"{layers['pace_screen_estimable_rows']} estimable screens", "release": "Waiting for source/context review"},
    {"part": "Proportionality", "built": f"{layers['proportionality_release_rows']} release-ready rows", "release": "Withheld"},
    {"part": "Nationality", "built": f"{nationality['british_accused_rows']} British-accused cases", "release": "Inconclusive"},
])
display(status)
assert strict["records_with_fia_citation"] == strict["unique_sources"] == 920
assert strict["pending_adversarial"] == 0
"""
            ),
            markdown(
                """
## 1. What became stronger

**Every reviewed case now has a source.** The strict audit covers 418 included decisions and 502
sampled exclusions. All 920 records cite an exact FIA URL. It confirmed 884 records, corrected 32,
and left four unavailable archive labels visibly unresolved. It never fills the blank human-review
ledgers or calls the same model an independent reviewer.

**The audit changed data, not just wording.** Seven decisions had fault-language errors. Twenty-five
had a missing affected-driver list that the cited source could resolve. Affected-driver coverage
rose from 372 of 418 decisions to 397 of 418. The remaining 21 stay blank because the public source
does not identify a driver clearly enough.

**The population boundary is more visible.** The public timing feed contains 966 Race Control
episodes. Of 346 formal primary decisions, 177 link to an episode at high confidence. Candidate and
ambiguous links remain visible rather than being forced into the analysis.

**Incident timing is much better.** FIA local incident clocks map 338 of 346 cases into lap windows.
The method reproduces all 31 cases that already had a known lap. It gives 174 single-lap candidates;
wider windows remain uncertain.

**Similar cases are compared without looking at the result.** The matching process excludes fault,
penalty, damage, retirement, and finish. It finds at least five neighbors for 317 cases. A different
outcome inside a close pair is a reason to read both sources, not a finding that either ruling was
wrong.

**Harm now follows every participant.** The 233 collision decision rows reduce to 193 candidate
incidents and expand to 412 driver-level harm records. This handles chain collisions and different
types of harm to different drivers.
"""
            ),
            code(
                """
audit_status = (
    strict_cases.groupby(["review_scope", "strict_model_review_status"], dropna=False)
    .size()
    .rename("records")
    .reset_index()
)
corrections = strict_cases.loc[
    strict_cases["model_correction_fields"].ne(""),
    ["document_id", "event_name", "title", "model_correction_fields", "model_correction_rationale", "fia_decision_citation_url"],
]
display(audit_status)
display(corrections)
display(Markdown("[Download the full 920-row source-cited audit](../data/manual/study_v2_strict_model_audit/strict-model-audit-0fe15fd6b052/strict_model_case_audit.csv)"))
"""
            ),
            markdown(
                """
## 2. Damage evidence and pace loss

No single public database reliably records Formula 1 damage. The collection method therefore joins
FIA timing and classifications with official team reports, named driver or engineer accounts, and
Formula1.com reporting. Team accounts can identify a floor, wing, puncture, repair, or attributed
pace cost, but they are interested-party evidence and must be checked against official timing.

Driver-specific clock mapping gives a single incident lap for 241 harm records. Fifty-two have the
minimum clean laps before and after plus teammate coverage. Exact same-lap matching leaves 28
estimable timing screens. These are not confirmed damage effects: tyre choice, traffic, strategy,
weather, and hidden car conditions can still drive the result.

The source method is documented with official examples, including
[Hamilton's attributed Imola front-wing loss](https://www.formula1.com/en/latest/article/front-wing-damage-cost-hamilton-0-6s-per-lap-until-imola-red-flag-mercedes.4YdB5ZdPJaoMCfjnx5Nk3u),
[Piastri's Miami wing change](https://www.formula1.com/en/latest/article/sainz-hit-with-five-second-time-penalty-after-collision-with-piastri-in.3D1JHk6lYz0GzKch77GcrZ), and
[Williams' description of worsening floor damage in Japan](https://www.williamsf1.com/posts/05f49fb5-62ac-4308-b14d-52f8959cfee8/2023-japanese-grand-prix).
"""
            ),
            code(
                """
display(Markdown("![Referral funnel](../reports/generated/study_v2/referral_funnel.png)"))
display(Markdown("![Pace screens](../reports/generated/study_v2/pace_screen_distribution.png)"))
display(Markdown("![Nationality power](../reports/generated/study_v2/nationality_power_v2.png)"))
"""
            ),
            markdown(
                """
## 3. Conduct, harm, and punishment stay separate

Study v2 does not create one fairness score. It stores:

1. the act and the written finding;
2. each participant's observed consequence;
3. the nominal and realized cost of the sanction, in seconds, positions, grid places, or points.

A proportionality comparison needs three different things: a fault finding, source-supported harm,
and the realized cost of the sanction. The strict audit now covers the first part. Damage and actual
sanction cost are still incomplete, so no full-corpus record meets every gate and the release count
remains zero. This is a boundary on the claim, not a failed analysis.

The FIA's public 2025 guideline explanation says the guidelines assist steward decisions but are
not regulations. Historical FIA practice was also described as judging the incident rather than its
outcome. Damage therefore measures consequence; it does not back-fill fault.
"""
            ),
            markdown(
                """
## 4. Nationality remains inconclusive

British accused drivers received sanctions in 25 of 44 formal cases (56.8%). Other accused drivers
received sanctions in 189 of 302 cases (62.6%). This raw 5.8-point difference is not an adjusted
effect and does not show favoritism.

Measured overlap passes the frozen balance checks, but the British group is below the required 98
cases. Simulated power for the prespecified 15-point difference is only 37.8% to 53.6%, depending on
the baseline rate. The model-led source audit is complete, but independent human validation is not.
More importantly, the sample-size and power gates fail on their own. No adjusted nationality result
is fit or released.
"""
            ),
            markdown(
                """
## 5. What is settled, and what is still open

The user does not need to work through hundreds of FIA decisions. The model-led audit is complete,
source-cited, and used by the downstream analysis. The blank Reviewer A and Reviewer B files remain
available only if a future reviewer wants to measure independent agreement.

The open work is narrower:

- confirm damage, repair, retirement, and rare benefit claims with incident-specific sources;
- verify the highest-priority close pairs with public video when a reliable clip exists;
- record when and where each sanction was served before calling nominal seconds an actual race cost;
- collect more seasons or cases before testing a small nationality effect.

Until those gates pass, the defensible conclusion is narrow: formal FIA decisions can be audited for
coding consistency, but the public record still cannot support a population-wide verdict that
stewarding is fair, unfair, biased, or proportional to race harm.
"""
            ),
            markdown(
                """
## Evidence status

| Output | Current status |
|---|---|
| Strict source audit | 920 of 920 cited; 32 included rows corrected; model-led disclosure |
| Primary 346-case population | Rebuilt from strict reviewed fields |
| Referral funnel | Descriptive public-feed coverage |
| Incident lap windows | Validated candidate context |
| Close-case neighbors | Review-priority tool |
| Damage and pace screens | Source-research tool |
| Proportionality | Withheld pending damage and realized-sanction evidence |
| Nationality effect | Inconclusive; release gate failed |

The protocol, source hierarchy, packets, transformations, and release gates are versioned in the
repository. Unknowns remain unknown instead of being converted into zeros.
"""
            ),
            markdown(
                """
## Appendix: one FIA citation for every included decision

The table below contains all 418 included decisions. Each link goes directly to that decision's FIA
source. The downloadable 920-row audit also includes the 502 exclusion checks, rule sources,
evidence spans, corrections, and unresolved-source status.
"""
            ),
            code(
                """
decision_citations = strict_cases.loc[
    strict_cases["review_scope"].isin(["primary", "secondary"]),
    ["season", "event_name", "review_scope", "title", "document_id", "fia_decision_citation_url"],
].copy()
decision_citations["FIA decision"] = decision_citations["fia_decision_citation_url"].map(
    lambda url: f'<a href="{url}">Official source</a>'
)
decision_citations = decision_citations.drop(columns="fia_decision_citation_url")
assert len(decision_citations) == 418
display(HTML(decision_citations.to_html(index=False, escape=False)))
"""
            ),
        ],
    )
    # Replace the earlier progress-report draft with the consolidated final narrative.
    write("12_study_v2_report.ipynb", build_integrated_report_cells(SETUP))


def execute_and_export() -> None:
    """Execute all Study v2 notebooks and export the integrated HTML report."""

    task_jupyter = ROOT / ".jupyter"
    environment = os.environ.copy()
    for variable, directory in (
        ("JUPYTER_CONFIG_DIR", task_jupyter / "config"),
        ("JUPYTER_DATA_DIR", task_jupyter / "data"),
        ("JUPYTER_RUNTIME_DIR", task_jupyter / "runtime"),
        ("IPYTHONDIR", task_jupyter / "ipython"),
    ):
        directory.mkdir(parents=True, exist_ok=True)
        environment[variable] = str(directory)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "notebook",
            "--execute",
            "--inplace",
            "--ExecutePreprocessor.timeout=600",
            *(str(path) for path in STUDY_V2_NOTEBOOKS),
        ],
        check=True,
        cwd=ROOT,
        env=environment,
    )
    for path in STUDY_V2_NOTEBOOKS:
        notebook = nbformat.read(path, as_version=4)
        for cell in notebook.cells:
            cell.metadata.pop("execution", None)
        nbformat.write(notebook, path)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "jupyter",
            "nbconvert",
            "--to",
            "html",
            "--TemplateExporter.exclude_input=True",
            "--TemplateExporter.exclude_input_prompt=True",
            "--TemplateExporter.exclude_output_prompt=True",
            "--output-dir",
            str(ROOT / "reports"),
            "--output",
            "the_cost_of_discretion_study_v2",
            str(STUDY_V2_NOTEBOOKS[-1]),
        ],
        check=True,
        cwd=ROOT,
        env=environment,
    )

    report_path = ROOT / "reports" / "the_cost_of_discretion_study_v2.html"
    report_html = report_path.read_text(encoding="utf-8")
    report_html = report_html.replace(
        "<title>12_study_v2_report</title>",
        (
            "<title>The Cost of Discretion — Formula 1 Stewarding, 2018–2025</title>"
            '<meta name="description" content="A source-cited data analysis of consistency, '
            'competitive burden, and potential nationality effects in Formula 1 stewarding."/>'
        ),
        1,
    )
    report_path.write_text(report_html, encoding="utf-8")


if __name__ == "__main__":
    build()
    execute_and_export()
    print("built and executed Study v2 notebooks 07-12; exported integrated HTML report")
