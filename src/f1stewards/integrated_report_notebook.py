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

    # Brian authored the opening and Chapters 1-2. Preserve their prose in rewrites.
    return [
        _markdown(
            """
# How Consistent Is Formula 1 Stewarding?

<div class="report-author">
<strong>Brian Zeng</strong><br>
<a href="mailto:bzeng0000@gmail.com">bzeng0000@gmail.com</a><br>
<a href="https://brianbzeng.com">brianbzeng.com</a>
</div>

Admittedly, I’m more of a newcomer to the Formula 1 scene, I only started watching a few years ago. Through my time in the community though, I’ve heard the term “british bias” thrown around more often than not. If you aren’t familiar with the term, it’s the narrative that British drivers in the sport get special treatment over their counterparts in terms of recognition in broadcasting and leniency when it comes to penalties. For our purposes, we’ll focus on the penalty side of things. Fans regularly cherry pick racing incidents to bring up precedent and question the fairness in penalties when a controversial racing incident occurs. Some of the comparisons are understandable, but the broadcast replays rarely ever show the full basis of the stewarding decision. Written rulings are released with every penalty after the race for transparency and they may include details about overlap, control, track position, or mitigation that may have been missed during a race.

Rather than judging solely on racing footage, this study goes over these official records to test whether the data supports the belief that similar incidents receive inconsistent treatment. Doing so, we answer the question: How Consistent Is Formula 1 Stewarding?

While exploring these documents, we cover:

1. The conduct described by the stewards
2. Their finding of responsibility
3. What sanction was imposed

to group similar incidents for comparison.

This separation allows us to tell whether the cases differ based on the penalty or because the stewards reached a different conclusion about fault. To dive deeper into the investigation, I also wanted to explore the actual competitive cost of the penalties we observe. For example, a ten second penalty for a front-runner late in a race would absolutely decimate their chances of scoring well, while a ten second penalty for a back marker wouldn’t have much if any effect on their race. We’ll also revisit the “British bias” narrative, and explore whether British drivers actually receive favorable treatment as well. Both of these questions are more to satisfy my curiosity, and determine whether there can be a genuine conclusion reached because they’re very contingent and luck-involved questions. Therefore, they’re both going to be treated as secondary questions with conclusions limited to what public data/evidence can truly back.
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

To begin, we have to establish what consistency means in this setting. A consistent system should bear similar results over similar conditions, but be able to distinguish two separate incidents if they overlap in conditions. Penalties are subjected, but not limited to: driver control, track position, weather, and even the lap the incident occurred.

Each FIA decision moves through three steps. The stewards describe the incident, decide how much responsibility each driver carried, and select an outcome such as no further action, a warning, or a sporting penalty. A difference at any one of these steps can produce two different final results.

In this study, we’ll go over five steps.

- Conduct: Do comparable driving acts receive comparable responsibility findings?
- Sanction: Do comparable responsibility findings receive comparable penalties?
- Consequence: What happened to each driver affected by the incident?
- Race cost: What did the sanction actually cost after its timing and application are considered?
- Nationality: Do group differences remain credible after sample size and case context are checked?

The five questions aren’t combined into a single score, but rather used to determine whether the stewarding is consistent over the selected areas. Even if fans disagree with the outcome of a penalty, as long as comparable racing incidents receive comparable outcomes, there is evidence of consistency in stewarding.

Steps 4 & 5 are necessary to cover the secondary questions I posed earlier, because a penalty could be correctly assigned under the regulations, but could lead to massively different race costs when compared to the same nominal penalty in another event.

How the report uses the word consistent: A decision is internally consistent when its formal outcome follows its written responsibility finding. Two decisions are comparable only when the public record describes similar incident conditions.
"""
        ),
        _markdown(
            """
<a id="chapter-2"></a>

## Chapter 2: Building the decision dataset

As I previously mentioned, the FIA publishes write ups to every penalty given out during or after the respective event, in an archive. In the same archive, we can also find classifications, summonses, technical reports, and corrected versions of earlier files. So for any given incident, the report that we care about comes with a multitude of other files that we don’t need to inspect.

From their archives, a total of 9,467 files were produced over the span of 173 F1 racing events. By the end, only 346 records were useful for our analysis. The figure below depicts the filtering process for the data obtained.
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
In the first screening, the 9,467 files had their titles scanned for keywords such as “Decision”, “Infringement”, or “Offence” to quickly determine whether the file was relevant to begin with. Out of the entirety of the archives between our target years, only 2,003 candidate files of them contained titles related to stewarding outcomes. To further filter the candidate files, I used Chat GPT-5.6 Sol to iterate through the remaining to remove any duplicates or administrative files and confirm whether they were racing incidents or not. Afterwards, we were only left with 418 candidate files, which were split between 72 qualifying and 346 racing incidents. The qualifying incidents were set aside and kept as a supporting dataset, as the conditions for racing and qualifying are foundationally different, meaning they can’t be treated the same. Mixing them would dilute the results, and make it harder to interpret.

### What one row represents

Each row represents one accused driver in one formal decision, which is the unit the FIA uses when
it identifies an alleged offence and announces an outcome. One collision can therefore produce
several rows if the stewards examine more than one driver. I kept a separate record for the harm
experienced by each participant, since the consequences of the same contact can differ sharply
between cars.

### What the dataset does not contain

The sample begins only after an incident reaches a published decision, so it does not include every
similar action on track. Race Control records could be linked with high confidence to 177 of the
346 main decisions, but that was not enough to reconstruct every incident noted, investigated, or
left alone. Any rate in this report describes published decisions, not the chance that a driver will
be penalized for a given action during a race.

I also left a field unknown when the ruling did not say enough to fill it. A decision that does not
mention damage, for example, is not evidence that no car was damaged. This costs some comparison
cases, but it prevents a short public explanation from creating certainty that the source does not
provide. Lap times and race results can describe what followed an incident; on their own, they
cannot establish who was at fault.
"""
        ),
        _markdown(
            """
<a id="chapter-3"></a>

## Chapter 3: Exploring the published decisions

With the dataset defined, I first wanted to see which kinds of incidents appeared most often and
how frequently the stewards imposed a sanction. The main sample contains 346 Race and Sprint
decisions from 131 events between 2018 and 2025. Stewards imposed a sanction in 214 decisions, or
61.8%, counting warnings and reprimands as well as penalties that affect race time, position, or
the starting grid.

That figure is a useful reference point, but it applies only to incidents that reached a published
decision. It cannot tell us how often similar conduct occurred without a formal ruling. Before
judging whether the stewards treated drivers consistently, I also needed to see whether one type of
incident drove the overall rate.
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
Causing a collision accounts for 233 of the 346 decisions, or about two-thirds of the sample.
Stewards imposed a sanction in 137 of those cases (58.8%), compared with 41 of 54 (75.9%) for
gaining an advantage off track and 23 of 43 (53.5%) for forcing another driver off track. The
categories describe different conduct and ask the stewards to consider different circumstances, so
these rates alone cannot show whether similar incidents received different treatment.

The highest bars also come from some of the smallest groups. Unsafe rejoins resulted in sanctions
in seven of eight decisions, while multiple defensive moves did so in five of six. There were only
two moving-under-braking cases, meaning one different outcome would change that category's rate by
50 percentage points. The wide intervals in the figure show why those percentages should not be
treated as a ranking of steward strictness.

The rate also changes from season to season. The lowest observed figure was 40.9% in 2019, when 18
of 44 decisions ended in a sanction; the highest was 75.9% in 2021, or 22 of 29. By 2025 it was
60.3% (38 of 63), close to the overall rate rather than continuing in one direction. That
variation does not establish that the stewards became stricter or more lenient, since the mix of
incidents, referral practices, available evidence, and applicable guidance can change as well.

These figures show where published decisions are concentrated, but neither incident labels nor
seasons explain why the stewards reached a particular outcome. The next step is to read their
written findings of responsibility and ask whether the sanction follows that finding.
"""
        ),
        _markdown(
            """
<a id="chapter-4"></a>

## Chapter 4: Testing how decisions are made

The first figures describe how often a sanction followed each type of incident, but not how the
stewards reached their decision. I approached that question in three stages: compare the outcome
with the written finding of fault, test what broad case labels can predict, and then find closer
comparisons using circumstances described before the outcome.

### Does the written fault finding match the outcome?

The clearest place to start is inside the ruling itself. When the stewards say one driver was wholly
or predominantly to blame, a sanction would be expected; when they call it a racing incident, no
further action would be expected. This checks whether the formal outcome follows their own stated
finding, not whether that finding was correct.
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
All 76 decisions that found a driver wholly or predominantly to blame imposed a sanction. All 24
racing-incident findings ended with no further action. In this group of 100 clear findings, the
formal outcome never contradicted the responsibility stated in the document.

That is internal agreement, not proof that fault was assigned correctly. A viewer might disagree
with a finding after watching the incident and still acknowledge that the penalty followed the
stewards' written conclusion. Testing the finding itself would require an independent review of
the incident evidence and the rule in force at that event.

Other rulings are less direct: some omit an explicit blame threshold, while off-track advantage
depends on whether a gain was made, retained, or returned. To see how much those distinctions
matter, I next tested whether simpler labels could anticipate the outcome without using the final
fault finding.

### Can broad case labels predict the outcome?

I fitted a simple model with incident type, season, and whether the incident involved more than two
cars. It was tested on events held out from training, so its score reflects cases from races it had
not seen. The point was not to let a model assign penalties; it was to learn whether those broad
labels carried much information about the stewards' choices.
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
The model's ROC AUC was 0.558, where 0.500 is chance ranking and 1.000 is perfect ranking. Its
Brier score improved by just 0.0005 over assigning every decision the overall sanction rate. On
held-out events, incident type, season, and multi-car involvement added little predictive value.
That does not rule out every simple explanation, but it shows why a collision label on its own is
too coarse for the comparison I wanted to make.

### What happens when similar cases are compared?

The matching screen used incident type, session, guideline era, first-lap status, wet conditions,
restarts, overlap, and attacker line. It did not use the eventual fault finding, sanction, damage,
retirement, or finishing result, since allowing those later facts to define similarity would make
the test circular. Warnings and reprimands were kept separate from penalties that directly affect
race time, position, or the grid.

Of the 346 main decisions, 317 had at least five candidate comparisons. For 186 of them (58.7%),
the closest available decision had the same direct-penalty result; for 131 (41.3%), it differed.
This is a useful list of cases to inspect, not an estimate that 41.3% of stewarding decisions were
wrong. The context fields came from machine-assisted extraction and still need independent review;
a decisive detail missing from those fields could explain an apparent difference.

<div class="report-note"><strong>How to read the 41.3%:</strong> It describes the outcome of a
matching screen, not a confirmed inconsistency or error rate.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-5"></a>

## Chapter 5: Investigating different outcomes

The 131 different-outcome matches are the place where the broad rates become individual cases.
After finding those matches without using the result, I returned to the written fault findings to
see where the decisions parted ways. If two rulings assign different responsibility, their
different penalties might each follow the stewards' own reasoning. The harder question is whether
the incidents really warranted those different findings.
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

In 87 of the 131 different-outcome comparisons (66.4%), the written fault categories also differ.
That locates the documented difference earlier than the sanction, although the extracted matching
fields may miss the fact that justified it. Another 30 comparisons (22.9%) have no explicit fault
threshold in either ruling, and 14 (10.7%) concern off-track advantage, where returning a place or
retaining a gain can change the analysis.

This second look makes the screen more useful without turning it into an error count. It shows
whether the public documents offer the same responsibility finding, a different one, or no common
threshold to compare. The independent incident-context review planned for these matches is still
unfinished, so none of the 131 is labeled a confirmed inconsistency here.

### How well-known controversies fit the analysis

I also read several rulings that fans regularly use as precedents. They help explain why criticism
persists and why two replay clips that look alike can lead to different outcomes once the written
findings are considered. I selected them for the questions they raise, not as a random sample of
all decisions, so they cannot show how common controversial rulings are.

| Case and source | Recorded parameters | Assessment |
|---|---|---|
| [Canada 2019](https://www.fia.com/sites/default/files/decision-document/2019%20Canadian%20Grand%20Prix%20-%20Offence%20-%20Car%205%20(re-joinged%20unsafely%20and%20forced%20car%2044%20of%20the%20track).pdf) and [Austria 2019, Document 50](https://www.fia.com/sites/default/files/doc_50_-_2019_austrian_grand_prix_-_decision_-_car_33_turn_3_incident_with_car_16.pdf) | Canada: Car 5, unsafe rejoin, Car 44 forced off, five seconds; Austria: Cars 33 and 16, Turn 3, no predominant fault, no further action | Different incident types and fault thresholds prevent a direct precedent comparison. |
| [Silverstone 2021, Document 50](https://www.fia.com/sites/default/files/doc_50_-_2021_british_grand_prix_-_offence_-_car_44_-_causing_a_collision_with_car_33.pdf) | Car 44, Turn 9, predominantly at fault, ten seconds, two penalty points; Car 33 retired and Car 44 won | The contrast between the sanction and the other driver's retirement raises a proportionality question, but does not measure a no-incident counterfactual. |
| [São Paulo 2021, Document 55](https://www.fia.com/sites/default/files/bra_doc_55_-_decision_-_mercedes_-_right_of_review_0.pdf) | Turn 4; forward and 360-degree footage classified as new, unavailable, and relevant; review rejected because the evidence was not significant | The record documents a limit in live evidence without proving the original outcome was incorrect. |
| [Abu Dhabi 2021 WMSC review, 19 March 2022](https://www.fia.com/sites/default/files/2021_f1_abu_dhabi_grand_prix_-_report_to_the_wmsc_-_19_march_2022.pdf) | Safety Car procedure; conflicting interpretations of Articles 48.12 and 48.13; direct team radio pressure | The case concerns Race Control procedure and remains outside the 346 driver-conduct decisions. |
| [Austin 2024, Document 69](https://www.fia.com/sites/default/files/decision-document/2024%20United%20States%20Grand%20Prix%20-%20Infringement%20-%20Car%204%20-%20Leaving%20the%20track%20and%20gaining%20an%20advantage.pdf) and [Mexico 2024, Document 47](https://www.fia.com/sites/default/files/decision-document/2024%20Mexico%20City%20Grand%20Prix%20-%20Infringement%20-%20Car%201%20-%20Turn%204%20Forcing%20another%20driver%20of%20the%20track%20(corrected).pdf) plus [Document 44](https://www.fia.com/sites/default/files/decision-document/2024%20Mexico%20City%20Grand%20Prix%20-%20Infringement%20-%20Car%201%20-%20Turn%208%20Leaving%20the%20track%20and%20gaining%20an%20advantage.pdf) | Austin: Car 4, five seconds; Mexico: Car 1, Turn 4 and Turn 8, ten seconds for each ruling | The documents record different apex, space, and retained-advantage findings under the same broad standard. |

### Cases that remain difficult to reconcile

| Case and source | Recorded parameters | Assessment |
|---|---|---|
| [Japan 2024, Car 63 and Car 81](https://www.fia.com/sites/default/files/decision-document/2024%20Japanese%20Grand%20Prix%20-%20Decision%20-%20Car%2063%20-%20Alleged%20forcing%20car%2081%20off%20the%20track.pdf) | Car 81 left the track to avoid contact, rejoined safely, retained the position, and received no action | The decision states that the driving standards did not cover this sequence. |
| [Hungary 2025, Document 38](https://www.fia.com/system/files/decision-document/2025_hungarian_grand_prix_-_decision_-_car_22_-_alleged_forcing_another_driver_off_of_the_track.pdf) and [Italy 2025, Document 38](https://www.fia.com/system/files/decision-document/2025_italian_grand_prix_-_infringement_-_car_31_-_forcing_another_driver_off_the_track.pdf) | Hungary: Car 22 forced Car 27 off, both contributed, correct order restored, no action; Italy: Car 31 failed to leave Car 18 space, five seconds | The public reasons use restoration of order differently, so the pair remains unresolved. |

Canada and Austria in 2019 illustrate one comparison problem: both involve a car being forced toward
the edge of the track, yet the documents use different incident categories and responsibility
thresholds. The pair raises a fair question, but it does not test the same rule under matched
conditions. Austin and Mexico in 2024 are closer in broad standard, though the written reasons
still differ on apex position, available space, and whether an advantage was retained.

Other records leave more room for debate. The Japan 2024 ruling says the driving standards did not
cover the particular sequence in which a driver avoided contact and retained position, while the
Hungary and Italy 2025 rulings discuss restoration of order and shared contribution differently.
Those explanations do not prove either result wrong. They show why a reader may reasonably want a
clearer account of how the responsibility threshold was applied.

The case studies give the numerical screen a human-scale meaning, but they cannot validate every
match. The 87 differing fault labels identify where to look first; footage, event-date guidance,
and independently reviewed context are still needed before calling any pair inconsistent.

- [FIA driver meeting on guideline revisions](https://www.fia.com/news/fia-stewards-open-constructive-dialogue-formula-1-drivers)
- [FIA explanation of the 2025 guideline publication](https://www.fia.com/news/fia-insights-guiding-principles-how-fia-bringing-even-more-transparency-application-f1)
"""
        ),
        _markdown(
            """
<a id="chapter-6"></a>

## Chapter 6: Checking decisions against the 2025 guidelines

Comparing the size of penalties across years is harder when an older ruling does not state the
starting point the stewards used. The FIA's public 2025 Driving Standards Guidelines and Penalty
Guidelines give a more explicit reference for decisions made under that guidance. I used them to
review 33 sanctions from 2025 that could be mapped to a published starting point, without applying
the 2025 documents to earlier seasons.
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
        "Within range; needs case context": int(
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
    "Within range; needs case context": 7,
    "Substitution or escalation needs context": 5,
}

guideline_rates = guideline_summary / guideline_summary.sum()
fig, ax = plt.subplots(figsize=(11, 5.1))
labels = [
    "Within the published starting point",
    "Within range; needs case context",
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
    "Of 33 comparable 2025 sanctions, 21 plainly matched a guideline starting point, seven needed case context to interpret, and five required more explanation for a substitution or escalation.",
    "This comparison measures whether the sanction fits the public starting point after the stewards made a fault finding. It does not independently decide whether that fault finding was correct.",
)
"""
        ),
        _markdown(
            """
Of those 33 sanctions, 21 (63.6%) plainly matched the published starting point. Seven more (21.2%)
fell within a guideline range that required case context to interpret; some records note mitigation
or possible mitigation, while others concern the no-immediate-consequence range. I did not treat all
seven as cases with documented mitigating factors.

The remaining five (15.2%) involved a substitution or escalation that the public ruling did not
fully explain against the starting point. That makes them transparency questions, not proven rule
violations. A fuller explanation of the baseline and the reason for moving away from it would make
these cases easier to evaluate without pretending the published document contains every fact the
stewards considered.

- [FIA Formula 1 Driving Standards Guidelines, version 4.1](https://www.fia.com/sites/default/files/f1_driving_standards_guidelines_version_4.1_feb_20_2025.pdf)
- [FIA 2025 Penalty Guidelines](https://www.fia.com/sites/default/files/2025_f1_guidelines_penalty_points_overview_-_14_may_clean_0.pdf)
"""
        ),
        _markdown(
            """
<a id="chapter-7"></a>

## Chapter 7: Separating penalties from race consequences

A written penalty does not tell us what it cost a driver on track. Five seconds added after a race
could change two positions or none, while five seconds served during a pit stop might change the
traffic and strategy that follow. I therefore kept the nominal sanction separate from its observed
competitive burden.

The harm caused by the incident is another question. A collision can briefly delay one driver,
damage another car for the rest of the race, force a repair stop, or end a third driver's afternoon.
Those consequences belong to each affected driver, not to the collision as a single row. A
nine-decision pilot with source-supported reviews helped test whether the data structure could keep
sanction, burden, and harm distinct.
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
The two five-second examples show how far observed costs can separate. Pérez's Abu Dhabi 2023
penalty was added after the finish and moved him from a provisional P2 to P4, costing two places,
six championship points, and a podium. Colapinto's Austria 2025 penalty changed neither his final
place nor his points.

Tsunoda served a ten-second penalty during the Austrian race, so simply subtracting ten seconds
from his final time would invent a race he did not drive. Antonelli carried a three-place grid
penalty to the next event and started P10 rather than P7, but the resulting effect on his finish
cannot be isolated. In the nine-decision pilot, affected-driver records also included one
incident-caused retirement, three observed one-place losses, and one possible damage report with
no immediate place loss. The pilot supports case-level descriptions, not a general rule about how
much a given penalty should cost.
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
Across the full collision screen, 233 decision rows were grouped into 193 distinct incidents, then
expanded to 412 driver-specific records for possible harm. Only 52 had the data needed to enter the
timing comparison, and 28 of those (6.8% of all 412 harm records) produced an estimable pace screen.
That narrow funnel is one reason this report does not claim a population-wide damage estimate.

A slower pace after contact can point toward a case worth checking, but it cannot prove damage or
measure how much time damage cost. Tyres, traffic, strategy, weather, or a separate car problem can
produce the same pattern. The 28 timing screens therefore remain leads for source review. No
full-dataset case passed the preregistered combination of clear fault, confirmed harm, and
measurable realized penalty cost needed to release a proportionality finding. The pilot can show
what happened in specific cases; it cannot establish whether FIA penalties generally match the
harm incidents caused.
"""
        ),
        _markdown(
            """
<a id="chapter-8"></a>

## Chapter 8: Testing the nationality claim

The British-bias question from the introduction deserves its own test, rather than a list of
memorable calls. I compared the British accused drivers in the 346 Race and Sprint decisions with
the other accused drivers, starting with the share of each group that received a sanction. A lower
British rate would point in the direction the favoritism claim predicts, but it would not explain
why the groups differ. Incident mix, written fault findings, and sample size all matter before a
raw gap can be interpreted.
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
British accused drivers received a sanction in 25 of 44 decisions (56.8%), compared with 189 of
302 (62.6%) for other drivers. That 5.8-percentage-point raw gap is in the direction the favoritism
claim predicts, but it is not an adjusted estimate of preferential treatment. The 95% confidence
intervals overlap: 42.2% to 70.3% for British drivers and 57.0% to 67.9% for the other group.

The study's planned test required at least 98 British decisions; this dataset has 44. Simulated
power to detect a 15-point difference was 37.8% to 53.6%, below the 80% target. In practical
terms, the study might miss a meaningful gap even if one existed, and the observed gap could also
reflect case mix or sampling variation. The controversy examples cannot repair this weakness,
since they were chosen to explain disputes rather than represent all rulings. FIA documents name
the panel but do not disclose individual votes, so they cannot show how any one steward contributed.

<div class="report-answer"><strong>Nationality result:</strong> The raw difference points in the
direction of the favoritism claim, but the sample and power requirements were not met. The
nationality question remains open.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-9"></a>
<a id="conclusion-tldr"></a>

## Chapter 9: Answering the research question

### TL;DR

<div class="report-answer"><strong>Short answer:</strong> The formal outcome followed the written
finding in all 100 decisions with the clearest responsibility language. A separate matching screen
found 131 of 317 decisions whose closest available comparison had a different direct-penalty
result, but those matches need independent context review before they can be called inconsistent.
The nationality and penalty-versus-harm questions remain unresolved.</div>

The answer depends on which part of the decision process is being measured. Published rulings give
clear evidence about whether a sanction followed a stated responsibility finding, but less certainty
about whether two different findings were equally justified by the incidents on track. The table
keeps those questions, and the strength of each answer, separate.

| Question | Main evidence | Conclusion |
|---|---|---|
| Does the outcome follow a clear written finding? | All 76 clear blame findings led to sanctions; all 24 racing-incident findings led to no further action. | These 100 decisions are internally consistent; the fault findings were not independently validated. |
| Can broad labels predict a sanction? | Incident type, season, and multi-car involvement gave ROC AUC 0.558 and Brier improvement 0.0005. | Those labels added little predictive information on held-out events. |
| What did the close-case screen find? | Of 317 decisions with enough candidate support, 186 nearest comparisons had the same direct-penalty outcome and 131 differed. | The 131 differences are review priorities, not confirmed stewarding errors. |
| Where did those outcomes diverge? | In 87 of the 131 different-outcome comparisons, written fault categories differed. | The documents show a fault-assessment difference; whether it was justified needs further review. |
| How did 2025 sanctions compare with public guidance? | Of 33 comparable sanctions, 21 plainly matched, seven needed case context to interpret, and five needed more explanation. | Most of this selected group fit the framework; the five are transparency questions, not proven breaches. |
| Did penalties match incident harm? | No full-dataset case passed the clear-fault, confirmed-harm, and measurable-cost release gate. | A population-level proportionality claim cannot be made. |
| Did British drivers receive preferential treatment? | Sanctions followed 25 of 44 British-accused decisions and 189 of 302 others. | The raw gap is directionally compatible with the claim, but the planned sample and power gates failed. |

The strongest finding is narrow: the formal outcome followed the written finding in all 76 clear
blame decisions and all 24 racing-incident decisions. That says the sanction process aligned with
the stewards' stated conclusion in these cases. It does not tell us whether the original judgment
of responsibility was correct.

The matching analysis looks earlier in that process. Its 131 different-outcome comparisons deserve
attention, especially the 87 with different written fault categories, but the matching context was
machine-extracted and has not completed independent review. The closest available match may omit
the detail that decided the case. I would not turn those counts into a percentage of inconsistent
rulings.

The case studies explain why fans can still have reasonable questions. Some documents identify
overlap, apex position, or a returned advantage that a broadcast comparison might miss, while
others leave the responsibility threshold harder to reconstruct. The 2025 guidance offers a clearer
reference for the sanction that follows a finding, though five selected rulings would benefit from
more public explanation of how their penalty was chosen.

<div class="report-answer"><strong>Conclusion:</strong> Published outcomes align with clear written
fault findings. The close-case screen identifies decisions worth reviewing, but it does not yet
establish how often fault was assigned inconsistently. The available data also leave the
nationality and penalty-versus-harm questions unanswered.</div>

That is not a declaration that stewarding is always fair. The dataset misses comparable incidents
that never reached a formal decision, and it cannot reconstruct every camera angle or piece of
telemetry considered at the time. Race harm, in-race penalty cost, and individual steward votes
also remain incomplete or unavailable.

### Evidence needed for a stronger answer

- Independent review of the 131 flagged comparisons using footage, decision text, and event-date guidance.
- A fuller record of comparable conduct that was noted, investigated, or never referred.
- Source-confirmed damage, repair stops, retirements, and any stops with a real strategic benefit.
- Penalty-service and race-state records that can support observed competitive-cost estimates.
- More British-accused decisions with comparable context for an adequately powered nationality test.
"""
        ),
        _markdown(
            """
<a id="chapter-10"></a>

## Chapter 10: Improving future stewarding analysis

The main obstacle was not a shortage of rulings. It was the difficulty of linking a decision to
the incident that prompted it, the evidence the stewards considered, and the later consequences for
each driver. Better links among those records would make comparisons easier to test without
requiring anyone to agree with every stewarding judgment.

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

None of these changes would remove discretion. Stewards would still judge overlap, control,
avoidance, and other circumstances in real time, but readers could see more clearly which facts led
them to a particular finding. A nominal penalty and its later race consequence should remain
separate: documenting the sanction is possible, while reconstructing the race that would have
happened without it often is not.

The 131 different-outcome matches are the most direct next review target. Each needs footage,
decision text, and event-date guidance checked by an independent reviewer before it can be called
inconsistent. The 28 timing screens can guide damage research in the same way, provided an external
source confirms the car's condition and alternative explanations for any pace change are examined.
A longer nationality study would still need comparable cases and enough British decisions to meet
its planned statistical threshold, not simply more seasons added indiscriminately.
"""
        ),
        _markdown(
            """
<a id="methods"></a>

## Methods, limitations, and reproducibility

The chapters above explain the choices needed to follow the argument. This section gathers the
scope, source roles, and release limits in one place so readers can check what each result
represents and reproduce the analysis if they wish.

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

The study uses linked tables rather than one fairness score. The conduct record holds the accused
driver and written responsibility finding; the consequence record tracks possible harm for each
affected driver; and the sanction record holds the formal outcome and how it was applied. Timing
and Race Control feeds establish observable events, not a second judgment of fault.

- **Archive coverage:** 173 completed championship events, 2018 to 2025.
- **Main dataset:** 346 Race and Sprint driver-conduct decisions from 131 events.
- **Supporting dataset:** 72 qualifying impeding decisions, kept outside the main sanction rate.
- **Primary unit:** one accused-driver decision in a Race or Sprint.
- **Primary scope:** causing a collision, forcing another driver off track, gaining an advantage
  off track, unsafe rejoining, moving under braking, and multiple defensive moves.
- **Close-case screen:** outcome-blind matching on extracted pre-outcome circumstances; independent
  incident-context review remains incomplete, so differences are research leads only.
- **Validation:** broad-label prediction was tested on held-out events; the nine-decision consequence
  pilot received independent double review, while the full 418-decision source audit was model-led.
- **Tools:** Python, Jupyter, pandas, DuckDB SQL, partitioned Parquet, Git, and automated tests.
- **Portability:** a locally validated Snowflake/Snowsight package is included; no live remote
  deployment is claimed.

The model-led audit includes a citation and evidence passage for every included decision, which
makes a classification inspectable but does not establish human reviewer agreement on every row.
Passing the descriptive release checks also does not make an unreviewed close-case inference
publishable.

### Important limitations

Each limit below changes what can be concluded from the available public record.

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

The evidence checks distinguish a descriptive result that can be reported from a claim that still
needs review. A source citation is necessary for an included decision, but it is not a substitute
for independent validation of a disputed comparison.

| Finding | Evidence level | Release decision |
|---|---|---|
| Source inventory and 418 included decisions | Source-cited, model-led audit | Descriptive scope and counts |
| Full-corpus sanction and responsibility rates | Source-cited decision table | Descriptive associations, not independent fault judgments |
| Broad-label prediction model | Grouped out-of-event validation | Negative result; no case ranking |
| Close-case outcome contrasts | Outcome-blind matching on candidate context; independent context review pending | Review priorities, not confirmed inconsistencies |
| Selected controversy cases | Official decisions plus FIA governance records | Bounded interpretation of those cases, not a prevalence estimate |
| Nine-decision penalty-cost pilot | Independent double review | Case-level release |
| Full collision damage and pace effects | Timing and source screening | No population damage claim |
| 2025 guideline comparison | Contemporaneous public guidance | Descriptive/contextual release |
| Nationality association | Failed sample-size and power gates | Inconclusive |

<details>
<summary>Reproduction notes</summary>

The executable version is `notebooks/12_study_v2_report.ipynb`. The report reads immutable,
content-addressed source-audit and Study v2 artifacts.

Rebuild with `python scripts/build_study_v2_notebooks.py`, then run `pytest`,
`ruff check src scripts tests`, `python scripts/audit_study_v2_completion.py`, and
`python scripts/audit_report_style.py`. The style check tests the public report rules rather than
claiming compliance with a formal editorial standard.

The public HTML hides code for readability. The notebook retains the executable code and outputs.

</details>
"""
        ),
        _markdown(
            """
<a id="citations"></a>

## Sources and citations

The sources do different jobs. FIA regulations and event-date guidelines establish the relevant
rules, while steward decisions record the official finding in a particular case. Classifications
and timing describe observed race results; attributed team or driver accounts can add limited
case-specific damage evidence. I did not use timing, news reports, or team statements to assign
fault, and the tables below keep governing material separate from supporting context.

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

The independently reviewed consequence pilot also used the following non-decision sources. Each
supports the case-specific fact stated here, not a general estimate of damage or penalty cost:

- [Gasly's Abu Dhabi 2023 damage account](https://www.formula1.com/en/latest/article/gasly-says-damage-with-hamilton-and-perez-finished-me-after-p13-result-at.4oooNkg91ON0oLVrNxcJSs): attributed diffuser damage and downforce loss, with earlier contact kept as a confounding cause.
- [Official Abu Dhabi 2023 race report](https://www.formula1.com/en/latest/article/verstappen-beats-leclerc-to-victory-in-abu-dhabi-to-end-record-breaking-year.6pYEohQvxeey5ATWkXh8sQ): race order and incident sequence around the Pérez and Norris contact.
- [Alpine's Austrian 2025 debrief](https://media.alpinecars.com/2025-formula-one-austrian-grand-prix-sunday/?lang=eng): Colapinto's first-party report that the car felt different after contact; coded as possible, not confirmed, damage.
- [Official Austrian 2025 race analysis](https://www.formula1.com/en/latest/article/austria-lowdown-all-the-key-moments-as-the-mclarens-duel-red-bull-suffer-and.7DG4DaK04hYZKL97D6xjr9): the effect of backmarker traffic on Piastri's pursuit, without assigning an exact time loss.
- [Verstappen's Austrian 2025 post-race account](https://www.formula1.com/en/latest/article/no-one-does-that-on-purpose-verstappen-gives-verdict-on-unlucky-race-ending.1WQnU9ao4YlVIuvewwaSOg): contextual confirmation of the race-ending collision, paired with the FIA classification.
- [Official British 2025 race report](https://www.formula1.com/en/latest/article/norris-wins-dramatic-wet-dry-british-gp-from-piastri-as-hulkenberg-claims.1puOD82avOZ8I0sca7fvLJ): race context after Antonelli served the carried Austrian grid penalty; not used to invent a counterfactual finish.

Third-party databases, media searches, broadcasts, photographs, and social posts helped identify
leads, but did not establish the published fault or fairness findings.

### Decision-level FIA sources

Every included primary and secondary decision has a direct FIA citation. The 418-row table is
collapsed to keep the main argument readable, while the downloadable audit also contains 502
exclusion checks, evidence passages, correction history, rule sources, confidence fields, and
review status.
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
