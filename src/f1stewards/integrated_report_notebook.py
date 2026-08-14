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

## What eight seasons of public evidence can—and cannot—tell us about fairness in Formula 1 stewarding

**Final integrated report | 2018–2025 seasons | Evidence frozen August 13, 2026**

I began with a question that comes up after almost every disputed race: **are Formula 1 incidents
being judged fairly and consistently?** The answer is more complicated than counting penalties.
A written five-second penalty can cost a podium, change nothing, or alter the strategy of the rest
of a race. A collision can cost another driver a place, a pit stop, persistent damage, or a finish.
And the public decisions cover only incidents that reached the stewards.

This report follows that question from raw FIA documents to a cautious answer. It combines the
source audit, the full 346-case Race/Sprint analysis, public Race Control messages, close-case
matching, a nine-decision impact pilot, collision-harm screening, the 2025 guideline comparison,
and the nationality diagnostic in one narrative.
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
<div class="report-answer"><strong>The short answer.</strong> The public record does not support a
defensible claim that Formula 1 stewarding was systematically unfair, inconsistent, or nationally
biased from 2018 through 2025. It does show that written fault findings align strongly with the
decision to penalize, while broad incident labels alone explain very little. It also shows why a
penalty cannot be evaluated without asking what it actually cost and what happened to every driver
involved.</div>

### Index

<ol class="toc">
<li><a href="#chapter-1">The question I wanted to answer</a></li>
<li><a href="#chapter-2">Turning FIA documents into usable data</a></li>
<li><a href="#chapter-3">What the formal decisions show</a></li>
<li><a href="#chapter-4">Whether similar cases received similar treatment</a></li>
<li><a href="#chapter-5">The 2025 public-guideline comparison</a></li>
<li><a href="#chapter-6">The real cost of a penalty—and of an incident</a></li>
<li><a href="#chapter-7">The nationality question</a></li>
<li><a href="#chapter-8">What I concluded</a></li>
<li><a href="#chapter-9">Recommendations</a></li>
<li><a href="#methods">Methods, limits, and reproducibility</a></li>
<li><a href="#citations">Decision-level FIA sources</a></li>
</ol>
"""
        ),
        _markdown(
            """
<a id="chapter-1"></a>

## Chapter 1 — The question I wanted to answer

The project started with the kind of claim fans make instinctively: one driver “always gets away
with it,” another is punished too harshly, or the stewards apply a different standard from one race
to the next. The controversy is real, but the word *fair* hides several different questions:

1. **Conduct:** did comparable driving acts receive comparable fault findings?
2. **Sanction:** did comparable findings receive comparable penalties?
3. **Consequence:** what harm did the incident cause each affected driver?
4. **Competitive burden:** what did the penalty actually cost the penalized driver?
5. **Distribution:** do outcomes differ systematically by nationality or another characteristic?

Those questions cannot be collapsed into one “fairness score.” A driver can be at fault even when
the other car escapes damage. A severe collision does not automatically prove responsibility. And
a five-second penalty is not compensation paid back to the affected driver.

<div class="report-method"><strong>Study rule:</strong> conduct, harm, and punishment remain separate
throughout the analysis. They are compared only when the supporting evidence exists for each one.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-2"></a>

## Chapter 2 — Turning FIA documents into usable data

The FIA does not publish one tidy table of incidents. The evidence is spread across event pages,
PDF decisions, corrected documents, classifications, regulations, and timing feeds. I first built
an inventory of all completed championship events from 2018 through 2025, then narrowed that
archive to the decisions relevant to driving conduct in Races and Sprints.
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
The public Race Control feed helps reveal what is missing between an on-track event and a formal
decision. It contains 16,039 Race/Sprint messages, from which 1,815 process-state messages form 966
referral episodes. Only 177 of the 346 primary decisions have a high-confidence link to one of
those episodes; 153 links remain candidates and 16 formal decisions remain unmatched. The feed
improves visibility, but it still is not a complete inventory of every comparable incident.

### The main struggles

- **Documents were not clean data.** Corrections and replacements sometimes appeared beside their
  originals. Keeping both would count one ruling twice.
- **The denominator was incomplete.** Formal PDFs show what reached a written decision, not every
  comparable act that happened on track.
- **Incidents were not always two-car events.** One collision can create several accused, affected,
  damaged, or retired-driver records.
- **Damage was rarely standardized.** A floor problem, puncture, broken wing, repair stop, and
  retirement require different evidence.
- **The first broad model asked too much of weak labels.** “Collision” does not describe overlap,
  control, available space, mitigation, or responsibility.

The work therefore moved through a small independently reviewed pilot, a full source inventory, a
strict model-led source audit, and a second study focused on referral coverage, incident timing,
close comparisons, and participant-level harm. Those iterations are preserved in the repository,
but this report uses the final corrected population.

### How the source review worked

GPT-5.6 Sol checked all 418 included decisions and 502 sampled exclusions against a cited source
under a frozen protocol. The 920-row audit confirmed 884 records and corrected 32 included records;
four old archive labels had no publicly recoverable source file and remain visibly unresolved.
Every included decision has an FIA citation and an evidence passage.

This is a disclosed **model-led source audit**, not independent human double-coding. A separate
nine-decision pilot did receive independent review and is labeled accordingly later in the report.
"""
        ),
        _markdown(
            """
<a id="chapter-3"></a>

## Chapter 3 — What the formal decisions show

The primary population contains 346 accused-driver decisions from 131 Race or Sprint events. A
sanction was imposed in 214 cases (61.8%); 132 ended with no further action. These are rates among
formal decisions—not among every incident that occurred.
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
Collision decisions dominate: 233 of the 346 cases, with sanctions in 58.8%. Gaining an advantage
off track produced a sanction in 75.9% of 54 cases; forcing another driver off track did so in 53.5%
of 43. The smallest families appear more severe, but eight unsafe-rejoin cases or two
moving-under-braking cases cannot support a stable league-wide comparison.

Season rates range from 40.9% in 2019 to 75.9% in 2021. That does not prove standards changed from
one year to the next. It mixes different incident facts, rule eras, responsibility findings,
mitigation, and referral choices.
"""
        ),
        _markdown(
            """
<a id="chapter-4"></a>

## Chapter 4 — Were similar cases treated similarly?

I approached this in three layers. First, I checked whether the stewards’ written responsibility
finding aligned with the result. Second, I tested whether broad incident labels could predict a
sanction. Third, I matched cases using only information chosen before looking at the penalty.

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
This is the strongest evidence of **internal coherence** in the formal decisions. Every one of the
76 rulings that explicitly found a driver wholly or predominantly to blame imposed a sanction.
Every one of the 24 rulings called a racing incident ended with no further action. Shared-fault and
less explicit records are more mixed.

That result should not be mistaken for an independent verdict on whether the written finding was
correct. It shows that once the stewards used the clearest responsibility language, the formal
outcome followed it consistently.

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
        "Same sanction decision": int((~nearest["different"]).sum()),
        "Different sanction decision": int(nearest["different"].sum()),
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
axes[0].set_title("Broad labels barely improve ranking")
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
    "A broad-label model scores 0.558 ROC AUC and nearest matched cases have the same sanction outcome in 186 of 317 supported cases.",
    f"The broad model improved Brier score over its baseline by only {model_brier_gain:.4f}. Matching excluded fault, penalty, damage, retirement, and finishing result.",
)
"""
        ),
        _markdown(
            """
A model using only incident family, season, and multi-car status achieved ROC AUC 0.558—barely above
the 0.500 chance-ranking reference—and almost no improvement over a simple sanction-rate baseline.
That is a useful negative result: *collision*, *season*, and *multi-car* are too broad to judge a
ruling.

The outcome-blind matching step was more focused. It matched exact incident family, Race/Sprint
session, and guideline era, then compared available first-lap, wet-track, restart, overlap, and
attacker-line context. Of 317 cases with at least five possible neighbors, the nearest available
match had the same sanction outcome in 186 cases and a different outcome in 131.

<div class="report-note"><strong>Do not read 41% as an inconsistency rate.</strong> The matching fields
remain incomplete, and the comparison intentionally excludes the stewards’ later fault finding.
The 131 differences form a transparent review queue; each pair still needs its facts and reasoning
read side by side.</div>
"""
        ),
        _markdown(
            """
<a id="chapter-5"></a>

## Chapter 5 — What happened under the 2025 public guidelines?

The FIA publicly released Formula 1 driving standards and penalty-guideline material in 2025. I
therefore compared only contemporaneous 2025 rulings to that guidance. Applying later guidance to
older decisions would rewrite the standard after the event.
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
Twenty-one of 33 comparable sanctions were plainly within the public starting point. Seven were
within the available range but involved mitigation or context, and five used a substitute or
escalated sanction that cannot be judged from the public summary alone. None is labeled an unfair
departure without the missing context.

The independently reviewed Austrian 2025 pilot offered a smaller cross-check: four of five
decisions matched the baseline guidance, and the fifth documented mitigation. Together, these
results suggest that the public guidance created a visible framework. They do not establish that
every 2025 judgment was correct or that earlier seasons followed the same standard.

- [FIA Formula 1 Driving Standards Guidelines, version 4.1](https://www.fia.com/sites/default/files/f1_driving_standards_guidelines_version_4.1_feb_20_2025.pdf)
- [FIA 2025 Penalty Guidelines](https://www.fia.com/sites/default/files/2025_f1_guidelines_penalty_points_overview_-_14_may_clean_0.pdf)
"""
        ),
        _markdown(
            """
<a id="chapter-6"></a>

## Chapter 6 — The real cost of a penalty—and of an incident

The independently reviewed pilot made the central practical problem clear: the number written in a
decision is not the same thing as its competitive burden.
"""
        ),
        _code(
            """
pilot_table = pd.DataFrame(
    [
        {
            "Case": "Pérez / Norris — Abu Dhabi 2023",
            "Written sanction": "5 seconds + 2 points",
            "How applied": "Added after the race",
            "Observed competitive burden": "P4 to P2 without penalty; two places, six points, and a podium",
        },
        {
            "Case": "Tsunoda / Colapinto — Austria 2025",
            "Written sanction": "10 seconds + 2 points",
            "How applied": "Served during the race",
            "Observed competitive burden": "Not recoverable by subtracting 10 seconds; strategy and traffic changed",
        },
        {
            "Case": "Colapinto / Piastri — Austria 2025",
            "Written sanction": "5 seconds + 1 point",
            "How applied": "Added after the race",
            "Observed competitive burden": "No classification place and no points changed",
        },
        {
            "Case": "Antonelli / Verstappen — Austria 2025",
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
The same written five seconds cost Pérez a podium and six points, while Colapinto’s five seconds
changed no finishing place or points. Tsunoda served ten seconds during the race, so the penalty
changed the strategy and traffic he experienced; a post-race subtraction would create a false
counterfactual. Antonelli’s grid penalty had a known starting-grid effect but an unknowable race
effect.

The harm side is equally varied. The pilot contains an incident-caused retirement, an observed
next-lap position loss, alleged damage without an immediate place loss, and an off-track excursion
whose time cost could not be isolated. This is why the full collision analysis gives every involved
driver a separate harm record.
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
Only 28 participant records had enough clean, same-lap teammate data for a timing screen. Those
screens remain **research leads**, not damage estimates. Public timing cannot by itself distinguish
a damaged floor from tyre condition, traffic, strategy, weather, or another hidden problem.

The final proportionality table therefore remains closed: no case is released as “punishment was
too small for the harm” until fault, incident-caused harm, and the realized sanction cost are all
supported separately. That choice leaves an important question unanswered, but it avoids turning
missing evidence into a false zero.
"""
        ),
        _markdown(
            """
<a id="chapter-7"></a>

## Chapter 7 — Was there evidence of British bias?

British-driver favoritism is one of the most common public claims. The raw full-corpus comparison
is straightforward: British accused drivers were sanctioned in 25 of 44 decisions (56.8%), while
other accused drivers were sanctioned in 189 of 302 (62.6%). The difference is –5.8 percentage
points.
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
That visible gap is not evidence of favoritism. The British group has only 44 cases against a
prespecified minimum of 98. Simulated power for the planned 15-point difference reaches only 37.8%
to 53.6%, depending on the assumed baseline rate—well below the 80% design target. The study also
does not observe comparable incidents that were never referred.

**Conclusion: nationality remains inconclusive.** The data do not establish British bias, and they
are not strong enough to establish its absence.
"""
        ),
        _markdown(
            """
<a id="chapter-8"></a>

## Chapter 8 — What the data told me

I started by looking for evidence that Formula 1 stewarding was unfair. The strongest defensible
answer is narrower:

1. **The clearest written findings were internally consistent.** All 76 “wholly” or
   “predominantly to blame” decisions imposed a sanction; all 24 racing-incident findings ended
   with no further action.
2. **Broad incident labels were not enough.** A collision label, season, and multi-car flag barely
   predicted a sanction. The details inside the incident and the written responsibility finding
   matter far more.
3. **Close cases deserve review, not automatic condemnation.** The nearest available match differed
   in sanction outcome for 131 of 317 supported cases, but the public context is not rich enough to
   call those differences errors.
4. **The 2025 public framework was visible in the decisions.** Twenty-one of 33 comparable sanctions
   were plainly within guideline and seven more sat within a contextual or mitigated range. Five
   substitutions or escalations need more context.
5. **Penalty size is not competitive cost.** The independently reviewed pilot shows identical
   written seconds producing radically different position and points effects.
6. **The nationality claim cannot be resolved with this sample.** The raw British-driver gap is
   small, uncertain, conditional on formal referral, and underpowered.

<div class="report-answer"><strong>Final conclusion.</strong> The evidence does not prove systematic
unfairness or national bias from 2018 through 2025. It also cannot clear every decision. The most
important weakness is not a single suspicious coefficient; it is the absence of a complete,
structured public trail from on-track incident to referral, reasoning, sanction, harm, and realized
competitive burden.</div>

### What would change this conclusion?

- A more complete referral denominator showing comparable incidents that never reached a decision.
- Independently verified context for the strongest close-case disagreements.
- Source-confirmed damage, repairs, retirements, and rare beneficial stops.
- Realized sanction-cost records, especially for penalties served during a race.
- A larger, adequately powered nationality sample with better decision-maker information.
"""
        ),
        _markdown(
            """
<a id="chapter-9"></a>

## Chapter 9 — Recommendations

### For the FIA

1. **Publish structured decisions.** Provide stable incident and decision IDs, accused and affected
   driver roles, session, lap, turn, finding, sanction, service timing, and version status.
2. **Connect the referral trail.** Link “noted,” “investigated,” “no further action,” and formal
   decision messages to the same incident ID.
3. **Version the guidance.** Identify the driving and penalty guideline active at each event and
   state the normal starting point plus aggravating or mitigating factors.
4. **Separate sanction from consequence.** Publish what the penalty nominally was and when it was
   served; do not imply that seconds alone describe its competitive burden.
5. **Make corrections explicit.** Retain the archive history but mark one effective version so
   outside analysts cannot double-count a ruling.

### For future analysts

1. Use models and close matches to prioritize reading—not to declare a steward wrong.
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

- Official FIA event indexes, decision PDFs, classifications, regulations, and public 2025 guidance.
- FastF1 timing and Race Control feeds for timing and process context—not for assigning fault.
- Official Formula 1, team, driver, or engineer reports for damage research, with interested-party
  claims kept distinct from FIA findings.

### Analytical design

- **Population:** 173 completed championship events, 2018–2025.
- **Primary unit:** one accused-driver decision in a Race or Sprint.
- **Primary scope:** causing a collision, forcing another driver off track, gaining an advantage
  off track, unsafe rejoining, moving under braking, and multiple defensive moves.
- **Tools:** Python, Jupyter, pandas, DuckDB SQL, partitioned Parquet, Git, and automated tests.
- **Portability:** a locally validated Snowflake/Snowsight package is included; no live remote
  deployment is claimed.
- **Validation:** 228 automated tests and 27 final Study v2 release controls passed at the report
  commit.

### Important limitations

1. Formal decisions are conditional on referral and do not represent every on-track act.
2. The full source audit was model-led; it does not measure independent human agreement.
3. Close-case context remains incomplete and is used only to prioritize review.
4. Timing changes cannot by themselves establish damage or its cause.
5. In-race penalty counterfactuals are altered by strategy, traffic, tyres, and later events.
6. The nationality design is underpowered and cannot support an adjusted effect.
7. The 2025 public guidelines are never applied retrospectively to earlier seasons.

### Evidence status

| Finding | Evidence level | Release decision |
|---|---|---|
| Source inventory and 418 included decisions | Strict source-cited model audit | Descriptive release |
| Full-corpus sanction and responsibility rates | Strict source-cited model audit | Descriptive release |
| Broad-label prediction model | Grouped out-of-event validation | Negative result; no case ranking |
| Close-case outcome contrasts | Outcome-blind screening | Review priorities only |
| Nine-decision penalty-cost pilot | Independent double review | Case-level release |
| Full collision damage and pace effects | Timing and source screening | No population damage claim |
| 2025 guideline comparison | Contemporaneous public guidance | Descriptive/contextual release |
| Nationality association | Failed sample-size and power gates | Inconclusive |

<details>
<summary>Reproduction notes</summary>

The executable version is `notebooks/12_study_v2_report.ipynb`. The report reads immutable,
content-addressed source-audit and Study v2 artifacts. Rebuild with
`python scripts/build_study_v2_notebooks.py`, then run `pytest`, `ruff check src scripts tests`, and
`python scripts/audit_study_v2_completion.py`. The public HTML hides code for readability; the
notebook retains it.

</details>
"""
        ),
        _markdown(
            """
<a id="citations"></a>

## Decision-level FIA sources

Every one of the 418 included primary and secondary decisions has a direct FIA citation. The table
is collapsed to keep the main report readable. The downloadable audit also contains the 502
exclusion checks, evidence passages, correction history, rule sources, confidence, and review
status.
"""
        ),
        _code(
            """
decision_citations = strict_cases.loc[
    strict_cases["review_scope"].isin(["primary", "secondary"]),
    ["season", "event_name", "review_scope", "title", "document_id", "fia_decision_citation_url"],
].copy()
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

**Project:** *The Cost of Discretion*  
**Coverage:** Formula 1 championship seasons 2018–2025  
**Final evidence date:** August 13, 2026  
**Review disclosure:** GPT-5.6 Sol model-led source audit; separate independently reviewed pilot;
no claim of full-corpus human inter-rater agreement.
"""
        ),
    ]
