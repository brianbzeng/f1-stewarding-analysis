# Steward Country Evidence and Conflict Gate

Status: official-source evidence ledger established; steward-country analysis remains blocked.

## Why this is an evidence ledger

The project initially reserved one static `nationality` field per steward. Source research showed
that this would erase a material ambiguity. FIA publications identify Loïc Bacquelaine as `BEL` in
2016 and in one March 2022 event visa, but as `LUX` in a different July 2022 visa and a 2025 Formula
1 media kit. The codes may represent nationality, sporting licence, or ASN affiliation, and the
same-year conflict rules out treating them as a clean timeless personal attribute without further
adjudication.

The pipeline therefore loads dated evidence before it creates any resolved analytical exposure:

```powershell
f1stewards load-steward-country-evidence
```

The command never updates `curated.stewards.nationality`. It preserves contradictions and keeps
the panel-country release gate closed.

## Source and normalization fields

Each `metadata.steward_country_evidence` row records:

- a stable evidence and steward identity;
- the date represented by the source and whether it is exact, month-, season-, or year-precision;
- the country code exactly as published;
- a separately reviewed code normalized to the project's Formula 1 vocabulary;
- the evidence dimension, source type, URL, title, and interpretation note.

Normalizing `DEU` to `GER`, `PRT` to `POR`, or `NLD` to `NED` does not alter the source value.
`source_country_code` remains available for verification.

Evidence dimensions are not interchangeable:

- `fia_published_country_code`: an FIA list, event visa, or media kit prints a code beside the name;
- `formula1_competition_nationality`: official Formula 1 standings print the former driver's code;
- `fia_asn_affiliation`: an FIA biography ties an official to a national sporting authority; and
- `fia_biographical_country`: an FIA biography explicitly describes a country association.

The first two are direct code evidence. ASN and biographical evidence can guide follow-up research,
but cannot by themselves satisfy the final direct-code control.

## Current research result

| Diagnostic | Result |
|---|---:|
| Official-source evidence records | 45 |
| Panel steward identities | 83 |
| Stewards with any evidence | 38 |
| Stewards with direct FIA/F1 code evidence | 33 |
| Stewards with one observed normalized code | 37 |
| Stewards with no evidence yet | 45 |
| Unresolved source conflicts | 1 |

This is research progress, not an analytical result. Coverage is deliberately counted at identity
grain so a heavily used steward with several sources cannot hide unsourced occasional stewards.

## Release and modeling consequences

`analysis.v_steward_country_evidence_summary` labels each identity as no evidence, a single observed
code not yet temporally resolved, or an unresolved source conflict. Country-based panel features
remain unavailable until every panel steward has direct evidence and conflicts are resolved into
source-supported date intervals or explicitly quarantined.

`analysis.v_steward_country_research_worklist` places conflicts first and then ranks unsourced
identities by decision-document exposure. This makes the research queue operational without
mistaking high-frequency coverage for population completeness.

The completed panel identity layer can still support event-grouped validation, panel fixed or
random effects, and exact membership inspection. The main British-driver outcome design can adjust
for panel identity without claiming that a steward is British. Same-country steward exposure and
claims about the nationality composition of panels remain withheld.

This distinction is important for the report: a country code printed by a sporting body is an
operational research variable, not proof of citizenship, ethnicity, culture, or motive. Even a
fully resolved sporting-country association would support an adjusted association analysis—not a
causal finding of national bias.
