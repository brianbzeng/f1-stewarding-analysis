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
# Does Formula 1 Stewarding Treat Similar Incidents the Same Way?

<div class="report-author">
<strong>Brian Zeng</strong><br>
<a href="mailto:bzeng0000@gmail.com">bzeng0000@gmail.com</a><br>
<a href="https://brianbzeng.com">brianbzeng.com</a>
</div>

## A data analysis of stewarding consistency, 2018 to 2025

Formula 1 stewards decide whether an on-track incident broke the rules and whether a driver should
receive a penalty. Those decisions often become controversial when two incidents look similar to
viewers but produce different written findings or penalties.

This study asks a narrower question than whether every decision was correct: does the public record
show a consistent path from the facts described by the stewards, to the finding of responsibility,
to the final sanction? It also examines where that path becomes difficult to compare, how much a
penalty can affect a race, and whether the available data support claims of nationality bias.

The analysis follows the standard data science process. It defines the questions, builds a dataset
from FIA documents, explores the decisions, tests consistency, investigates exceptions, and states
what the evidence cannot establish.
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
"""
        ),
        _markdown(
            """
### Index

<ol class="toc">
<li><a href="#chapter-1">The question: what would consistent stewarding look like?</a></li>
<li><a href="#chapter-2">Turning FIA documents into analyzable data</a></li>
<li><a href="#chapter-3">What the formal decisions look like</a></li>
<li><a href="#chapter-4">Do written findings lead to consistent outcomes?</a></li>
<li><a href="#chapter-5">Where similar cases still diverge</a></li>
<li><a href="#chapter-6">What the 2025 public guidelines add</a></li>
<li><a href="#chapter-7">Why penalty length is not the same as race cost</a></li>
<li><a href="#chapter-8">Testing the claim of British-driver bias</a></li>
<li><a href="#chapter-9">What the study can and cannot conclude</a></li>
<li><a href="#chapter-10">What better stewarding data would look like</a></li>
<li><a href="#methods">Methods, limits, and reproducibility</a></li>
<li><a href="#citations">Sources and citations</a></li>
</ol>
"""
        ),
        _markdown(
            """
<a id="chapter-1"></a>

## Chapter 1: The question: what would consistent stewarding look like?

An FIA decision has three main parts. The stewards describe what happened, decide how much
responsibility a driver carried, and choose an outcome such as no further action, a warning, or a
sporting penalty.

A consistent system should treat comparable conduct in comparable ways. That does not mean every
collision must receive the same penalty, because position, overlap, driver control, track
conditions, and mitigating factors can change the decision.

The study therefore separates five questions:

1. **Conduct:** Do comparable driving acts receive comparable responsibility findings?
2. **Sanction:** Do comparable responsibility findings receive comparable penalties?
3. **Consequence:** What happened to each driver affected by the incident?
4. **Race cost:** What did the sanction actually cost after its timing and application are considered?
5. **Nationality:** Do group differences remain credible after sample size and case context are checked?

The nationality question tests a specific claim that British drivers may receive favorable
treatment. It is a secondary analysis, not the starting assumption of the report.

The study does not combine these questions into one fairness score. A steward can describe fault
consistently while a fixed penalty still creates very different race costs, and a harmful outcome
does not by itself prove that the original driving act deserved a harsher finding.

<div class="report-method"><strong>Interpretation rule:</strong> This report calls a decision
internally consistent when the written responsibility finding and the formal outcome agree. It calls
two decisions comparable only when the available incident context is similar.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-2"></a>

## Chapter 2: Turning FIA documents into analyzable data

The FIA does not publish one analysis-ready table of stewarding decisions. Its event archives also
contain classifications, summonses, technical reports, corrected rulings, and several versions of
the same document, so counting search results would overstate the number of decisions.

The collection process began with 9,467 documents from 173 championship events. Each record then
passed through a sequence of filters designed to answer a simple question: is this a current,
source-supported steward decision that belongs in the study?
"""
        ),
        _code(
            """
flow = [
    ("9,467", "Documents listed across FIA event archives"),
    ("2,003", "Records that could contain a steward outcome"),
    ("418", "Verified decisions relevant to the study"),
    ("346", "Race and Sprint driver-conduct decisions analyzed"),
]

fig, ax = plt.subplots(figsize=(13, 4.0))
ax.set_xlim(0, len(flow) * 3.05)
ax.set_ylim(0, 2.5)
ax.axis("off")
flow_colors = [BLUE, SKY, GREEN, ORANGE]
for index, ((count, label), color) in enumerate(zip(flow, flow_colors, strict=True)):
    x = index * 3.05 + 0.08
    box = patches.FancyBboxPatch(
        (x, 0.50),
        2.45,
        1.35,
        boxstyle="round,pad=0.03,rounding_size=0.05",
        facecolor=color,
        edgecolor=CHARCOAL,
        linewidth=0.8,
    )
    ax.add_patch(box)
    text_color = "white" if color in {BLUE, GREEN} else CHARCOAL
    ax.text(x + 1.225, 1.38, count, ha="center", va="center", fontsize=19, fontweight="bold", color=text_color)
    ax.text(x + 1.225, 0.91, "\\n".join(textwrap.wrap(label, width=31)), ha="center", va="center", fontsize=10, color=text_color)
    if index < len(flow) - 1:
        ax.annotate("", xy=(x + 2.92, 1.18), xytext=(x + 2.52, 1.18), arrowprops={"arrowstyle": "->", "color": CHARCOAL, "lw": 1.6})
ax.set_title("Four filters turn the FIA archive into the main study dataset", fontsize=15, pad=10)
save_and_show(
    fig,
    "final_population_path.png",
    "Four filters reduce 9,467 FIA archive documents to 346 Race and Sprint driver-conduct decisions.",
    "The 418 verified decisions include 346 Race and Sprint cases used in the main analysis and 72 qualifying impeding cases used only as supporting material.",
)
"""
        ),
        _markdown(
            """
The first filter identified 2,003 archive records that might contain a steward outcome. The source
review then removed administrative files, duplicate versions, and decisions outside the selected
incident types, leaving 418 verified decisions with direct FIA citations.

The main analysis uses 346 decisions about driver conduct during a Race or Sprint. The remaining 72
decisions concern qualifying impeding and appear only where they add supporting context, so they are
never mixed into the main sanction rate.

### What one row represents

One row represents one accused driver in one formal decision. A multi-car crash can therefore
create several decision rows, while harm to each affected driver is stored separately so one
driver's retirement does not overwrite another driver's puncture or time loss.

### What the dataset does not contain

Formal decisions show incidents that reached the stewards, not every comparable act on track. Race
Control messages produced high-confidence referral links for 177 of the 346 main decisions, which
was not enough to construct a complete population of investigated and uninvestigated incidents.

The analysis also cannot infer missing facts from silence. If a decision does not describe overlap,
damage, or mitigation, that field remains unknown instead of being coded as absent.

These limits shape every later result. The report can test patterns inside published decisions, but
it cannot estimate how often similar conduct was never referred or decide fault from timing data
alone.
"""
        ),
        _markdown(
            """
<a id="chapter-3"></a>

## Chapter 3: What the formal decisions look like

The first step is descriptive. The main dataset contains 346 accused-driver decisions from 131 Race
or Sprint events, and stewards imposed some form of sanction in 214 decisions (61.8%).

That percentage is not the rate at which all on-track incidents are punished. It describes only
the incidents that produced a formal FIA decision and passed the study filters in Chapter 2.

Incident type provides the first useful comparison. If one category receives sanctions more often
than another, the difference can identify where the rules or case facts deserve closer study, but
the raw rate cannot establish inconsistency on its own.
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

family["display_label"] = family.apply(
    lambda row: f'{row["label"]}  (n={int(row["cases"])})', axis=1
)

fig, ax = plt.subplots(figsize=(11.5, 6.2))
y = np.arange(len(family))
ax.barh(y, family["rate"], color=BLUE, edgecolor=CHARCOAL, linewidth=0.6)
ax.errorbar(
    family["rate"],
    y,
    xerr=[family["rate"] - family["low"], family["high"] - family["rate"]],
    fmt="none",
    ecolor=CHARCOAL,
    capsize=3,
    linewidth=1,
)
ax.set_yticks(y, family["display_label"])
ax.set_xlim(0, 1.0)
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.axvline(overall_rate, color=CHARCOAL, linestyle="--", linewidth=1.2, label="All decisions: 61.8%")
ax.set_title("Raw sanction rates differ by incident type")
ax.set_xlabel("Share of formal decisions ending in a sanction")
ax.set_ylabel("")
for index, row in family.reset_index(drop=True).iterrows():
    ax.text(0.025, index, f'{row["rate"]:.0%}', va="center", color="white", fontweight="bold")
ax.legend(loc="lower right")
fig.tight_layout()
save_and_show(
    fig,
    "final_sanction_rates.png",
    "Horizontal bars show raw sanction rates and 95 percent confidence intervals for six incident types.",
    "Sample sizes appear in the category labels. The black intervals show statistical uncertainty, and the dashed line marks the 61.8% rate across all 346 decisions.",
)

fig, ax = plt.subplots(figsize=(10.8, 5.2))
ax.errorbar(
    season["season"],
    season["rate"],
    yerr=[season["rate"] - season["low"], season["high"] - season["rate"]],
    color=ORANGE,
    marker="o",
    markersize=6,
    capsize=3,
    linewidth=2,
)
ax.axhline(overall_rate, color=CHARCOAL, linestyle="--", linewidth=1.2, label="All decisions: 61.8%")
ax.set_ylim(0.25, 0.95)
ax.yaxis.set_major_formatter(PercentFormatter(1))
ax.set_title("The raw sanction rate changes by season")
ax.set_xlabel("Season")
ax.set_ylabel("Share of formal decisions ending in a sanction")
ax.legend(loc="lower right")
fig.tight_layout()
save_and_show(
    fig,
    "final_season_rates.png",
    "Annual raw sanction rates with 95 percent confidence intervals from 2018 through 2025.",
    "The annual rate ranges from 40.9% in 2019 to 75.9% in 2021. The figure does not adjust for changes in incident mix, written responsibility, or stewarding guidance.",
)
"""
        ),
        _markdown(
            """
Causing a collision dominates the dataset, with 233 of the 346 decisions. Stewards imposed a
sanction in 137 of those cases (58.8%), compared with 41 of 54 gaining-an-advantage cases (75.9%)
and 23 of 43 forcing-another-driver-off cases (53.5%).

The smaller categories are much less stable. Unsafe rejoining contains eight decisions, moving
under braking contains two, and multiple defensive moves contains six, so their wide intervals are
more informative than their point estimates.

The annual rate ranges from 40.9% in 2019 to 75.9% in 2021. That difference could reflect changes in
incident mix, evidence, rule interpretation, or referral practice, so the report does not treat it
as proof that one season was stricter than another.

This descriptive stage shows where variation exists, but not why. The next stage tests whether the
written responsibility finding provides a clearer explanation of the outcome than broad labels such
as season or incident type.
"""
        ),
        _markdown(
            """
<a id="chapter-4"></a>

## Chapter 4: Do written findings lead to consistent outcomes?

The descriptive rates in Chapter 3 group incidents by broad labels. Stewarding decisions rely on
more specific facts, so the consistency analysis moves closer to the reasoning recorded in each
document.

Three tests address different parts of that reasoning. The first checks whether the written
responsibility finding agrees with the formal outcome, the second measures how much broad labels
can predict, and the third compares each case with its closest available matches.

### Test 1: Does the written finding match the outcome?

This is the most direct internal check. A decision that calls an event a racing incident should not
normally impose a penalty, while a finding that one driver was wholly or predominantly to blame
should normally lead to a sanction.
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
fault["display_label"] = fault.apply(
    lambda row: f'{row["label"]}  (n={int(row["cases"])})', axis=1
)

fig, ax = plt.subplots(figsize=(11, 5.6))
y = np.arange(len(fault))
ax.barh(y, fault["rate"], color=GREEN, edgecolor=CHARCOAL, linewidth=0.6)
ax.set_yticks(y, fault["display_label"])
ax.set_xlim(0, 1.0)
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.set_xlabel("Share of decisions ending in a sanction")
ax.set_ylabel("")
ax.set_title("Clear responsibility findings align with the formal outcome")
for index, row in fault.reset_index(drop=True).iterrows():
    label_x = 0.025 if row["rate"] >= 0.16 else row["rate"] + 0.02
    label_color = "white" if row["rate"] >= 0.16 else CHARCOAL
    ax.text(label_x, index, f'{row["rate"]:.0%}', va="center", color=label_color, fontweight="bold")
fig.tight_layout()
save_and_show(
    fig,
    "final_fault_language.png",
    "Sanction rates for six categories of written FIA responsibility language.",
    "Sample sizes appear beside each category. All 76 decisions finding a driver wholly or predominantly to blame imposed a sanction, while all 24 racing-incident findings ended with no further action.",
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
The result is exact for the two clearest ends of the responsibility scale. All 76 decisions that
found a driver wholly or predominantly to blame imposed a sanction, and all 24 racing-incident
findings ended with no further action.

Those 100 decisions show complete agreement between the published finding and the published
outcome. They do not prove that the stewards reached the correct finding, because that would require
reconstructing the incident evidence and applying the rule independently in every case.

The middle categories explain why sanction rates alone can mislead. Decisions with no explicit
blame threshold or with off-track advantage findings cover several factual situations, so the next
tests ask how much can be learned before the final responsibility finding is known.

### Test 2: Can broad case labels predict the outcome?

A simple model used only the incident type, season, and whether more than two cars were involved.
The goal was not to automate stewarding, but to measure whether those broad labels carry enough
information to reproduce the pattern of decisions at events the model had not seen.
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

nearest_rates = nearest_counts / nearest_counts.sum()
fig, ax = plt.subplots(figsize=(10.5, 4.6))
bars = ax.barh(
    ["Same outcome", "Different outcome"],
    nearest_rates.values,
    color=[GREEN, ORANGE],
    edgecolor=CHARCOAL,
    linewidth=0.6,
)
ax.set_xlim(0, 0.7)
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.set_xlabel("Share of 317 decisions with enough comparison cases")
ax.set_title("The closest matched decision had the same direct-penalty outcome in 59% of cases")
for bar, count, rate in zip(bars, nearest_counts.values, nearest_rates.values, strict=True):
    ax.text(0.02, bar.get_y() + bar.get_height() / 2, f"{count} cases  ({rate:.1%})", va="center", color="white", fontweight="bold")
fig.tight_layout()
save_and_show(
    fig,
    "final_similarity_screen.png",
    "The closest matched decision had the same direct sporting-penalty outcome in 186 of 317 cases and a different outcome in 131 cases.",
    "The matching step did not use the eventual fault finding, penalty, damage, retirement, or finishing result. Warnings and reprimands were kept separate from penalties that directly changed race time, position, or the grid.",
)
"""
        ),
        _markdown(
            """
A model using those three labels produced a ROC AUC of 0.558, where 0.500 represents chance ranking
and 1.000 represents perfect ranking. Its Brier score improved by only 0.0005 over a baseline that
used the overall sanction rate.

In plain terms, broad labels add very little predictive information. This negative result supports
the decision to compare detailed case context instead of treating every collision or every season
as equivalent.

### Test 3: What happens when similar cases are compared?

The matching screen compared decisions on incident type, session, guideline era, first-lap status,
wet conditions, restarts, overlap, and attacker line. It deliberately excluded the later fault
finding, penalty, damage, retirement, and finishing result so the outcome could not define the match.

Warnings and reprimands were kept separate from direct sporting penalties because they do not
immediately change race time, position, or the starting grid. Of the 346 main decisions, 317 had at
least five possible comparison cases and could enter the screen.

The closest match produced the same direct-penalty outcome in 186 cases (58.7%) and a different
outcome in 131 cases (41.3%). That split identifies where the investigation should continue, but it
does not show that stewards made 131 mistakes.

<div class="report-note"><strong>41.3% is not an inconsistency rate:</strong> The matching fields
remain incomplete, and the screen excludes the later fault finding. The 131 differences are review
candidates, not confirmed errors.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-5"></a>

## Chapter 5: Where similar cases still diverge

Chapter 4 left 131 matched cases with different direct-penalty outcomes. The next step restores the
written responsibility finding that was intentionally hidden during matching and asks whether it
explains why the outcomes diverged.

This distinction matters because two incidents can look similar before adjudication but receive
different penalties after the stewards assign different levels of responsibility. That pattern may
raise a question about the fault finding, but it is not an internal mismatch between finding and
sanction.
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
display_rates = display_order / display_order.sum()
bars = ax.barh(
    display_order.index,
    display_rates.values,
    color=[SKY, ORANGE, BLUE],
    edgecolor=CHARCOAL,
    linewidth=0.6,
)
ax.set_xlim(0, 0.84)
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.set_xlabel("Share of the 131 different-outcome matches")
ax.set_ylabel("")
ax.set_title("Most different outcomes also contain a different written fault finding")
for bar, count, rate in zip(bars, display_order.values, display_rates.values, strict=True):
    ax.text(
        rate + 0.012,
        bar.get_y() + bar.get_height() / 2,
        f"{count} cases  ({rate:.1%})",
        va="center",
        fontweight="bold",
        color=CHARCOAL,
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
### What explains the 131 different outcomes?

- **Different written fault finding, 87 of 131 (66.4%):** The paired decisions used different responsibility thresholds.
- **No explicit fault threshold, 30 of 131 (22.9%):** Both rulings required the reader to infer responsibility from the reasons.
- **Off-track advantage context, 14 of 131 (10.7%):** The outcome depended on whether an advantage was retained, returned, or caused by being forced off.

The largest group contains 87 pairs in which the stewards published different responsibility
findings. The sanction then followed that finding, so the unresolved question is whether the
different fault assessments were justified by facts that the matching data could not fully capture.

Another 30 pairs provide no explicit responsibility threshold in either document, which makes the
reasoning difficult to compare from the public text. The remaining 14 depend on whether an off-track
advantage was gained, returned, or caused by another driver.

This audit reduces a broad 41.3% difference rate to more specific questions about how responsibility
and advantage are described. It still cannot turn an incomplete public record into a definitive
error count.

### How well-known controversies fit the framework

The following cases were selected because they show why fans question stewarding consistency and
why broad comparisons can fail. They are explanatory examples, not a random sample and not an
estimate of how often controversial decisions occur.

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

## Chapter 6: What the 2025 public guidelines add

Historical comparisons are difficult because the public decision gives the final sanction but not
always the starting point the stewards used. The FIA's publication of Formula 1 driving standards
and penalty guidance in 2025 created a clearer reference for decisions from that season.

The analysis identified 33 sanctions from 2025 that could be mapped to a published starting point.
It asked whether each sanction was plainly within the guidance, within range after context or
mitigation, or dependent on an unexplained substitution or escalation.

This is a contemporaneous comparison only. The 2025 guidance is never applied to decisions from
2018 through 2024 because doing so would judge earlier decisions against a later public standard.
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

guideline_rates = guideline_summary / guideline_summary.sum()
fig, ax = plt.subplots(figsize=(11, 5.1))
labels = [
    "Within the published starting point",
    "Within range after context or mitigation",
    "Substitution or escalation needs more context",
]
bars = ax.barh(labels, guideline_rates.values, color=[GREEN, SKY, ORANGE], edgecolor=CHARCOAL, linewidth=0.7)
ax.invert_yaxis()
ax.set_xlim(0, 0.78)
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.set_xlabel("Share of 33 comparable 2025 sanctions")
ax.set_ylabel("")
ax.set_title("Most comparable 2025 sanctions follow the published starting point")
for bar, value, rate in zip(bars, guideline_summary.values, guideline_rates.values, strict=True):
    ax.text(rate + 0.012, bar.get_y() + bar.get_height() / 2, f"{value} cases  ({rate:.1%})", ha="left", va="center", fontweight="bold", color=CHARCOAL)
fig.tight_layout()
save_and_show(
    fig,
    "final_guideline_comparison.png",
    "Of 33 comparable 2025 sanctions, 21 were plainly within guideline, seven were within range with context or mitigation noted, and five required more context for a substitution or escalation.",
    "This comparison measures whether the sanction fits the public starting point after the stewards made a fault finding. It does not independently decide whether that fault finding was correct.",
)
"""
        ),
        _markdown(
            """
Of the 33 comparable sanctions, 21 (63.6%) matched the published starting point without further
interpretation. Another seven (21.2%) remained within the published range after the reason given by
the stewards was considered.

Five sanctions (15.2%) used a substitution or escalation that required more context than the public
decision supplied. The analysis treats those five as transparency questions, not guideline
violations, because the stewards may have considered evidence or mitigation that was not published.

This result shows what public guidance can improve. A stated starting point makes similar sanctions
easier to compare, while an explicit explanation for every departure would make the remaining
judgment calls easier to audit.

- [FIA Formula 1 Driving Standards Guidelines, version 4.1](https://www.fia.com/sites/default/files/f1_driving_standards_guidelines_version_4.1_feb_20_2025.pdf)
- [FIA 2025 Penalty Guidelines](https://www.fia.com/sites/default/files/2025_f1_guidelines_penalty_points_overview_-_14_may_clean_0.pdf)
"""
        ),
        _markdown(
            """
<a id="chapter-7"></a>

## Chapter 7: Why penalty length is not the same as race cost

A five-second penalty sounds fixed, but its competitive cost depends on when it is applied and on
the gaps between cars. It can change several positions after the finish, change no position at all,
or alter strategy and traffic when it is served during the race.

The same problem applies to incident harm. A collision can cause no measurable loss, a temporary
delay, a repair stop, lasting car damage, or a retirement, and a multi-car incident can affect each
participant differently.

The study first tested these distinctions on nine source-supported decisions. The examples below
show why nominal seconds, realized penalty cost, and incident harm must remain separate fields.
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
    ("233", "Decision rows involving a collision"),
    ("193", "Distinct incidents after related rows were grouped"),
    ("412", "Driver-specific records for possible harm"),
    ("28", "Timing screens with enough comparison data"),
]
fig, ax = plt.subplots(figsize=(13, 4.0))
ax.set_xlim(0, len(harm_flow) * 3.05)
ax.set_ylim(0, 2.5)
ax.axis("off")
harm_colors = [BLUE, SKY, GREEN, ORANGE]
for index, ((count, label), color) in enumerate(zip(harm_flow, harm_colors, strict=True)):
    x = index * 3.05 + 0.08
    box = patches.FancyBboxPatch(
        (x, 0.50), 2.45, 1.35, boxstyle="round,pad=0.03,rounding_size=0.05", facecolor=color, edgecolor=CHARCOAL, linewidth=0.8
    )
    ax.add_patch(box)
    text_color = "white" if color in {BLUE, GREEN} else CHARCOAL
    ax.text(x + 1.225, 1.38, count, ha="center", va="center", fontsize=19, fontweight="bold", color=text_color)
    ax.text(x + 1.225, 0.91, "\\n".join(textwrap.wrap(label, width=31)), ha="center", va="center", fontsize=10, color=text_color)
    if index < len(harm_flow) - 1:
        ax.annotate("", xy=(x + 2.92, 1.18), xytext=(x + 2.52, 1.18), arrowprops={"arrowstyle": "->", "color": CHARCOAL, "lw": 1.6})
ax.text(6.1, 0.25, "The count rises because one incident can affect several drivers.", ha="center", va="center", fontsize=10)
ax.set_title("Public timing supports only a small screen for possible race harm", fontsize=15, pad=10)
save_and_show(
    fig,
    "final_harm_path.png",
    "The harm workflow groups 233 collision decision rows into 193 incidents, expands them to 412 driver-specific records, and retains 28 records for timing screens.",
    "The 28 timing screens are research leads, not confirmed damage effects. Tyres, traffic, strategy, weather, and hidden car conditions remain alternative explanations for a pace change.",
)
assert damage_manifest["candidate_incident_count"] == 193
assert damage_manifest["participant_record_count"] == 412
assert damage_manifest["participant_rows_with_incident_lap"] == 241
assert layers_manifest["pace_screen_estimable_rows"] == 28
"""
        ),
        _markdown(
            """
Only 28 of the 412 driver-specific records (6.8%) had enough same-lap teammate data for a timing
screen. A slower post-incident pace can identify a case worth researching, but timing alone cannot
separate damage from tyres, traffic, strategy, weather, or an unreported car problem.

No full-corpus case contained all three forms of evidence required for a proportionality conclusion:
a clear fault finding, source-confirmed incident harm, and a measurable realized penalty cost. The
report therefore presents the case examples but does not claim that FIA penalties are generally
proportional or disproportional to race harm.

That withheld result is part of the analysis. It prevents a severe outcome, such as a puncture or
retirement, from being treated as automatic proof that another driver deserved a larger penalty.
"""
        ),
        _markdown(
            """
<a id="chapter-8"></a>

## Chapter 8: Testing the claim of British-driver bias

Claims of British favoritism appear in public debates about Formula 1 stewarding, especially when a
high-profile decision benefits or harms a British driver. Selected controversies cannot test that
claim because memorable cases are not a representative sample.

The study instead compares every British accused driver in the 346-decision main dataset with all
other accused drivers. This is a test of group-level sanction patterns, not a judgment about any
individual driver or steward.

The raw comparison is only a starting point. A credible nationality result also needs enough
British cases, overlap in incident context, and statistical power to detect a difference of the
size defined before the analysis.
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

nationality_plot["display_label"] = nationality_plot.apply(
    lambda row: f'{row["group"]}  ({int(row["sanctions"])} of {int(row["cases"])})', axis=1
)
fig, ax = plt.subplots(figsize=(10.8, 3.6))
y = np.arange(len(nationality_plot))
ax.errorbar(
    nationality_plot["rate"],
    y,
    xerr=[nationality_plot["rate"] - nationality_plot["low"], nationality_plot["high"] - nationality_plot["rate"]],
    fmt="o",
    markersize=9,
    color=BLUE,
    ecolor=CHARCOAL,
    capsize=4,
)
ax.set_yticks(y, nationality_plot["display_label"])
ax.invert_yaxis()
ax.set_xlim(0.35, 0.78)
ax.xaxis.set_major_formatter(PercentFormatter(1))
ax.set_xlabel("Raw sanction rate with 95% confidence interval")
ax.set_title("The uncertainty ranges for the two raw sanction rates overlap")
for index, row in nationality_plot.iterrows():
    ax.text(0.755, index, f'{row["rate"]:.1%}', va="center", ha="right", fontweight="bold")
fig.tight_layout()
save_and_show(
    fig,
    "final_nationality_result.png",
    "British accused drivers have a 56.8 percent raw sanction rate and other accused drivers have a 62.6 percent rate, with overlapping 95 percent confidence intervals.",
    "The British group contains 44 decisions, below the prespecified minimum of 98. The raw 5.8-point difference is not an adjusted effect and the study lacks power for the planned 15-point test.",
)
"""
        ),
        _markdown(
            """
British accused drivers received sanctions in 25 of 44 decisions (56.8%), compared with 189 of 302
decisions for other drivers (62.6%). The British interval extends from 42.2% to 70.3% and the other
group's interval extends from 57.0% to 67.9%, so the raw estimates overlap substantially.

The British group also falls below the prespecified minimum of 98 cases. Simulated power to detect a
15-point difference ranges from 37.8% to 53.6%, well below the study's 80% target, which means a real
difference of that size could easily remain undetected.

The controversy examples in Chapter 5 cannot repair this weakness because they were selected for
explanation and include decisions that both helped and harmed British drivers. FIA documents also
list the stewarding panel but do not publish individual votes, so the study cannot assign an outcome
to one steward's nationality.

<div class="report-answer"><strong>Nationality result:</strong> The observed data do not show a
higher sanction rate for British accused drivers, but the sample is too small to rule out a
meaningful difference. The correct conclusion is inconclusive, not proof of bias and not proof that
bias is absent.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-9"></a>

## Chapter 9: What the study can and cannot conclude

The analysis began with a question about whether Formula 1 stewarding treats similar incidents in a
consistent way. The answer depends on which part of the decision process is being measured.

| Question | Main evidence | Conclusion |
|---|---|---|
| Does the formal outcome follow the written responsibility finding? | 76 of 76 clear blame findings led to sanctions; 24 of 24 racing-incident findings led to no further action | Yes, for the 100 clearest written findings |
| Do broad case labels explain the outcome? | ROC AUC 0.558; Brier improvement 0.0005 | No, incident type and season alone explain very little |
| Do the closest available cases receive the same direct penalty outcome? | 186 of 317 matched cases agreed; 131 differed | Often, but the 41.3% difference rate requires case review |
| What explains the different matched outcomes? | 87 of 131 had different written fault findings | Most differences begin in the responsibility assessment |
| Do 2025 sanctions follow public guidance? | 21 of 33 plainly matched; seven fit with context; five needed more context | Mostly, with a small set of transparency questions |
| Are penalties proportional to incident harm? | No case had complete fault, harm, and realized-cost evidence | The public data cannot answer this at population level |
| Do the data support British-driver bias? | 25 of 44 British cases sanctioned versus 189 of 302 others; power below 80% | Inconclusive |

<div class="report-answer"><strong>Primary result:</strong> The formal outcome aligns with the
written finding in all 100 decisions at the clearest ends of the responsibility scale. The largest
remaining source of variation is the responsibility assessment itself, not a penalty that
contradicts the published finding.</div>

<div class="report-answer"><strong>Final conclusion:</strong> The evidence does not support a claim
that Formula 1 stewarding is systematically inconsistent or biased by driver nationality. It also
does not prove that every fault finding was correct, because close-case context, non-referrals,
incident harm, and individual steward votes remain incomplete.</div>

The study therefore reaches a bounded conclusion. Published decisions are internally consistent in
their clearest language and most 2025 sanctions map to public guidance, but the FIA could make the
system easier to audit by explaining responsibility thresholds and departures from penalty starting
points more explicitly.

### Evidence needed for a stronger answer

- A complete record of comparable incidents that were noted, investigated, or never referred.
- More detailed context for the 131 matched cases with different direct-penalty outcomes.
- Source-confirmed damage, repair stops, retirements, and rare beneficial stops.
- Realized penalty-cost records, especially for penalties served during a race.
- A larger nationality sample and public information about individual steward votes.
"""
        ),
        _markdown(
            """
<a id="chapter-10"></a>

## Chapter 10: What better stewarding data would look like

The main limitations come from disconnected records, incomplete explanations, and missing measures
of realized race cost. The following changes would let future analysis distinguish justified
judgment calls from genuine inconsistency with less inference.

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

- **Archive coverage:** 173 completed championship events, 2018 to 2025.
- **Main dataset:** 346 Race and Sprint driver-conduct decisions from 131 events.
- **Supporting dataset:** 72 qualifying impeding decisions, kept outside the main sanction rate.
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

**Project:** *Does Formula 1 Stewarding Treat Similar Incidents the Same Way?*<br>
**Coverage:** Formula 1 championship seasons 2018 to 2025<br>
**Review disclosure:** GPT-5.6 Sol model-led source audit; separate independently reviewed pilot;
no claim of full-corpus human inter-rater agreement.
"""
        ),
    ]
