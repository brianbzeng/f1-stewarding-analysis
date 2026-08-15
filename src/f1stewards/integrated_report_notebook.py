"""Notebook cells for the consolidated, general-audience final report."""

# ruff: noqa: E501

from __future__ import annotations

import nbformat


def _markdown(source: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_markdown_cell(source.strip())


def _code(source: str) -> nbformat.NotebookNode:
    return nbformat.v4.new_code_cell(source.strip())


def build_integrated_report_cells(setup_source: str) -> list[nbformat.NotebookNode]:
    """Return the executable cells for the integrated final report."""

    return [
        _markdown(
            """
# The Cost of Discretion

<div class="report-author">
<strong>Brian Zeng</strong><br>
<a href="mailto:bzeng0000@gmail.com">bzeng0000@gmail.com</a><br>
<a href="https://brianbzeng.com">brianbzeng.com</a>
</div>

## Quantitative assessment of Formula 1 stewarding, 2018 to 2025

**Final integrated report | 2018 to 2025 seasons | Analytical data frozen August 13, 2026 |
Narrative sources checked August 14, 2026**

The dataset contains 346 Race and Sprint decisions from 131 events. Stewards imposed a sanction in
214 cases (61.8%) and took no further action in 132 cases (38.2%).

All 76 decisions that found a driver wholly or predominantly to blame imposed a sanction. All 24
racing-incident findings ended with no further action.

The nearest-neighbor screen found different direct-penalty outcomes in 131 of 317 supported cases
(41.3%). Of those 131 differences, 87 (66.4%) also had different written fault findings.

British accused drivers received sanctions in 25 of 44 decisions (56.8%), compared with 189 of 302
other-driver decisions (62.6%). The 44 British-driver cases fell below the prespecified minimum of
98, so the nationality result remains inconclusive.
"""
        ),
        _code(setup_source),
        _code(
            """
import html
import math
import textwrap

import numpy as np
from matplotlib import patches
from matplotlib.ticker import PercentFormatter

PILOT = ROOT / "data/manual/reconciled/pilot-41f4502411c2"
LEGACY_GENERATED = ROOT / "reports/generated"

BLUE = "#0072B2"
SKY = "#56B4E9"
GREEN = "#009E73"
ORANGE = "#E69F00"
VERMILLION = "#D55E00"
PURPLE = "#CC79A7"
CHARCOAL = "#262626"
LIGHT_GRID = "#D9D9D9"

plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": CHARCOAL,
        "axes.labelcolor": CHARCOAL,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "axes.grid.axis": "x",
        "grid.color": LIGHT_GRID,
        "grid.linewidth": 0.7,
        "text.color": CHARCOAL,
        "xtick.color": CHARCOAL,
        "ytick.color": CHARCOAL,
        "font.size": 11,
        "legend.frameon": False,
    }
)

display(
    HTML(
        '''
<style>
body { color: #262626; }
.jp-Notebook { max-width: 1080px; margin: 0 auto; }
.jp-RenderedHTMLCommon { font-size: 17px; line-height: 1.68; }
.jp-RenderedHTMLCommon h1, .jp-RenderedHTMLCommon h2, .jp-RenderedHTMLCommon h3 { text-transform: uppercase; letter-spacing: .035em; }
.jp-RenderedHTMLCommon h1 { color: #17324d; font-size: 2.55rem; line-height: 1.08; margin-top: 1.2rem; }
.jp-RenderedHTMLCommon h2 { color: #17324d; border-bottom: 2px solid #d9e3ea; padding-bottom: .32rem; margin-top: 3.2rem; }
.jp-RenderedHTMLCommon h3 { color: #225b78; margin-top: 2rem; }
.jp-RenderedHTMLCommon p { max-width: 880px; }
.jp-RenderedHTMLCommon table { font-size: .92rem; }
.jp-RenderedHTMLCommon th { background: #eaf2f7; color: #17324d; }
.jp-RenderedHTMLCommon td, .jp-RenderedHTMLCommon th { padding: .55rem .7rem; }
.report-answer { border-left: 6px solid #0072B2; background: #eef6fa; padding: 1rem 1.2rem; margin: 1.3rem 0 1.8rem; max-width: 880px; }
.report-note { border-left: 5px solid #E69F00; background: #fff8e8; padding: .85rem 1.1rem; margin: 1rem 0; max-width: 880px; }
.report-method { border-left: 5px solid #009E73; background: #eef9f5; padding: .85rem 1.1rem; margin: 1rem 0; max-width: 880px; }
.report-author { color: #434343; line-height: 1.45; margin: .55rem 0 1.3rem; }
.report-author strong { color: #17324d; font-size: 1.08rem; }
.report-author a { color: #225b78; text-decoration: none; }
.report-author a:hover { text-decoration: underline; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: .8rem; max-width: 900px; margin: 1.25rem 0 1.5rem; }
.stat-item { border-top: 5px solid #0072B2; background: #f5f8fa; padding: .9rem 1rem; }
.stat-value { color: #17324d; font-size: 1.75rem; font-weight: 700; line-height: 1.1; }
.stat-label { color: #434343; font-size: .91rem; margin-top: .25rem; }
.toc { columns: 2; column-gap: 2.2rem; max-width: 900px; padding: 1rem 1.25rem; background: #f5f8fa; border-top: 4px solid #009E73; }
.toc li { break-inside: avoid; margin-bottom: .4rem; }
.figure-caption { color: #4d4d4d; font-size: .92rem; max-width: 900px; margin-top: -.3rem; }
.table-scroll { overflow-x: auto; }
details { max-width: 100%; margin: 1rem 0; }
details > summary { cursor: pointer; color: #225b78; font-weight: 700; }
@media (max-width: 700px) { .toc { columns: 1; } .jp-RenderedHTMLCommon { font-size: 16px; } }
</style>
'''
    )
)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (math.nan, math.nan)
    proportion = successes / total
    denominator = 1 + z**2 / total
    center = (proportion + z**2 / (2 * total)) / denominator
    spread = z * math.sqrt((proportion * (1 - proportion) + z**2 / (4 * total)) / total) / denominator
    return center - spread, center + spread


def save_and_show(fig: plt.Figure, filename: str, alt_text: str, caption: str) -> None:
    destination = GENERATED / filename
    fig.savefig(destination, dpi=190, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    display(Markdown(f"![{alt_text}](../reports/generated/study_v2/{filename})"))
    display(HTML(f'<p class="figure-caption">{html.escape(caption)}</p>'))
"""
        ),
        _code(
            """
strict_manifest = json.loads((STRICT / "manifest.json").read_text(encoding="utf-8"))
strict_cases = pd.read_csv(STRICT / "strict_model_case_audit.csv", keep_default_na=False)
primary = strict_cases.loc[strict_cases["review_scope"].eq("primary")].copy()
secondary = strict_cases.loc[strict_cases["review_scope"].eq("secondary")].copy()
primary["sanction_outcome"] = primary["reviewed_outcome_family"].ne("no_further_action")

referral_manifest = json.loads((REFERRAL / "manifest.json").read_text(encoding="utf-8"))
referral_funnel = pd.read_csv(REFERRAL / "referral_funnel.csv")
clock_manifest = json.loads((CLOCK / "manifest.json").read_text(encoding="utf-8"))
close_manifest = json.loads((CLOSE / "manifest.json").read_text(encoding="utf-8"))
close_summary = pd.read_csv(CLOSE / "conduct_neighbor_summary.csv")
close_edges = pd.read_csv(LAYERS / "close_case_outcome_contrasts.csv")
damage_manifest = json.loads((DAMAGE / "manifest.json").read_text(encoding="utf-8"))
layers_manifest = json.loads((LAYERS / "manifest.json").read_text(encoding="utf-8"))
nationality_manifest = json.loads((NATIONALITY / "manifest.json").read_text(encoding="utf-8"))
nationality_rates = pd.read_csv(NATIONALITY / "descriptive_rates.csv")
nationality_power = pd.read_csv(NATIONALITY / "simulation_power.csv")
model_metrics = pd.read_csv(LEGACY_GENERATED / "grouped_model_metrics.csv").set_index("metric")["value"]

pilot_adjudications = pd.read_csv(PILOT / "adjudications.csv")
pilot_impacts = pd.read_csv(PILOT / "impact_assessments.csv")
pilot_harms = pd.read_csv(PILOT / "harm_assessments.csv")

assert len(primary) == 346
assert int(primary["sanction_outcome"].sum()) == 214
assert primary["event_id"].nunique() == 131
assert len(secondary) == 72
assert strict_manifest["included_decisions"] == 418
assert strict_manifest["records_with_fia_citation"] == 920
assert strict_manifest["corrected_included_rows"] == 32
assert referral_manifest["high_confidence_link_count"] == 177
assert clock_manifest["mapped_case_count"] == 338
assert close_manifest["pre_review_minimum_support_count"] == 317
assert len(pilot_adjudications) == 9

overall_rate = primary["sanction_outcome"].mean()
overview = [
    ("346", "primary Race/Sprint decisions"),
    (f"{overall_rate:.1%}", "ended with a sanction"),
    ("920", "source-cited audit records"),
    ("32", "included records corrected"),
]
overview_html = '<div class="stat-grid">' + ''.join(
    f'<div class="stat-item"><div class="stat-value">{value}</div><div class="stat-label">{label}</div></div>'
    for value, label in overview
) + '</div>'
display(HTML(overview_html))
"""
        ),
        _markdown(
            """
<div class="report-answer"><strong>Primary result:</strong> The 100 clearest responsibility findings
produced 100 outcomes aligned with the written finding: 76 blame findings led to sanctions and 24
racing-incident findings led to no further action. This measures internal consistency after the
fault finding, not whether each fault finding was correct.</div>

### Index

<ol class="toc">
<li><a href="#chapter-1">Analytical framework</a></li>
<li><a href="#chapter-2">Data construction and quality control</a></li>
<li><a href="#chapter-3">Descriptive results</a></li>
<li><a href="#chapter-4">Consistency tests</a></li>
<li><a href="#chapter-5">Inconsistency audit and case studies</a></li>
<li><a href="#chapter-6">2025 guideline comparison</a></li>
<li><a href="#chapter-7">Penalty burden and incident harm</a></li>
<li><a href="#chapter-8">Nationality analysis</a></li>
<li><a href="#chapter-9">Results summary</a></li>
<li><a href="#chapter-10">Recommendations</a></li>
<li><a href="#methods">Methods, limits, and reproducibility</a></li>
<li><a href="#citations">Sources and citations</a></li>
</ol>
"""
        ),
        _markdown(
            """
<a id="chapter-1"></a>

## Chapter 1: Analytical framework

The analysis divides fairness into five testable components:

1. **Conduct:** Comparable driving acts should receive comparable fault findings.
2. **Sanction:** Comparable fault findings should receive comparable penalties.
3. **Consequence:** Harm must be measured separately for each affected driver.
4. **Competitive burden:** Penalty cost must reflect how and when the sanction was applied.
5. **Distribution:** Group outcome differences require adequate samples and comparable case context.

The study does not calculate a composite fairness score. Conduct, harm, and sanction burden remain
separate because each measure uses different evidence.

<div class="report-method"><strong>Study rule:</strong> A proportionality claim requires separate
evidence for fault, incident-caused harm, and realized sanction cost.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-2"></a>

## Chapter 2: Data construction and quality control

The source inventory contains 9,467 FIA event documents from 173 completed championship events.
The final analytical population contains 346 Race and Sprint decisions from 131 events.
"""
        ),
        _code(
            """
flow = [
    ("9,467", "FIA event documents"),
    ("2,003", "outcome records checked"),
    ("1,984", "local source files"),
    ("1,935", "current decision versions"),
    ("418", "included decisions"),
    ("346", "primary Race/Sprint cases"),
]

fig, ax = plt.subplots(figsize=(14, 3.5))
ax.set_xlim(0, len(flow) * 2.25)
ax.set_ylim(0, 2.2)
ax.axis("off")
flow_colors = [BLUE, SKY, GREEN, ORANGE, PURPLE, VERMILLION]
for index, ((count, label), color) in enumerate(zip(flow, flow_colors, strict=True)):
    x = index * 2.25 + 0.08
    box = patches.FancyBboxPatch(
        (x, 0.48),
        1.72,
        1.12,
        boxstyle="round,pad=0.03,rounding_size=0.05",
        facecolor=color,
        edgecolor=CHARCOAL,
        linewidth=0.8,
    )
    ax.add_patch(box)
    text_color = "white" if color in {BLUE, GREEN, VERMILLION, PURPLE} else CHARCOAL
    ax.text(x + 0.86, 1.20, count, ha="center", va="center", fontsize=17, fontweight="bold", color=text_color)
    ax.text(x + 0.86, 0.82, "\\n".join(textwrap.wrap(label, width=21)), ha="center", va="center", fontsize=9.5, color=text_color)
    if index < len(flow) - 1:
        ax.annotate("", xy=(x + 2.10, 1.04), xytext=(x + 1.78, 1.04), arrowprops={"arrowstyle": "->", "color": CHARCOAL, "lw": 1.4})
ax.set_title("From public archive to the final analytical population", fontsize=15, pad=8)
save_and_show(
    fig,
    "final_population_path.png",
    "Six-stage source path from 9,467 FIA event documents to 346 primary Race and Sprint cases.",
    "Counts describe different stages of the evidence pipeline; they are not all independent documents or incidents.",
)
"""
        ),
        _markdown(
            """
The Race Control linkage produced the following counts:

- **16,039 messages:** All collected Race and Sprint Race Control messages.
- **1,815 process messages:** Messages describing noted, investigated, or sanctioned states.
- **966 referral episodes:** Process messages grouped into incident-level sequences.
- **177 high-confidence links:** Primary decisions linked to a referral episode, 51.2% of 346.
- **153 candidate links:** Primary decisions requiring further context review, 44.2% of 346.
- **16 unmatched decisions:** Formal decisions without a referral match, 4.6% of 346.

The Race Control feed therefore does not provide a complete denominator for all comparable acts.

### Data constraints

- **Version control:** The source audit marked 32 records as corrected to prevent duplicate rulings.
- **Referral coverage:** Formal PDFs include referred cases but exclude unobserved non-referrals.
- **Multi-car incidents:** One incident can produce several accused-driver and affected-driver records.
- **Damage coding:** Floors, tyres, wings, repair stops, and retirements require separate evidence fields.
- **Broad labels:** An incident-family label does not record overlap, control, space, or mitigation.

The final dataset followed a nine-decision pilot, a full source inventory, a model-led source audit,
and participant-level timing and harm screens. The report uses only the final corrected population.

### How the source review worked

GPT-5.6 Sol checked all 418 included decisions and 502 sampled exclusions against a cited source
under a frozen protocol. The 920-row audit confirmed 884 records, corrected 32 included records,
and marked four archive labels as unresolved because no public source file was recoverable.

All 418 included decisions have an FIA citation and an evidence passage. The full audit is
model-led, while the separate nine-decision pilot received independent review.
"""
        ),
        _markdown(
            """
<a id="chapter-3"></a>

## Chapter 3: Descriptive results

The primary population contains 346 accused-driver decisions from 131 Race or Sprint events. A
sanction was imposed in 214 cases (61.8%); 132 ended with no further action.

These rates describe formal decisions, not every incident that occurred.
"""
        ),
        _code(
            """
family = (
    primary.groupby("reviewed_incident_family", dropna=False)
    .agg(cases=("sanction_outcome", "size"), sanctions=("sanction_outcome", "sum"))
    .reset_index()
)
family["rate"] = family["sanctions"] / family["cases"]
family[["low", "high"]] = family.apply(
    lambda row: pd.Series(wilson_interval(int(row["sanctions"]), int(row["cases"]))), axis=1
)
family["label"] = family["reviewed_incident_family"].str.replace("_", " ").str.title()
family = family.sort_values("rate")

season = (
    primary.groupby("season")
    .agg(cases=("sanction_outcome", "size"), sanctions=("sanction_outcome", "sum"))
    .reset_index()
)
season["rate"] = season["sanctions"] / season["cases"]
season[["low", "high"]] = season.apply(
    lambda row: pd.Series(wilson_interval(int(row["sanctions"]), int(row["cases"]))), axis=1
)

fig, axes = plt.subplots(1, 2, figsize=(14, 5.7), gridspec_kw={"width_ratios": [1.2, 1]})
y = np.arange(len(family))
axes[0].barh(y, family["rate"], color=BLUE, edgecolor=CHARCOAL, linewidth=0.6)
axes[0].errorbar(
    family["rate"],
    y,
    xerr=[family["rate"] - family["low"], family["high"] - family["rate"]],
    fmt="none",
    ecolor=CHARCOAL,
    capsize=3,
    linewidth=1,
)
axes[0].set_yticks(y, family["label"])
axes[0].set_xlim(0, 1.08)
axes[0].xaxis.set_major_formatter(PercentFormatter(1))
axes[0].axvline(overall_rate, color=CHARCOAL, linestyle="--", linewidth=1.2)
axes[0].set_title("Sanction rate by incident family")
axes[0].set_xlabel("Formal decisions ending in a sanction")
axes[0].set_ylabel("")
for index, row in family.reset_index(drop=True).iterrows():
    axes[0].text(min(row["rate"] + 0.025, 0.96), index, f'{row["rate"]:.0%}  n={int(row["cases"])}', va="center", fontsize=9)

axes[1].errorbar(
    season["season"],
    season["rate"],
    yerr=[season["rate"] - season["low"], season["high"] - season["rate"]],
    color=ORANGE,
    marker="o",
    markersize=6,
    capsize=3,
    linewidth=2,
)
axes[1].axhline(overall_rate, color=CHARCOAL, linestyle="--", linewidth=1.2, label="Overall 61.8%")
axes[1].set_ylim(0, 1)
axes[1].yaxis.set_major_formatter(PercentFormatter(1))
axes[1].set_title("Sanction rate by season")
axes[1].set_xlabel("Season")
axes[1].set_ylabel("Formal decisions ending in a sanction")
axes[1].legend(loc="lower right")
fig.suptitle("Formal outcomes vary, but small groups carry wide uncertainty", fontsize=16, fontweight="bold")
fig.tight_layout()
save_and_show(
    fig,
    "final_sanction_rates.png",
    "Two panels showing sanction rates with 95 percent intervals by incident family and season.",
    "The dashed line is the overall 61.8% rate. Intervals are Wilson 95% intervals; they widen sharply for small incident families.",
)
"""
        ),
        _markdown(
            """
- **Causing a collision:** 137 sanctions in 233 decisions (58.8%).
- **Gaining an advantage off track:** 41 sanctions in 54 decisions (75.9%).
- **Forcing another driver off track:** 23 sanctions in 43 decisions (53.5%).
- **Small groups:** Eight unsafe-rejoin decisions and two moving-under-braking decisions are insufficient for stable comparisons.

Season rates range from 40.9% in 2019 to 75.9% in 2021. That does not prove standards changed from
one year to the next.

The seasonal comparison mixes incident facts, rule eras, responsibility findings, mitigation, and
referral choices.
"""
        ),
        _markdown(
            """
<a id="chapter-4"></a>

## Chapter 4: Consistency tests

The consistency analysis used three tests:

1. **Responsibility alignment:** Compare the written fault finding with the formal outcome.
2. **Predictive validation:** Test broad incident labels on held-out events.
3. **Close-case screening:** Match cases without using the observed sanction or fault finding.

### Written responsibility and the decision
"""
        ),
        _code(
            """
fault_labels = {
    "wholly_to_blame": "Wholly to blame",
    "predominantly_to_blame": "Predominantly to blame",
    "shared_fault": "Shared fault",
    "racing_incident": "Racing incident",
    "no_conclusion": "No explicit blame threshold",
    "not_applicable": "Threshold not applicable",
}
fault = (
    primary.groupby("reviewed_fault_language", dropna=False)
    .agg(cases=("sanction_outcome", "size"), sanctions=("sanction_outcome", "sum"))
    .reset_index()
)
fault["rate"] = fault["sanctions"] / fault["cases"]
fault["label"] = fault["reviewed_fault_language"].map(fault_labels).fillna("Other")
fault = fault.sort_values("rate")

fig, ax = plt.subplots(figsize=(10, 5.2))
y = np.arange(len(fault))
ax.barh(y, fault["rate"], color=GREEN, edgecolor=CHARCOAL, linewidth=0.6)
ax.set_yticks(y, fault["label"])
ax.set_xlim(0, 1.12)
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.set_xlabel("Decisions ending in a sanction")
ax.set_ylabel("")
ax.set_title("The clearest written findings map closely to the outcome")
for index, row in fault.reset_index(drop=True).iterrows():
    ax.text(min(row["rate"] + 0.02, 1.01), index, f'{row["rate"]:.0%}  n={int(row["cases"])}', va="center")
fig.tight_layout()
save_and_show(
    fig,
    "final_fault_language.png",
    "Sanction rates for six categories of written FIA responsibility language.",
    "All 76 decisions finding a driver wholly or predominantly to blame imposed a sanction; all 24 racing-incident findings ended with no further action.",
)

explicit_blame = primary["reviewed_fault_language"].isin(["wholly_to_blame", "predominantly_to_blame"])
racing_incident = primary["reviewed_fault_language"].eq("racing_incident")
assert explicit_blame.sum() == 76
assert primary.loc[explicit_blame, "sanction_outcome"].all()
assert racing_incident.sum() == 24
assert not primary.loc[racing_incident, "sanction_outcome"].any()
"""
        ),
        _markdown(
            """
All 76 decisions that found a driver wholly or predominantly to blame imposed a sanction. All 24
racing-incident findings ended with no further action.

These 100 decisions show complete outcome alignment after the written fault finding. They do not
test whether the fault finding itself was correct.

### Broad labels and close comparisons
"""
        ),
        _code(
            """
model_auc = float(model_metrics["model_roc_auc"])
model_brier_gain = float(model_metrics["brier_improvement_over_baseline"])

supported_ids = set(
    close_summary.loc[
        close_summary["pre_review_minimum_support"].astype(str).str.lower().eq("true"),
        "adjudication_instance_id",
    ]
)
nearest = close_edges.loc[
    close_edges["neighbor_rank"].eq(1)
    & close_edges["adjudication_instance_id"].isin(supported_ids)
].copy()
nearest["different"] = nearest["different_sanction_outcome"].astype(str).str.lower().eq("true")
nearest_counts = pd.Series(
    {
        "Same direct-penalty result": int((~nearest["different"]).sum()),
        "Different direct-penalty result": int(nearest["different"].sum()),
    }
)
assert nearest_counts.sum() == 317

fig, axes = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1, 1.15]})
axes[0].set_xlim(0.48, 1.0)
axes[0].set_ylim(-0.4, 0.4)
axes[0].axvline(0.5, color=CHARCOAL, linestyle="--", linewidth=1.2)
axes[0].scatter([model_auc], [0], s=180, color=BLUE, edgecolor=CHARCOAL, marker="o", zorder=3)
axes[0].text(0.505, -0.22, "chance\\n0.50", ha="left", va="top", fontsize=9)
axes[0].text(model_auc + 0.015, 0.17, f"broad-label model\\n{model_auc:.3f}", ha="left", va="bottom", fontweight="bold")
axes[0].text(1.0, -0.22, "perfect ranking\\n1.00", ha="right", va="top", fontsize=9)
axes[0].set_yticks([])
axes[0].set_xlabel("ROC AUC")
axes[0].set_title("Broad labels show limited ranking performance")
axes[0].grid(False)

bars = axes[1].barh(
    ["Same outcome", "Different outcome"],
    nearest_counts.values,
    color=[BLUE, ORANGE],
    edgecolor=CHARCOAL,
    linewidth=0.6,
)
axes[1].set_xlim(0, 220)
axes[1].set_xlabel("Cases with at least five available neighbors")
axes[1].set_title("Closest available match: 59% same, 41% different")
for bar, count in zip(bars, nearest_counts.values, strict=True):
    axes[1].text(bar.get_width() + 4, bar.get_y() + bar.get_height() / 2, f"{count} ({count / 317:.0%})", va="center")
fig.suptitle("Similarity screening identifies questions, not verdicts", fontsize=16, fontweight="bold")
fig.tight_layout()
save_and_show(
    fig,
    "final_similarity_screen.png",
    "A broad-label model scores 0.558 ROC AUC and nearest matched cases have the same direct sporting-penalty result in 186 of 317 supported cases.",
    f"The broad model improved Brier score over its baseline by only {model_brier_gain:.4f}. Matching excluded fault, penalty, damage, retirement, and finishing result; warnings and reprimands were separated from penalties with direct race or grid burden.",
)
"""
        ),
        _markdown(
            """
A model using incident family, season, and multi-car status produced ROC AUC 0.558 against a 0.500
chance-ranking reference. Its Brier score improved by 0.0005 over the sanction-rate baseline.

The outcome-blind screen matched incident family, session, guideline era, first-lap status, wet
track, restart, overlap, and attacker-line context. Warnings and reprimands were excluded from the
direct-penalty outcome because they did not change race time, position, or the grid.

Among 317 cases with at least five available neighbors, 186 nearest matches had the same
direct-penalty outcome (58.7%). The remaining 131 had different outcomes (41.3%).

<div class="report-note"><strong>41.3% is not an inconsistency rate:</strong> The matching fields
remain incomplete, and the screen excludes the later fault finding. The 131 differences are review
candidates, not confirmed errors.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-5"></a>

## Chapter 5: Inconsistency audit and case studies

The nearest-neighbor screen identified 131 different direct-penalty outcomes among 317 supported
comparisons (41.3%). The audit then classified all 131 differences by written fault language and
off-track context.

The five case studies below explain specific public controversies. They do not estimate the
frequency of disputed decisions in the 346-case population.
"""
        ),
        _code(
            """
case_fault = close_summary.set_index("adjudication_instance_id")["fault_language"]
nearest["case_fault"] = nearest["adjudication_instance_id"].map(case_fault)
nearest["neighbor_fault"] = nearest["neighbor_adjudication_instance_id"].map(case_fault)
different_nearest = nearest.loc[nearest["different"]].copy()

disagreement_taxonomy = pd.Series(
    {
        "Different written fault finding": int(
            different_nearest["case_fault"].ne(different_nearest["neighbor_fault"]).sum()
        ),
        "No explicit fault threshold in either ruling": int(
            (
                different_nearest["case_fault"].eq("no_conclusion")
                & different_nearest["neighbor_fault"].eq("no_conclusion")
            ).sum()
        ),
        "Off-track advantage context": int(
            (
                different_nearest["case_fault"].eq("not_applicable")
                & different_nearest["neighbor_fault"].eq("not_applicable")
            ).sum()
        ),
    }
)
assert disagreement_taxonomy.to_dict() == {
    "Different written fault finding": 87,
    "No explicit fault threshold in either ruling": 30,
    "Off-track advantage context": 14,
}
assert int(disagreement_taxonomy.sum()) == 131

fig, ax = plt.subplots(figsize=(11, 4.8))
display_order = disagreement_taxonomy.sort_values()
bars = ax.barh(
    display_order.index,
    display_order.values,
    color=[SKY, ORANGE, BLUE],
    edgecolor=CHARCOAL,
    linewidth=0.6,
)
ax.set_xlim(0, 100)
ax.set_xlabel("Nearest-neighbor cases with a different direct sporting-penalty outcome")
ax.set_ylabel("")
ax.set_title("The 131 close-case disagreements do not all mean the same thing")
for bar, count in zip(bars, display_order.values, strict=True):
    ax.text(
        count + 2,
        bar.get_y() + bar.get_height() / 2,
        f"{count} ({count / 131:.0%})",
        va="center",
        fontweight="bold",
    )
fig.tight_layout()
save_and_show(
    fig,
    "final_inconsistency_map.png",
    "Of 131 nearest-neighbor cases with different direct sporting-penalty outcomes, 87 had different written fault findings, 30 had no explicit fault threshold in either ruling, and 14 involved off-track advantage context.",
    "The screen treats warnings and reprimands separately from penalties that directly affect race time or the grid. These are review categories, not proven stewarding errors.",
)
"""
        ),
        _markdown(
            """
### What the 131 disagreements actually contain

- **Different written fault finding, 87 of 131 (66.4%):** The paired decisions used different responsibility thresholds.
- **No explicit fault threshold, 30 of 131 (22.9%):** Both rulings required the reader to infer responsibility from the reasons.
- **Off-track advantage context, 14 of 131 (10.7%):** The outcome depended on whether an advantage was retained, returned, or caused by being forced off.

The 41.3% result is a screening rate, not an error rate. The 87 different fault findings account for
66.4% of the screened outcome differences.

### Five selected controversies

| Case and source | Recorded parameters | Assessment |
|---|---|---|
| [Canada 2019](https://www.fia.com/sites/default/files/decision-document/2019%20Canadian%20Grand%20Prix%20-%20Offence%20-%20Car%205%20(re-joinged%20unsafely%20and%20forced%20car%2044%20of%20the%20track).pdf) and [Austria 2019, Document 50](https://www.fia.com/sites/default/files/doc_50_-_2019_austrian_grand_prix_-_decision_-_car_33_turn_3_incident_with_car_16.pdf) | Canada: Car 5, unsafe rejoin, Car 44 forced off, five seconds; Austria: Cars 33 and 16, Turn 3, no predominant fault, no further action | Different incident types and fault thresholds prevent a direct precedent comparison. |
| [Silverstone 2021, Document 50](https://www.fia.com/sites/default/files/doc_50_-_2021_british_grand_prix_-_offence_-_car_44_-_causing_a_collision_with_car_33.pdf) | Car 44, Turn 9, predominantly at fault, ten seconds, two penalty points; Car 33 retired and Car 44 won | The case measures proportionality between conduct and harm, not nationality bias. |
| [São Paulo 2021, Document 55](https://www.fia.com/sites/default/files/bra_doc_55_-_decision_-_mercedes_-_right_of_review_0.pdf) | Turn 4; forward and 360-degree footage classified as new, unavailable, and relevant; review rejected because the evidence was not significant | The record documents a limit in live evidence without proving the original outcome was incorrect. |
| [Abu Dhabi 2021 WMSC review, 19 March 2022](https://www.fia.com/sites/default/files/2021_f1_abu_dhabi_grand_prix_-_report_to_the_wmsc_-_19_march_2022.pdf) | Safety Car procedure; conflicting interpretations of Articles 48.12 and 48.13; direct team radio pressure | The case concerns Race Control procedure and remains outside the 346 driver-conduct decisions. |
| [Austin 2024, Document 69](https://www.fia.com/sites/default/files/decision-document/2024%20United%20States%20Grand%20Prix%20-%20Infringement%20-%20Car%204%20-%20Leaving%20the%20track%20and%20gaining%20an%20advantage.pdf) and [Mexico 2024, Document 47](https://www.fia.com/sites/default/files/decision-document/2024%20Mexico%20City%20Grand%20Prix%20-%20Infringement%20-%20Car%201%20-%20Turn%204%20Forcing%20another%20driver%20of%20the%20track%20(corrected).pdf) plus [Document 44](https://www.fia.com/sites/default/files/decision-document/2024%20Mexico%20City%20Grand%20Prix%20-%20Infringement%20-%20Car%201%20-%20Turn%208%20Leaving%20the%20track%20and%20gaining%20an%20advantage.pdf) | Austin: Car 4, five seconds; Mexico: Car 1, Turn 4 and Turn 8, ten seconds for each ruling | The documents record different apex, space, and retained-advantage findings under the same broad standard. |

### Unresolved consistency questions

| Case and source | Recorded parameters | Assessment |
|---|---|---|
| [Japan 2024, Car 63 and Car 81](https://www.fia.com/sites/default/files/decision-document/2024%20Japanese%20Grand%20Prix%20-%20Decision%20-%20Car%2063%20-%20Alleged%20forcing%20car%2081%20off%20the%20track.pdf) | Car 81 left the track to avoid contact, rejoined safely, retained the position, and received no action | The decision states that the driving standards did not cover this sequence. |
| [Hungary 2025, Document 38](https://www.fia.com/system/files/decision-document/2025_hungarian_grand_prix_-_decision_-_car_22_-_alleged_forcing_another_driver_off_of_the_track.pdf) and [Italy 2025, Document 38](https://www.fia.com/system/files/decision-document/2025_italian_grand_prix_-_infringement_-_car_31_-_forcing_another_driver_off_the_track.pdf) | Hungary: Car 22 forced Car 27 off, both contributed, correct order restored, no action; Italy: Car 31 failed to leave Car 18 space, five seconds | The public reasons use restoration of order differently, so the pair remains unresolved. |

The audit explains 87 of 131 different outcomes through a different written fault finding. The
remaining 44 contain no explicit shared threshold or depend on off-track advantage context.

- [FIA driver meeting on guideline revisions](https://www.fia.com/news/fia-stewards-open-constructive-dialogue-formula-1-drivers)
- [FIA explanation of the 2025 guideline publication](https://www.fia.com/news/fia-insights-guiding-principles-how-fia-bringing-even-more-transparency-application-f1)
"""
        ),
        _markdown(
            """
<a id="chapter-6"></a>

## Chapter 6: 2025 guideline comparison

The analysis compared 33 sanctions from 2025 with the public driving and penalty guidelines in
force that season. The guidelines were not applied to decisions from 2018 through 2024.
"""
        ),
        _code(
            """
guideline_rows = strict_cases.loc[
    strict_cases["review_scope"].isin(["primary", "secondary"])
    & strict_cases["penalty_guideline_assessment"].isin(
        [
            "within_contemporaneous_public_guideline",
            "within_guideline_with_documented_or_possible_mitigation",
            "within_no_immediate_consequence_range_requires_context",
            "substitution_or_escalation_requires_context",
        ]
    )
].copy()
guideline_summary = pd.Series(
    {
        "Plainly within guideline": int(
            guideline_rows["penalty_guideline_assessment"].eq("within_contemporaneous_public_guideline").sum()
        ),
        "Within range; context or mitigation noted": int(
            guideline_rows["penalty_guideline_assessment"].isin(
                [
                    "within_guideline_with_documented_or_possible_mitigation",
                    "within_no_immediate_consequence_range_requires_context",
                ]
            ).sum()
        ),
        "Substitution or escalation needs context": int(
            guideline_rows["penalty_guideline_assessment"].eq("substitution_or_escalation_requires_context").sum()
        ),
    }
)
assert guideline_summary.to_dict() == {
    "Plainly within guideline": 21,
    "Within range; context or mitigation noted": 7,
    "Substitution or escalation needs context": 5,
}

fig, ax = plt.subplots(figsize=(10, 4.6))
labels = ["Plainly within\\nguideline", "Within range; context\\nor mitigation noted", "Substitution/escalation\\nneeds more context"]
bars = ax.bar(labels, guideline_summary.values, color=[GREEN, SKY, ORANGE], edgecolor=CHARCOAL, linewidth=0.7)
ax.set_ylim(0, 25)
ax.set_ylabel("2025 decisions")
ax.set_title("Thirty-three sanctions could be compared with the public 2025 guidance")
ax.grid(axis="y")
ax.grid(axis="x", visible=False)
for bar, value in zip(bars, guideline_summary.values, strict=True):
    ax.text(bar.get_x() + bar.get_width() / 2, value + 0.6, str(value), ha="center", va="bottom", fontweight="bold")
fig.tight_layout()
save_and_show(
    fig,
    "final_guideline_comparison.png",
    "Of 33 comparable 2025 sanctions, 21 were plainly within guideline, seven were within range with context or mitigation noted, and five required more context for a substitution or escalation.",
    "This comparison describes conformity with the public starting points. It does not independently decide whether the underlying fault finding was correct.",
)
"""
        ),
        _markdown(
            """
Of 33 comparable sanctions, 21 (63.6%) were plainly within the public starting point. Seven (21.2%)
were within range with mitigation or context, and five (15.2%) required additional context for a
substitution or escalation.

The independently reviewed Austrian 2025 pilot matched the baseline in four of five decisions
(80.0%). The fifth decision documented mitigation.

- [FIA Formula 1 Driving Standards Guidelines, version 4.1](https://www.fia.com/sites/default/files/f1_driving_standards_guidelines_version_4.1_feb_20_2025.pdf)
- [FIA 2025 Penalty Guidelines](https://www.fia.com/sites/default/files/2025_f1_guidelines_penalty_points_overview_-_14_may_clean_0.pdf)
"""
        ),
        _markdown(
            """
<a id="chapter-7"></a>

## Chapter 7: Penalty burden and incident harm

The independently reviewed pilot contains nine decisions. Two nominal five-second penalties
produced different observed position and points effects.
"""
        ),
        _code(
            """
pilot_table = pd.DataFrame(
    [
        {
            "Case": "Pérez / Norris, Abu Dhabi 2023",
            "Written sanction": "5 seconds + 2 points",
            "How applied": "Added after the race",
            "Observed competitive burden": "P4 to P2 without penalty; two places, six points, and a podium",
        },
        {
            "Case": "Tsunoda / Colapinto, Austria 2025",
            "Written sanction": "10 seconds + 2 points",
            "How applied": "Served during the race",
            "Observed competitive burden": "Not recoverable by subtracting 10 seconds; strategy and traffic changed",
        },
        {
            "Case": "Colapinto / Piastri, Austria 2025",
            "Written sanction": "5 seconds + 1 point",
            "How applied": "Added after the race",
            "Observed competitive burden": "No classification place and no points changed",
        },
        {
            "Case": "Antonelli / Verstappen, Austria 2025",
            "Written sanction": "3 grid places + 2 points",
            "How applied": "At the next event",
            "Observed competitive burden": "Starting position moved from P7 to P10; race effect not isolated",
        },
    ]
)
display(HTML('<div class="table-scroll">' + pilot_table.to_html(index=False, escape=True) + '</div>'))
"""
        ),
        _markdown(
            """
Pérez's five-second penalty changed P2 to P4, a loss of two places, six points, and a podium.
Colapinto's five-second penalty changed no finishing place or points.

Tsunoda served ten seconds during the race, so a post-race subtraction cannot reconstruct the
altered strategy and traffic. Antonelli's three-place grid penalty moved his start from P7 to P10,
while the race-finish effect remained unidentifiable.

The nine harm records include one incident-caused retirement, three observed one-place losses, and
one possible damage report without an immediate place loss. The full collision screen therefore
stores a separate harm record for each participant.
"""
        ),
        _code(
            """
harm_flow = [
    ("233", "collision decision rows"),
    ("193", "candidate incidents"),
    ("412", "driver-level harm records"),
    ("241", "single-lap driver mappings"),
    ("52", "pace-screen candidates"),
    ("28", "estimable timing screens"),
]
fig, ax = plt.subplots(figsize=(14, 3.5))
ax.set_xlim(0, len(harm_flow) * 2.25)
ax.set_ylim(0, 2.2)
ax.axis("off")
harm_colors = [BLUE, SKY, GREEN, ORANGE, PURPLE, VERMILLION]
for index, ((count, label), color) in enumerate(zip(harm_flow, harm_colors, strict=True)):
    x = index * 2.25 + 0.08
    box = patches.FancyBboxPatch(
        (x, 0.48), 1.72, 1.12, boxstyle="round,pad=0.03,rounding_size=0.05", facecolor=color, edgecolor=CHARCOAL, linewidth=0.8
    )
    ax.add_patch(box)
    text_color = "white" if color in {BLUE, GREEN, VERMILLION, PURPLE} else CHARCOAL
    ax.text(x + 0.86, 1.20, count, ha="center", va="center", fontsize=17, fontweight="bold", color=text_color)
    ax.text(x + 0.86, 0.82, "\\n".join(textwrap.wrap(label, width=19)), ha="center", va="center", fontsize=9.2, color=text_color)
    if index < len(harm_flow) - 1:
        ax.annotate("", xy=(x + 2.10, 1.04), xytext=(x + 1.78, 1.04), arrowprops={"arrowstyle": "->", "color": CHARCOAL, "lw": 1.4})
ax.text(5.38, 0.23, "The count rises here because one incident can create several driver records.", ha="center", va="center", fontsize=9.5)
ax.set_title("Damage research narrows quickly when timing and comparison rules are enforced", fontsize=15, pad=8)
save_and_show(
    fig,
    "final_harm_path.png",
    "Collision-harm workflow from 233 decision rows to 28 estimable timing screens, expanding to 412 driver-level harm records before narrowing.",
    "The 28 timing screens are research leads, not confirmed damage effects. Tyres, traffic, strategy, weather, and hidden car conditions remain alternative explanations.",
)
assert damage_manifest["candidate_incident_count"] == 193
assert damage_manifest["participant_record_count"] == 412
assert damage_manifest["participant_rows_with_incident_lap"] == 241
assert layers_manifest["pace_screen_estimable_rows"] == 28
"""
        ),
        _markdown(
            """
Only 28 of 412 participant records (6.8%) had enough clean, same-lap teammate data for a timing
screen. These 28 records remain screening results because public timing cannot isolate damage from
tyres, traffic, strategy, weather, or hidden car conditions.

Zero cases passed the prespecified proportionality release gate. A case requires separate evidence
for fault, incident-caused harm, and realized sanction cost before a proportionality conclusion is
released.
"""
        ),
        _markdown(
            """
<a id="chapter-8"></a>

## Chapter 8: Nationality analysis

British accused drivers were sanctioned in 25 of 44 decisions (56.8%). Other accused drivers were
sanctioned in 189 of 302 decisions (62.6%), a raw difference of -5.8 percentage points.

The 95% Wilson interval was 42.2% to 70.3% for British drivers and 57.0% to 67.9% for other drivers.
The intervals overlap by 10.9 percentage points.
"""
        ),
        _code(
            """
nationality_plot = pd.DataFrame(
    [
        {"group": "British accused driver", "cases": 44, "sanctions": 25},
        {"group": "Other accused driver", "cases": 302, "sanctions": 189},
    ]
)
nationality_plot["rate"] = nationality_plot["sanctions"] / nationality_plot["cases"]
nationality_plot[["low", "high"]] = nationality_plot.apply(
    lambda row: pd.Series(wilson_interval(int(row["sanctions"]), int(row["cases"]))), axis=1
)

fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.7), gridspec_kw={"width_ratios": [1.25, 1]})
y = np.arange(len(nationality_plot))
axes[0].errorbar(
    nationality_plot["rate"],
    y,
    xerr=[nationality_plot["rate"] - nationality_plot["low"], nationality_plot["high"] - nationality_plot["rate"]],
    fmt="o",
    markersize=9,
    color=BLUE,
    ecolor=CHARCOAL,
    capsize=4,
)
axes[0].set_yticks(y, nationality_plot["group"])
axes[0].invert_yaxis()
axes[0].set_xlim(0.35, 0.78)
axes[0].xaxis.set_major_formatter(PercentFormatter(1))
axes[0].set_xlabel("Sanction rate with 95% interval")
axes[0].set_title("Raw rates overlap substantially")
for index, row in nationality_plot.iterrows():
    axes[0].text(row["rate"] + 0.018, index, f'{row["rate"]:.1%}  n={int(row["cases"])}', va="center")

sample_bars = axes[1].barh(["Observed British cases", "Prespecified minimum"], [44, 98], color=[ORANGE, SKY], edgecolor=CHARCOAL, linewidth=0.6)
axes[1].set_xlim(0, 112)
axes[1].set_xlabel("British-accused decisions")
axes[1].set_title("The planned sample-size gate fails")
for bar, value in zip(sample_bars, [44, 98], strict=True):
    axes[1].text(value + 3, bar.get_y() + bar.get_height() / 2, str(value), va="center", fontweight="bold")
fig.suptitle("The nationality result is inconclusive", fontsize=16, fontweight="bold")
fig.tight_layout()
save_and_show(
    fig,
    "final_nationality_result.png",
    "British accused drivers have a 56.8 percent raw sanction rate versus 62.6 percent for other drivers, with overlapping 95 percent intervals; only 44 British cases are available against a minimum target of 98.",
    "The raw difference is not an adjusted effect and the design lacks power for the prespecified 15-point difference.",
)
"""
        ),
        _markdown(
            """
The British group contains 44 cases against a prespecified minimum of 98. Simulated power for a
15-point difference ranged from 37.8% to 53.6%, below the 80% design target.

The five controversy cases in Chapter 5 were selected for explanation, not nationality estimation.
They include decisions that helped and harmed British drivers, so they cannot replace the 346-case
population.

FIA decisions list panel members but not individual votes. The same-nationality panel analysis was
withheld because its country-evidence and overlap gates failed.

**Result:** The -5.8-point raw difference is inconclusive because N=44 fell below the required 98
and simulated power remained below 80%.
"""
        ),
        _markdown(
            """
<a id="chapter-9"></a>

## Chapter 9: Results summary

1. **Responsibility alignment:** All 76 explicit blame findings led to sanctions, and all 24 racing-incident findings led to no further action.
2. **Broad-label model:** Incident family, season, and multi-car status produced ROC AUC 0.558 and Brier improvement 0.0005.
3. **Close-case screen:** Different direct-penalty outcomes occurred in 131 of 317 nearest matches (41.3%).
4. **Difference classification:** Different fault findings accounted for 87 of 131 outcome differences (66.4%).
5. **2025 guideline comparison:** 21 of 33 sanctions were plainly within guideline, seven were contextual, and five required more context.
6. **Penalty burden:** One five-second penalty cost two places and six points, while another changed zero places and zero points.
7. **Nationality result:** The -5.8-point raw difference remained inconclusive with N=44 and simulated power of 37.8% to 53.6%.

<div class="report-answer"><strong>Final conclusion:</strong> The evidence points to a stewarding
system with complete outcome alignment across the 100 clearest responsibility findings. The
remaining evidence does not establish systematic unfairness or nationality bias because 131 close
comparisons lack complete context and the nationality test failed its sample-size and power gates.</div>

### Evidence needed for stronger conclusions

- A more complete referral denominator showing comparable incidents that never reached a decision.
- Independently verified context for the highest-priority close-case disagreements.
- Source-confirmed damage, repairs, retirements, and rare beneficial stops.
- Realized sanction-cost records, especially for penalties served during a race.
- A larger, adequately powered nationality sample with better decision-maker information.
"""
        ),
        _markdown(
            """
<a id="chapter-10"></a>

## Chapter 10: Recommendations

### For the FIA

1. **Publish structured decisions:** Provide stable incident and decision IDs, accused and affected
   driver roles, session, lap, turn, finding, sanction, service timing, and version status.
2. **Connect the referral trail:** Link “noted,” “investigated,” “no further action,” and formal
   decision messages to the same incident ID.
3. **Version the guidance:** Identify the driving and penalty guideline active at each event and
   state the normal starting point plus aggravating or mitigating factors.
4. **Separate sanction from consequence:** Publish what the penalty nominally was and when it was
   served; do not imply that seconds alone describe its competitive burden.
5. **Make corrections explicit:** Retain the archive history but mark one effective version so
   outside analysts cannot double-count a ruling.

### For future analysts

1. Use models and close matches to prioritize source review, not to label a decision incorrect.
2. Keep conduct, victim harm, and sanction burden in separate tables.
3. Treat unavailable evidence as unknown, never as “no harm” or “no effect.”
4. Report small samples and failed power gates as results rather than forcing a conclusion.
5. Preserve a citation and evidence passage for every published case-level statement.
"""
        ),
        _markdown(
            """
<a id="methods"></a>

## Methods, limitations, and reproducibility

### Data used

- Official FIA [event and timing pages](https://www.fia.com/events/fia-formula-one-world-championship),
  [decision documents](https://www.fia.com/documents/season), classifications,
  [Formula 1 regulations](https://www.fia.com/regulation/category/110), and the
  [International Sporting Code](https://www.fia.com/regulation/category/123).
- [FastF1 timing and Race Control feeds](https://docs.fastf1.dev/data_reference/index.html) for
  timing and process context, not for assigning fault.
- [Official Formula 1 reporting](https://www.formula1.com/en/latest/all), team reports, and named
  driver or engineer accounts for damage research, with interested-party claims kept distinct from
  FIA findings and checked against official timing where possible.

### Analytical design

- **Population:** 173 completed championship events, 2018 to 2025.
- **Primary unit:** one accused-driver decision in a Race or Sprint.
- **Primary scope:** causing a collision, forcing another driver off track, gaining an advantage
  off track, unsafe rejoining, moving under braking, and multiple defensive moves.
- **Inconsistency audit:** full-corpus nearest-neighbor disagreements were separated by written
  fault language, then high-salience and residual gray-area cases were read against their official
  FIA decisions and contemporaneous governance documents.
- **Tools:** Python, Jupyter, pandas, DuckDB SQL, partitioned Parquet, Git, and automated tests.
- **Portability:** a locally validated Snowflake/Snowsight package is included; no live remote
  deployment is claimed.
- **Validation:** the full automated test suite and all final Study v2 release controls passed at
  the report commit.

### Important limitations

1. Formal decisions are conditional on referral and do not represent every on-track act.
2. The full source audit was model-led; it does not measure independent human agreement.
3. Close-case context remains incomplete and is used only to prioritize review.
4. Timing changes cannot by themselves establish damage or its cause.
5. In-race penalty counterfactuals are altered by strategy, traffic, tyres, and later events.
6. The nationality design is underpowered and cannot support an adjusted effect.
7. The 2025 public guidelines are never applied retrospectively to earlier seasons.
8. The highlighted controversy cases were chosen for explanatory value and are not a prevalence
   estimate of controversial decisions.

### Evidence status

| Finding | Evidence level | Release decision |
|---|---|---|
| Source inventory and 418 included decisions | Strict source-cited model audit | Descriptive release |
| Full-corpus sanction and responsibility rates | Strict source-cited model audit | Descriptive release |
| Broad-label prediction model | Grouped out-of-event validation | Negative result; no case ranking |
| Close-case outcome contrasts | Outcome-blind screening | Review priorities only |
| Inconsistency and controversy audit | Official decisions plus FIA governance records | Bounded case-study interpretation |
| Nine-decision penalty-cost pilot | Independent double review | Case-level release |
| Full collision damage and pace effects | Timing and source screening | No population damage claim |
| 2025 guideline comparison | Contemporaneous public guidance | Descriptive/contextual release |
| Nationality association | Failed sample-size and power gates | Inconclusive |

<details>
<summary>Reproduction notes</summary>

The executable version is `notebooks/12_study_v2_report.ipynb`. The report reads immutable,
content-addressed source-audit and Study v2 artifacts.

Rebuild with
`python scripts/build_study_v2_notebooks.py`, then run `pytest`, `ruff check src scripts tests`, and
`python scripts/audit_study_v2_completion.py`. Run `python scripts/audit_report_style.py` to enforce
the public writing rules.

The public HTML hides code for readability. The notebook retains the executable code and outputs.

</details>
"""
        ),
        _markdown(
            """
<a id="citations"></a>

## Sources and citations

Regulations and guidelines define the standard, while steward decisions record the official
finding. Classifications and timing record observed results, while attributed team or driver
reports provide case-specific damage evidence.

Each source is restricted to the role listed below.

### Rules and governing material

| Source | How it was used | Important limit |
|---|---|---|
| [FIA Formula 1 Regulations Archive](https://www.fia.com/regulation/category/110) | Event-date Sporting Regulations and sanction authority | The applicable issue can change during a season. |
| [FIA International Sporting Code and Appendices](https://www.fia.com/regulation/category/123) | Steward powers, protests, reviews, appeals, and general driving rules | Multiple editions may exist in the same year. |
| [2025 F1 Driving Standards Guidelines, version 4.1](https://www.fia.com/sites/default/files/f1_driving_standards_guidelines_version_4.1_feb_20_2025.pdf) | The contemporaneous overtaking and driving-standard comparison in Chapter 6 | Guidance, not a regulation; not applied to earlier seasons. |
| [2025 FIA Penalty Guidelines](https://www.fia.com/sites/default/files/2025_f1_guidelines_penalty_points_overview_-_14_may_clean_0.pdf) | Public sanction starting points and penalty-point ranges | Context can justify mitigation, escalation, or substitution. |

### FIA process and policy context

| Source | How it was used | Important limit |
|---|---|---|
| [FIA explanation of publishing the stewarding guidelines](https://www.fia.com/news/fia-adds-further-transparency-fia-formula-one-world-championship-publication-stewards) | Status, purpose, and history of the public guidance | Does not reconstruct every historical internal guideline. |
| [FIA explanation of how the guidelines are applied](https://www.fia.com/news/fia-insights-guiding-principles-how-fia-bringing-even-more-transparency-application-f1) | Living-document status, evidence limits, and first-lap tolerance | General explanation rather than a case ruling. |
| [FIA steward and driver discussion on revising the guidelines](https://www.fia.com/news/fia-stewards-open-constructive-dialogue-formula-1-drivers) | Context for the post-Austin 2024 rule discussion | Describes the reform process, not whether one driver deserved a penalty. |
| [FIA 2021 Abu Dhabi review to the World Motor Sport Council](https://www.fia.com/sites/default/files/2021_f1_abu_dhabi_grand_prix_-_report_to_the_wmsc_-_19_march_2022.pdf) | Governance case study separating Race Control procedure from ordinary steward penalties | Outside the study's driver-conduct penalty population. |
| [Formula 1 interview with the 2021 Race Director](https://www.formula1.com/en/latest/article/masi-backs-stewards-on-hamilton-penalty-adding-that-decisions-are-always.52AUb0ZpArxnTSoCDsfahy) | Contemporary explanation that stewards assessed conduct rather than the eventual consequence | An attributed policy explanation, not governing law. |

### Timing, results, and damage evidence

| Source | How it was used | Important limit |
|---|---|---|
| [FIA event and timing pages](https://www.fia.com/events/fia-formula-one-world-championship) | Official classifications, grids, lap charts, pit-stop summaries, and Race Control records | They establish observed results, not a no-incident counterfactual. |
| [FastF1 data reference](https://docs.fastf1.dev/data_reference/index.html) | Lap timing, position, pit, track-status, and Race Control context | Timing alone cannot prove damage, causation, or fault. |
| [Official Formula 1 race reporting](https://www.formula1.com/en/latest/all) | Attributed interviews, race sequencing, and damage context | Secondary to an FIA finding and explicitly attributed. |

The independently reviewed consequence pilot also used the following case-level, non-decision
sources. They support only the particular fact described here:

- [Gasly's Abu Dhabi 2023 damage account](https://www.formula1.com/en/latest/article/gasly-says-damage-with-hamilton-and-perez-finished-me-after-p13-result-at.4oooNkg91ON0oLVrNxcJSs): attributed diffuser damage and downforce loss, with earlier contact kept as a confounding cause.
- [Official Abu Dhabi 2023 race report](https://www.formula1.com/en/latest/article/verstappen-beats-leclerc-to-victory-in-abu-dhabi-to-end-record-breaking-year.6pYEohQvxeey5ATWkXh8sQ): race order and incident sequence around the Pérez and Norris contact.
- [Alpine's Austrian 2025 debrief](https://media.alpinecars.com/2025-formula-one-austrian-grand-prix-sunday/?lang=eng): Colapinto's first-party report that the car felt different after contact; coded as possible, not confirmed, damage.
- [Official Austrian 2025 race analysis](https://www.formula1.com/en/latest/article/austria-lowdown-all-the-key-moments-as-the-mclarens-duel-red-bull-suffer-and.7DG4DaK04hYZKL97D6xjr9): the effect of backmarker traffic on Piastri's pursuit, without assigning an exact time loss.
- [Verstappen's Austrian 2025 post-race account](https://www.formula1.com/en/latest/article/no-one-does-that-on-purpose-verstappen-gives-verdict-on-unlucky-race-ending.1WQnU9ao4YlVIuvewwaSOg): contextual confirmation of the race-ending collision, paired with the FIA classification.
- [Official British 2025 race report](https://www.formula1.com/en/latest/article/norris-wins-dramatic-wet-dry-british-gp-from-piastri-as-hulkenberg-claims.1puOD82avOZ8I0sca7fvLJ): race context after Antonelli served the carried Austrian grid penalty; not used to invent a counterfactual finish.

Third-party databases, media searches, broadcasts, photographs, and social posts could identify
leads, but they did not establish the study's published fault or fairness findings.

### Decision-level FIA sources

Every one of the 418 included primary and secondary decisions has a direct FIA citation. The table
is collapsed to keep the main report readable.

The downloadable audit contains 502 exclusion checks, evidence passages, correction history, rule
sources, confidence fields, and review status.
"""
        ),
        _code(
            """
decision_citations = strict_cases.loc[
    strict_cases["review_scope"].isin(["primary", "secondary"]),
    ["season", "event_name", "review_scope", "title", "document_id", "fia_decision_citation_url"],
].copy()
decision_citations["title"] = (
    decision_citations["title"].str.replace(r"[\u2013\u2014]", "-", regex=True)
)
decision_citations["FIA source"] = decision_citations["fia_decision_citation_url"].map(
    lambda url: f'<a href="{html.escape(url, quote=True)}">Official decision</a>'
)
decision_citations = decision_citations.drop(columns="fia_decision_citation_url")
assert len(decision_citations) == 418
assert decision_citations["FIA source"].str.contains("Official decision", regex=False).all()
citation_html = decision_citations.to_html(index=False, escape=False, border=0)
display(
    HTML(
        '<details><summary>Open all 418 FIA decision citations</summary>'
        '<div class="table-scroll">' + citation_html + '</div></details>'
    )
)
display(
    Markdown(
        "[Download the complete 920-row source audit]"
        "(../data/manual/study_v2_strict_model_audit/strict-model-audit-0fe15fd6b052/strict_model_case_audit.csv)"
    )
)
"""
        ),
        _markdown(
            """
---

**Project:** *The Cost of Discretion*<br>
**Coverage:** Formula 1 championship seasons 2018 to 2025<br>
**Final evidence date:** August 13, 2026<br>
**Review disclosure:** GPT-5.6 Sol model-led source audit; separate independently reviewed pilot;
no claim of full-corpus human inter-rater agreement.
"""
        ),
    ]
