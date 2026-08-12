# Source Register

This register defines the public evidence hierarchy. Exact downloaded versions, effective dates, hashes, and retrieval timestamps will be written to the source manifest during collection.

The pilot's machine-readable event/source assignments live in
`config/regulatory_sources.yml` and load into `metadata.regulatory_sources` plus
`metadata.event_regulatory_sources`. `f1stewards regulatory-audit` prints the matrix.
The full Sporting Regulation publication schedule, International Sporting Code effective windows,
and their event-date selectors are documented in `docs/regulatory_catalog_method.md`; unresolved coverage is explicit in
`reports/regulatory_source_gap_register.csv`.

## Evidence hierarchy

1. Applicable FIA regulation or code in force on the event date.
2. Final FIA steward decision, including a correction or review when applicable.
3. Official final classification and championship-points document.
4. FIA event-specific Race Director instructions and circuit notes.
5. FIA review, protest, or International Court of Appeal decision.
6. Public FIA/F1 timing data accessed through FastF1.
7. Third-party structured data used only for completeness checking.

Third-party summaries cannot overwrite an official source. Conflicts are logged and resolved manually.

## Official FIA sources

| Source | Coverage/use | Known caveat |
|---|---|---|
| [FIA Decision Documents](https://www.fia.com/documents/season) | Event decisions, summonses, event notes, classifications, and championship points | Page structures and document naming vary by season |
| [F1 Regulations Archive](https://www.fia.com/regulation/category/110) | Annual and in-season Sporting Regulation issues | Event-date version must be selected; year alone is insufficient |
| [International Sporting Code and Appendices](https://www.fia.com/regulation/category/123) | Steward authority, sanctions, protests, reviews, appeals, Appendix L and Appendix H | Multiple issues can exist within a year |
| [2025 Formula 1 Penalty and Point Guidelines](https://www.fia.com/sites/default/files/2025_f1_guidelines_penalty_points_overview_-_14_may_clean_0.pdf) | Public Formula 1 sanction baselines/ranges and penalty points | Version dated 14 May; publicly released 25 June 2025; guideline, not regulation |
| [2025 F1 Driving Standards Guidelines v4.1](https://www.fia.com/sites/default/files/f1_driving_standards_guidelines_version_4.1_feb_20_2025.pdf) | Public overtaking and driving-standard tests | Guideline, not regulation |
| [2025 guideline publication and explanation](https://www.fia.com/news/fia-adds-further-transparency-fia-formula-one-world-championship-publication-stewards) | Purpose, history, and non-regulatory status | Historical internal versions are not public |
| [FIA explanation of guideline use](https://www.fia.com/news/fia-insights-guiding-principles-how-fia-bringing-even-more-transparency-application-f1) | Evidence limitations, living-document status, and first-lap tolerance | Explanatory material, not governing law |
| [2018 Azerbaijan Right of Review decision](https://www.fia.com/file/68044/download?token=T9Ow9Dxc) | Historical evidence that realized consequences of penalties were not used to resize the sanction | Event decision; do not assume identical policy wording for every season |
| [2024 Australian GP Car 14 decision](https://www.fia.com/sites/default/files/decision-document/2024%20Australian%20Grand%20Prix%20-%20Infringement%20-%20Car%2014%20-%20Potentially%20dangerous%20driving.pdf) | Direct example in which stewards explicitly did not consider crash consequences | One decision, not a universal rule text |
| [2026 F1 guideline update](https://www.fia.com/news/updated-fia-formula-one-world-championship-stewards-guidelines-driving-standards-penalties) | Future taxonomy and rule-evolution reference | Must not be applied retrospectively to 2018-2025 |
| [FIA International Court of Appeal judgments](https://www.fia.com/judgments-ica) | Final appellate decisions and case-law index | Appeals are selected, not representative of all decisions |
| [2021 Abu Dhabi review](https://www.fia.com/sites/default/files/2021_f1_abu_dhabi_grand_prix_-_report_to_the_wmsc_-_19_march_2022.pdf) | Governance case study | Race Control procedure, not an ordinary steward penalty |

## Event-specific document families

The collector will identify and retain:

- steward decision/infringement/offence;
- summons;
- recalled or corrected decision;
- Right of Review or protest;
- final and provisional classifications;
- championship points;
- Race Director event/competition notes;
- circuit map and event notes;
- relevant scrutineering or timing material when cited in a decision.

## Timing and results sources

| Source | Coverage/use | Known caveat |
|---|---|---|
| [FastF1](https://docs.fastf1.dev/data_reference/index.html) | Timing, laps, pit in/out, tyre age, positions, telemetry, weather, track status, race control, and results from 2018 | Public feed is less complete than FIA/team evidence; individual sessions can be missing and timing alone cannot confirm damage |
| [OpenF1](https://openf1.org/docs/) | Secondary validation for timing, position, and race control from 2023 | Unofficial; not a primary source |

## Completeness-only references

The [F1 Penalties Dashboard](https://github.com/j5t3313/F1_Penalties_Dashboard) may be used to identify possible missing records from 2020-2025. Any record added after that comparison must be independently verified against an FIA document.

## Source limitations that affect claims

- Public evidence is not the full evidentiary record available to stewards.
- The universe of incidents not referred or investigated is not observable.
- Public F1 driving-standard guidelines begin in 2025, although the FIA reports internal use from 2022.
- Regulations and guidelines change during and between seasons.
- Steward decisions are collective; individual votes are not public.
- Driver and steward nationality must be sourced and defined consistently rather than inferred from names.
- Final classifications show official consequences, not the alternate race strategy that would have occurred without a penalty.
- Team debriefs can confirm damage or an incident-responsive stop, but teams are interested parties;
  the timing consequence is independently checked where possible.
- A slow post-incident lap can reflect traffic, tyre condition, fuel, track evolution, damage, or race
  management. It is not damage evidence by itself.

## Pilot event-date assignments

| Event | Sporting Regulations | International Sporting Code | Appendix L / guidelines |
|---|---|---|---|
| 2019 Austria | 12 March 2019 issue | 2019 marked-up edition | 17 June 2019 Appendix L |
| 2023 Abu Dhabi | Issue 7, 25 October 2023 | 2023 clean edition | 19 October archive metadata; current binary is post-event and not used clause-by-clause |
| 2025 Austria | Issue 5, 30 April 2025 | 2025 clean edition | 2025 Appendix L, Driving Standards v4.1, and 14 May Penalty Guidelines |

The 2023 Appendix L mismatch is an explicit source gap, not an invitation to substitute the later
binary. Historical guideline conformance remains `unclear` until the correct version is recovered.
