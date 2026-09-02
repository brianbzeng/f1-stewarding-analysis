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
# How Consistent Is Formula 1 Stewarding?

<div class="report-author">
<strong>Brian Zeng</strong><br>
<a href="mailto:bzeng0000@gmail.com">bzeng0000@gmail.com</a><br>
<a href="https://brianbzeng.com">brianbzeng.com</a>
</div>

## What FIA decisions from 2018 to 2025 show about fault, penalties, and fairness

Formula 1 fans regularly compare two incidents and ask why one driver received a penalty while
another did not. These comparisons are understandable, but a television replay rarely shows the
full basis of a stewarding decision. The written ruling may include details about overlap, control,
track position, or mitigation that are easy to miss during a race.

This study tests whether the official record supports the belief that similar incidents receive
inconsistent treatment. Each decision is followed through three separate stages: the conduct
described by the stewards, their finding of responsibility, and the sanction they imposed. This
separation identifies whether two cases differ because of the penalty or because the stewards first
reached different conclusions about fault.

Two additional questions address claims that often appear in public debate. First, does the written penalty
reflect the actual competitive cost to the driver? Second, do the available decisions support the
claim that British drivers receive favorable treatment? Both are treated as secondary questions,
and conclusions are limited to what the public evidence can support.
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

PILOT = Path(
    os.environ.get(
        "F1STEWARDS_REPORT_PILOT",
        ROOT / "data/manual/reconciled/pilot-41f4502411c2",
    )
)
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
<li><a href="#chapter-1">Defining a fair comparison</a></li>
<li><a href="#chapter-2">Building the decision dataset</a></li>
<li><a href="#chapter-3">Exploring the published decisions</a></li>
<li><a href="#chapter-4">Testing how decisions are made</a></li>
<li><a href="#chapter-5">Investigating different outcomes</a></li>
<li><a href="#chapter-6">Checking decisions against the 2025 guidelines</a></li>
<li><a href="#chapter-7">Separating penalties from race consequences</a></li>
<li><a href="#chapter-8">Testing the nationality claim</a></li>
<li><a href="#conclusion-tldr">Conclusion TL;DR</a></li>
<li><a href="#chapter-9">Answering the research question</a></li>
<li><a href="#chapter-10">Improving future stewarding analysis</a></li>
<li><a href="#methods">Methods, limits, and reproducibility</a></li>
<li><a href="#citations">Sources and citations</a></li>
</ol>
"""
        ),
        _markdown(
            """
<a id="chapter-1"></a>

## Chapter 1: Defining a fair comparison

The analysis began by defining what consistency means in this setting. A consistent system should reach
similar conclusions when the conduct and surrounding conditions are similar. It should not assign
the same penalty to every collision, because two collisions can differ in overlap, driver control,
track position, weather, or other facts used by the stewards.

Each FIA decision moves through three steps. The stewards describe the incident, decide how much
responsibility each driver carried, and select an outcome such as no further action, a warning, or
a sporting penalty. A difference at any one of these steps can produce two different final results.

The analysis separates the problem into five questions so that one type of difference is not mistaken
for another:

1. **Conduct:** Do comparable driving acts receive comparable responsibility findings?
2. **Sanction:** Do comparable responsibility findings receive comparable penalties?
3. **Consequence:** What happened to each driver affected by the incident?
4. **Race cost:** What did the sanction actually cost after its timing and application are considered?
5. **Nationality:** Do group differences remain credible after sample size and case context are checked?

The nationality question tests a specific claim about favorable treatment for British drivers. It
is included because the claim appears often in fan discussions, not because it is assumed to be true.
The evidence needed to evaluate group bias is also different from the evidence needed to compare
two individual incidents.

The five questions were not combined into one fairness score. A decision can be internally
consistent because the penalty follows the written fault finding, even if an outside reviewer
disagrees with that finding. A penalty can also be correct under the rules but create a much smaller
or larger race cost than the same nominal penalty in another event.

<div class="report-method"><strong>How the report uses the word consistent:</strong> A decision is
internally consistent when its formal outcome follows its written responsibility finding. Two
decisions are comparable only when the public record describes similar incident conditions.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-2"></a>

## Chapter 2: Building the decision dataset

The FIA publishes decisions as separate documents within each event archive. The same archive also
contains classifications, summonses, technical reports, and corrected versions of earlier files.
For this reason, every archive entry could not be treated as one stewarding decision.

A total of 9,467 files were collected from 173 completed championship events and screened in stages.
Only records that could answer the research question were retained, and the direct FIA source was
preserved at every stage. The figure below shows how the broad archive became the main Race and
Sprint dataset.
"""
        ),
        _code(
            """
flow = [
    ("9,467", "All FIA event files collected"),
    ("2,003", "Possible decisions after title screening"),
    ("418", "Source-verified decisions in the selected categories"),
    ("346", "Race and Sprint decisions in the main analysis"),
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
ax.set_title("How the main decision dataset was built", fontsize=15, pad=10)
save_and_show(
    fig,
    "final_population_path.png",
    "The source review reduces 9,467 FIA event files to 346 Race and Sprint driver-conduct decisions.",
    "The 418 verified decisions contain 346 Race and Sprint cases for the main analysis and 72 qualifying impeding cases used only for supporting context.",
)
"""
        ),
        _markdown(
            """
The title screen identified 2,003 files that could contain a steward outcome. The source documents
were then opened, administrative files and duplicate versions were removed, and decisions outside
the selected incident categories were excluded. This process left 418 verified decisions with
direct FIA citations.

The main analysis uses 346 decisions about driver conduct during a Race or Sprint. Another 72
qualifying impeding decisions were kept as a separate supporting dataset because qualifying and
racing create different conditions. Mixing them would make the main sanction rate harder to
interpret.

### What one row represents

One row represents one accused driver in one formal decision. This unit matches the structure of an
FIA ruling, which usually identifies the driver being investigated and the outcome assigned to that
driver. A multi-car crash can create several decision rows, while a separate harm table records what
happened to every affected participant.

### What the dataset does not contain

The dataset contains formal decisions, not every comparable action that occurred on track.
High-confidence Race Control referral links were found for 177 of the 346 main decisions, but that
coverage was not enough to build a complete set of incidents that were noted, investigated, or
ignored. The results are therefore conditional on an incident reaching the published decision stage.

Missing information was also treated as unknown. If a document did not describe overlap, damage, or
mitigation, the condition was not assumed to be absent. This choice reduces the number of cases
available for some comparisons, but it prevents silence in a short ruling from becoming false
evidence.

These limits determine what the study can answer. Patterns can be tested within published decisions,
but the rate at which comparable conduct was never referred cannot be estimated. Fault also cannot
be assigned from lap timing or a race result when the supporting incident evidence is missing.
"""
        ),
        _markdown(
            """
<a id="chapter-3"></a>

## Chapter 3: Exploring the published decisions

Before individual cases were compared, the overall shape of the dataset was examined. The 346 main
decisions came from 131 Race or Sprint events, and 214 decisions (61.8%) ended in some form of
sanction. This percentage describes published decisions in the selected categories, not the chance
that any action on track will be penalized.

The decisions were first grouped by incident type. This provides a baseline for understanding which
categories usually lead to sanctions and which categories contain more uncertainty. A difference
between categories is not evidence of unfair treatment by itself, because the conduct and decision
standard can also differ.
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
Causing a collision accounts for 233 of the 346 decisions, making it the only incident family large
enough to dominate the overall rate. Stewards imposed a sanction in 137 of those cases (58.8%). The
rate was 75.9% for gaining an advantage off track (41 of 54) and 53.5% for forcing another driver
off track (23 of 43).

The remaining categories contain between two and eight decisions each. Their percentages may look
different, but the wide confidence intervals show how little precision those small samples provide.
For example, the unsafe-rejoin rate is based on eight decisions, while the moving-under-braking rate
is based on only two.

The annual sanction rate also changes across the study period, from 40.9% in 2019 to 75.9% in 2021.
This range cannot be interpreted as a direct change in steward strictness because the mix of incidents,
available evidence, referral practice, and guidance can change by season. The season plot identifies
variation that needs explanation rather than giving the explanation itself.

This exploratory step showed that incident type and season are related to the observed rate, but
neither explains how the stewards reasoned through a case. The analysis therefore moves from broad
categories to the responsibility language written in each decision.
"""
        ),
        _markdown(
            """
<a id="chapter-4"></a>

## Chapter 4: Testing how decisions are made

The exploratory results describe the outcome, but they do not explain why the stewards reached it.
For that reason, the decision process was tested at three levels. The written fault finding was
first compared with the final outcome, then the predictive value of broad case labels was measured,
and finally cases were matched using the detailed context available before the outcome.

### Does the written fault finding match the outcome?

This is the most direct test of internal consistency. A finding that one driver was wholly or
predominantly to blame should normally lead to a sanction. A racing-incident finding should normally
lead to no further action.
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
The clearest responsibility findings align exactly with the final outcome. All 76 decisions that
found a driver wholly or predominantly to blame imposed a sanction, while all 24 racing-incident
findings ended with no further action. Within these 100 decisions, no formal outcome contradicted
the written responsibility finding.

This result measures internal agreement, not whether the stewards assigned fault correctly. To
answer that second question, the evidence would need to be reconstructed and the relevant rule
applied independently in every case. The distinction matters because fans may reasonably disagree
with a fault finding even when the penalty follows that finding in a consistent way.

The middle categories are less direct. Some decisions do not state a clear blame threshold, while
off-track advantage cases depend on whether an advantage was gained, retained, or returned. The next
test asks whether simpler labels can explain these outcomes without using the final fault finding.

### Can broad case labels predict the outcome?

A simple model was fit using incident type, season, and whether more than two cars were involved. Its
purpose was not to automate stewarding or decide which driver deserved a penalty. Instead, the model
served as a diagnostic test of whether broad labels contain enough information to reproduce outcomes
at events it had not seen.
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
The model produced a ROC AUC of 0.558, where 0.500 represents chance ranking and 1.000 represents
perfect ranking. Its Brier score improved by only 0.0005 over a baseline that assigned the overall
sanction rate to every decision. These values show that the three broad labels add very little
predictive information.

This weak performance is useful because it rules out a simple explanation. Knowing that a case was
a collision in a particular season is not enough to anticipate the outcome. A stronger comparison
therefore needed more of the incident context recorded before the stewards reached their finding.

### What happens when similar cases are compared?

Decisions were matched using incident type, session, guideline era, first-lap status, wet conditions,
restarts, overlap, and attacker line. The later fault finding, penalty, damage, retirement, and
finishing result were intentionally excluded. This design prevents the outcome from deciding which
cases count as similar.

Warnings and reprimands were also separated from penalties that directly change time, position, or
the starting grid. Of the 346 main decisions, 317 had at least five possible comparison cases and
could enter the matching screen. This support rule prevented isolated cases from being compared with
a single weak match.

The closest available case had the same direct-penalty outcome in 186 decisions (58.7%) and a
different outcome in 131 decisions (41.3%). The 131 differences identify cases that need additional
review, but they do not show that the stewards made 131 errors. The matching data may still omit a
fact that explains why the two decisions diverged.

<div class="report-note"><strong>How to read the 41.3% result:</strong> This is the share of matched
cases with different direct-penalty outcomes. It is a review rate, not an estimated stewarding error
rate.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-5"></a>

## Chapter 5: Investigating different outcomes

The matching screen produced 131 decisions whose closest comparison had a different direct-penalty
outcome. The written responsibility finding that had been excluded from the matching step was then
restored. This tests whether the outcomes differed because the stewards first reached different
conclusions about fault.

This distinction changes the interpretation of a disputed pair. If two incidents receive different
fault findings, the later difference in penalties may follow the written reasoning correctly. The
remaining question is whether the public facts justify the different fault assessments.
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

The written fault finding differed in 87 of the 131 pairs (66.4%). In these pairs, the sanction
usually followed the finding, so the disagreement begins with the stewards' assessment of
responsibility. The matching fields may not contain every detail needed to decide whether that
difference was justified.

Another 30 pairs (22.9%) had no explicit fault threshold in either ruling. A reader can see the
outcome, but the short public explanation does not provide a shared responsibility standard for the
comparison. The final 14 pairs (10.7%) involved off-track advantage, where the result can depend on
whether the advantage was retained, returned, or caused by another driver.

This second review gives the 41.3% result a more useful meaning. Most different outcomes are linked
to a different fault assessment, while the remaining cases are difficult to compare because the
public reasoning is incomplete or uses a different decision framework. These categories still
cannot be converted into a confirmed error count.

### How well-known controversies fit the analysis

The same framework was next applied to several well-known controversies. These examples show where
fan criticism comes from and why two incidents that look similar can produce different official
results. The cases were selected for explanatory value, so they are not a random sample and cannot
measure how often controversial decisions occur.

| Case and source | Recorded parameters | Assessment |
|---|---|---|
| [Canada 2019](https://www.fia.com/sites/default/files/decision-document/2019%20Canadian%20Grand%20Prix%20-%20Offence%20-%20Car%205%20(re-joinged%20unsafely%20and%20forced%20car%2044%20of%20the%20track).pdf) and [Austria 2019, Document 50](https://www.fia.com/sites/default/files/doc_50_-_2019_austrian_grand_prix_-_decision_-_car_33_turn_3_incident_with_car_16.pdf) | Canada: Car 5, unsafe rejoin, Car 44 forced off, five seconds; Austria: Cars 33 and 16, Turn 3, no predominant fault, no further action | Different incident types and fault thresholds prevent a direct precedent comparison. |
| [Silverstone 2021, Document 50](https://www.fia.com/sites/default/files/doc_50_-_2021_british_grand_prix_-_offence_-_car_44_-_causing_a_collision_with_car_33.pdf) | Car 44, Turn 9, predominantly at fault, ten seconds, two penalty points; Car 33 retired and Car 44 won | The case measures proportionality between conduct and harm, not nationality bias. |
| [São Paulo 2021, Document 55](https://www.fia.com/sites/default/files/bra_doc_55_-_decision_-_mercedes_-_right_of_review_0.pdf) | Turn 4; forward and 360-degree footage classified as new, unavailable, and relevant; review rejected because the evidence was not significant | The record documents a limit in live evidence without proving the original outcome was incorrect. |
| [Abu Dhabi 2021 WMSC review, 19 March 2022](https://www.fia.com/sites/default/files/2021_f1_abu_dhabi_grand_prix_-_report_to_the_wmsc_-_19_march_2022.pdf) | Safety Car procedure; conflicting interpretations of Articles 48.12 and 48.13; direct team radio pressure | The case concerns Race Control procedure and remains outside the 346 driver-conduct decisions. |
| [Austin 2024, Document 69](https://www.fia.com/sites/default/files/decision-document/2024%20United%20States%20Grand%20Prix%20-%20Infringement%20-%20Car%204%20-%20Leaving%20the%20track%20and%20gaining%20an%20advantage.pdf) and [Mexico 2024, Document 47](https://www.fia.com/sites/default/files/decision-document/2024%20Mexico%20City%20Grand%20Prix%20-%20Infringement%20-%20Car%201%20-%20Turn%204%20Forcing%20another%20driver%20of%20the%20track%20(corrected).pdf) plus [Document 44](https://www.fia.com/sites/default/files/decision-document/2024%20Mexico%20City%20Grand%20Prix%20-%20Infringement%20-%20Car%201%20-%20Turn%208%20Leaving%20the%20track%20and%20gaining%20an%20advantage.pdf) | Austin: Car 4, five seconds; Mexico: Car 1, Turn 4 and Turn 8, ten seconds for each ruling | The documents record different apex, space, and retained-advantage findings under the same broad standard. |

### Cases that remain difficult to reconcile

| Case and source | Recorded parameters | Assessment |
|---|---|---|
| [Japan 2024, Car 63 and Car 81](https://www.fia.com/sites/default/files/decision-document/2024%20Japanese%20Grand%20Prix%20-%20Decision%20-%20Car%2063%20-%20Alleged%20forcing%20car%2081%20off%20the%20track.pdf) | Car 81 left the track to avoid contact, rejoined safely, retained the position, and received no action | The decision states that the driving standards did not cover this sequence. |
| [Hungary 2025, Document 38](https://www.fia.com/system/files/decision-document/2025_hungarian_grand_prix_-_decision_-_car_22_-_alleged_forcing_another_driver_off_of_the_track.pdf) and [Italy 2025, Document 38](https://www.fia.com/system/files/decision-document/2025_italian_grand_prix_-_infringement_-_car_31_-_forcing_another_driver_off_the_track.pdf) | Hungary: Car 22 forced Car 27 off, both contributed, correct order restored, no action; Italy: Car 31 failed to leave Car 18 space, five seconds | The public reasons use restoration of order differently, so the pair remains unresolved. |

The Canada and Austria decisions from 2019 illustrate a common comparison problem. Both involved a
driver being forced toward the edge of the track, but the FIA documents used different incident
categories and responsibility thresholds. The pair can still motivate a useful discussion, but it
does not provide a controlled comparison of the same rule.

The Austin and Mexico decisions from 2024 are closer because they use the same broad driving
standard. Their written reasons still differ on apex position, space, and whether an advantage was
retained. These details show why a label such as "forcing another driver off track" cannot replace
the full decision text.

Japan 2024 and the Hungary and Italy decisions from 2025 remain harder to reconcile from the public
record. The reasons refer to avoiding contact, restoring the original order, and shared contribution
in ways that do not create one clear comparison rule. These cases do not prove systematic
inconsistency, but they show where additional written explanation would improve transparency.

Across the full matching audit, 87 of the 131 different outcomes can be traced to a different
written fault finding. The other 44 either lack an explicit shared threshold or depend on off-track
advantage context. This is the part of the dataset where public concern about inconsistency has the
strongest basis, even though the evidence is not sufficient to label the decisions incorrect.

- [FIA driver meeting on guideline revisions](https://www.fia.com/news/fia-stewards-open-constructive-dialogue-formula-1-drivers)
- [FIA explanation of the 2025 guideline publication](https://www.fia.com/news/fia-insights-guiding-principles-how-fia-bringing-even-more-transparency-application-f1)
"""
        ),
        _markdown(
            """
<a id="chapter-6"></a>

## Chapter 6: Checking decisions against the 2025 guidelines

Historical penalty comparisons have a basic limitation: the public ruling does not always state the
starting penalty the stewards considered. In 2025, the FIA published Formula 1 driving standards and
penalty guidance that made this process easier to evaluate. These documents provide a benchmark for
decisions made while that public guidance was in effect.

The analysis found 33 sanctions from 2025 that could be mapped to a published starting point. Each
sanction was classified by whether it plainly matched the guidance, fit the published range after
context or mitigation, or used a substitution or escalation that needed more explanation. The 2025
guidance was never applied retrospectively to decisions from 2018 through 2024.
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
Of the 33 comparable sanctions, 21 (63.6%) matched the published starting point without additional
interpretation. Seven more (21.2%) remained within the published range after the context or
mitigation described by the stewards was considered. Together, 28 of the 33 sanctions fit the public
guidance or its stated range.

The remaining five sanctions (15.2%) used a substitution or escalation that required more context
than the public decision supplied. These were classified as transparency questions rather than rule
violations because the stewards may have considered evidence that was not included in the document.
The data support a question about explanation, not a conclusion that the sanction was improper.

This comparison shows the value of a public starting point. It gives analysts and fans a shared
reference for evaluating the sanction after fault has been assigned. The remaining uncertainty
could be reduced if each decision stated the starting point and explained every mitigation,
escalation, or substitution.

- [FIA Formula 1 Driving Standards Guidelines, version 4.1](https://www.fia.com/sites/default/files/f1_driving_standards_guidelines_version_4.1_feb_20_2025.pdf)
- [FIA 2025 Penalty Guidelines](https://www.fia.com/sites/default/files/2025_f1_guidelines_penalty_points_overview_-_14_may_clean_0.pdf)
"""
        ),
        _markdown(
            """
<a id="chapter-7"></a>

## Chapter 7: Separating penalties from race consequences

A written penalty and its competitive cost are not the same measurement. A five-second penalty can
change several positions when added after the finish, change no position when the next driver is far
behind, or affect traffic and strategy when served during the race. Comparing penalty seconds alone
therefore misses part of the result.

Incident harm creates a separate measurement problem. Contact can cause a brief delay, a puncture,
a repair stop, lasting damage, or a retirement. In a multi-car incident, each participant can suffer
a different outcome, so harm was recorded at the driver level instead of assigning one consequence
to the entire incident.

This structure was first tested on nine source-supported decisions. The examples below show why the
written sanction, its realized competitive burden, and the harm from the incident were kept in
separate fields.
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
The same five-second sanction produced two different observed costs in the pilot. Pérez lost two
positions, six championship points, and a podium after his Abu Dhabi 2023 penalty was added at the
finish. Colapinto's five-second Austria 2025 penalty changed neither his position nor his points.

Penalties served before the finish are harder to reconstruct. Tsunoda served ten seconds during the
race, so subtracting ten seconds from his final time would ignore changes in strategy and traffic.
Antonelli's three-place grid penalty moved his starting position from P7 to P10 at the next event,
but its effect on his finishing position could not be isolated.

The nine harm records included one incident-caused retirement, three observed one-place losses, and
one possible damage report without an immediate place loss. These cases confirmed that harm must be
recorded for each driver and supported by a source. They also showed that a written penalty cannot
serve as a substitute for measuring what the affected drivers lost.
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
The full collision screen began with 233 decision rows, which represented 193 distinct incidents
after related rulings were grouped. Expanding those incidents to every potentially affected driver
created 412 harm records. Only 28 records (6.8%) had enough same-lap teammate data for a timing
screen, which makes a population-level damage estimate impractical with the available data.

A slower pace after contact can identify a case for further source review, but it cannot establish
damage by itself. Tyres, traffic, strategy, weather, or an unrelated car problem can create the same
pattern. The 28 timing results were therefore treated as research leads rather than confirmed effects.

No case in the full dataset contained all three forms of evidence needed for a proportionality
conclusion: a clear fault finding, source-confirmed harm, and a measurable realized penalty cost.
The pilot examples can be described, but the data cannot show whether FIA penalties are generally
proportional or disproportional to race harm. Withholding that conclusion prevents a severe outcome
from being treated as automatic proof that another driver deserved a larger penalty.
"""
        ),
        _markdown(
            """
<a id="chapter-8"></a>

## Chapter 8: Testing the nationality claim

Claims of favorable treatment for British drivers appear frequently after high-profile stewarding
decisions. A collection of memorable examples cannot test that claim because fans are more likely
to remember unusual or championship-relevant incidents. A useful test must compare the full group
of British accused drivers with the other accused drivers in the main dataset.

This analysis asks whether the observed sanction rate differs by driver nationality. It does not
judge any individual driver or steward, and it does not assume that a raw group difference is caused
by bias. A credible result also requires enough British cases, comparable incident context, and
enough statistical power to detect a meaningful difference.
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
British accused drivers received sanctions in 25 of 44 decisions (56.8%). Other accused drivers
received sanctions in 189 of 302 decisions (62.6%), a raw difference of 5.8 percentage points in the
opposite direction from the favoritism claim. The 95% confidence intervals overlap, from 42.2% to
70.3% for British drivers and from 57.0% to 67.9% for other drivers.

The sample cannot support a strong conclusion from that difference. The British group contains 44
decisions, below the prespecified minimum of 98. Simulated power to detect a 15-point difference was
37.8% to 53.6%, well below the 80% target, so a meaningful difference could remain undetected.

The controversy examples from Chapter 5 cannot solve this problem because they were chosen for
explanation rather than representation. FIA documents identify the stewarding panel but do not
publish individual votes, which also prevents a decision from being linked to one steward's
nationality. These limitations keep the nationality analysis descriptive.

<div class="report-answer"><strong>Nationality result:</strong> The observed sanction rate was not
higher for British accused drivers, but the sample was too small to rule out a meaningful group
difference. The result is inconclusive. It is not evidence that nationality bias exists, and it is
not proof that nationality bias is absent.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-9"></a>
<a id="conclusion-tldr"></a>

## Chapter 9: Answering the research question

### TL;DR

<div class="report-answer"><strong>Short answer:</strong> Formula 1 stewarding is consistent after
a clear responsibility finding, but meaningfully inconsistent at the point where responsibility is
assigned. The closest matched case had a different direct-penalty outcome in 131 of 317 decisions
(41.3%), and 87 of those 131 differences began with a different written fault finding. This is
evidence of uneven judgment at the boundary, not a 41.3% stewarding error rate.</div>

The study asks whether Formula 1 stewarding treats similar incidents consistently. The results
do not support a single yes-or-no answer because consistency changes depending on which part of the
decision process is measured. The summary below connects each research question to the evidence used
to answer it.

| Question | Main evidence | Conclusion |
|---|---|---|
| Does the formal outcome follow the written responsibility finding? | 76 of 76 clear blame findings led to sanctions; 24 of 24 racing-incident findings led to no further action | Yes, for the 100 clearest written findings |
| Do broad case labels explain the outcome? | ROC AUC 0.558; Brier improvement 0.0005 | No, incident type and season alone explain very little |
| Do the closest available cases receive the same direct penalty outcome? | 186 of 317 matched cases agreed; 131 differed | Often, but the 41.3% difference rate requires case review |
| What explains the different matched outcomes? | 87 of 131 had different written fault findings | Most differences begin in the responsibility assessment |
| Do 2025 sanctions follow public guidance? | 21 of 33 plainly matched; seven fit with context; five needed more context | Mostly, with a small set of transparency questions |
| Are penalties proportional to incident harm? | No case had complete fault, harm, and realized-cost evidence | The public data cannot answer this at population level |
| Do the data support British-driver bias? | 25 of 44 British cases sanctioned versus 189 of 302 others; power below 80% | Inconclusive |

<div class="report-answer"><strong>Main finding:</strong> The formal outcome matched the written
finding in all 100 decisions at the clearest ends of the responsibility scale. Most variation among
the closest cases began when the stewards assigned responsibility, not when they selected a penalty
afterward.</div>

The first part of the decision process appears internally consistent. Every clear blame finding led
to a sanction, and every racing-incident finding led to no further action. Most comparable 2025
sanctions also followed the public starting point or its stated range.

The more difficult question is whether the stewards assigned responsibility consistently across
similar incidents. Among the 131 closest matches with different direct-penalty outcomes, 87 also had
different written fault findings. Some of those differences may reflect incident details missing
from the structured data, while others remain difficult to explain from the public reasons.

<div class="report-answer"><strong>Conclusion:</strong> The available evidence shows meaningful
inconsistency in how responsibility is assigned near the decision boundary, but not a systematic
breakdown across the full stewarding process. Written findings and sanctions align strongly, while
similar-looking cases can still receive different fault assessments. The nationality analysis
remains inconclusive.</div>

This conclusion is narrower than a claim that the FIA is always fair. The study cannot measure
comparable incidents that were never referred, and it cannot reconstruct every camera angle or
piece of telemetry used by the stewards. It also lacks complete measures of incident harm,
in-race penalty cost, and individual steward votes.

Stewards often make these decisions quickly with limited live evidence, which makes some variation
understandable. Time pressure is context, however, not proof that a particular difference was
justified. The public record still needs a clearer explanation when comparable incidents receive
different responsibility findings.

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

## Chapter 10: Improving future stewarding analysis

The largest limitations came from disconnected records, short public explanations, and missing
measures of actual race cost. Better reporting would not remove judgment from stewarding, but it
would make the basis of that judgment easier to compare. The following changes would reduce the
amount of inference required from outside analysts.

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

These recommendations follow directly from the analysis. Structured incident IDs would improve the
referral population, clearer responsibility thresholds would strengthen case matching, and explicit
penalty service details would improve the race-cost analysis. None of these changes requires the FIA
to remove discretion from the stewards.

The next version of this study should focus on the 131 matched outcome differences and the 28 timing
screens with enough comparison data. Those cases offer the greatest opportunity for targeted video,
telemetry, and source review. A larger number of seasons would also improve the nationality analysis,
but only if the incident context remains comparable over time.
"""
        ),
        _markdown(
            """
<a id="methods"></a>

## Methods, limitations, and reproducibility

This section records the technical choices behind the report. These details are kept separate from
the main narrative so the results remain readable while the analysis can still be reproduced and
audited.

### Data sources

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

The study is stored as a set of linked tables rather than one combined fairness score. The conduct
table records the accused driver and written finding, the consequence table records harm to each
affected driver, and the sanction table records the formal outcome and how it was applied.

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

The limitations below are part of the result, not only technical caveats. Each one identifies a
question that the public data cannot answer reliably.

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

A release status was assigned to each major finding before the conclusion was written. Descriptive
results were released when the source and unit of analysis were complete, while claims requiring
missing context or failed statistical gates were withheld.

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

Each source serves a specific purpose. FIA regulations and guidelines define the decision
standard, while steward decisions record the official finding for one incident. Classifications and
timing establish observed race results, and attributed team or driver reports provide limited
case-specific damage evidence.

Timing data, news reports, and team statements were not used to assign fault. The tables below state
the role and limitation of each source group, allowing governing evidence to be separated from
supporting context.

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

Every included primary and secondary decision has a direct FIA citation. The 418-row table is
collapsed so the source audit remains available without interrupting the main report. The
downloadable file also contains 502 exclusion checks, evidence passages, correction history, rule
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

**Project:** *How Consistent Is Formula 1 Stewarding?*<br>
**Coverage:** Formula 1 championship seasons 2018 to 2025<br>
**Review disclosure:** GPT-5.6 Sol model-led source audit; separate independently reviewed pilot;
no claim of full-corpus human inter-rater agreement.
"""
        ),
    ]
