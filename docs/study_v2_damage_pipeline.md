# Study v2 Damage and Harm Pipeline

The unit is an incident–participant record, not a two-car adjudication row. All named cars in a
collision episode receive a separate record. When multiple FIA documents map to the same candidate
Race Control episode, they share one candidate incident key; that grouping remains pending review.

The first pass uses classification status, a pit within two laps of the incident candidate, observed
position movement, multi-car involvement, and clean-lap availability only to prioritize source
research. None of those signals confirms damage or proves that a stop was forced. The output retains
`damage_state=unknown` until an accepted source is reviewed.

Persistent-pace eligibility requires at least five accurate green-flag, non-pit laps on both sides
and five clean teammate laps on both sides. Driver-specific FIA clock mapping supplies a single lap
for 240 of 411 participant records. Fifty-two pass the initial timing screen, and 28 retain five
same-lap teammate comparisons on each side. Their before/after teammate-relative change is saved as
a research screen. It is not a damage estimate until damage, incident lap, causality, traffic,
strategy, weather, and reference choice are independently reviewed. The three- and eight-lap
windows remain sensitivity analyses.

The web-source seeds demonstrate the evidence schema with official Formula 1, team, and attributed
driver reports. They remain `pending` for independent human review and cannot release a damage count.
The full source-research queue includes exact driver, event, team, counterpart, timing signals, and
search terms for every participant.
