# Study v2 FIA Incident-Clock Mapping

FIA decisions usually provide a local incident clock even when they omit a lap. The warehouse also
stores each event's UTC offset and timestamped FastF1 laps. Study v2 combines them without pretending
a minute-only clock is exact.

For each adjudication, the local clock is converted to UTC using the event-specific offset. A clock
shown as `15:42` becomes the entire interval from 15:42:00 through 15:42:59.999. Every accused-driver
lap interval overlapping that minute is retained. This often produces two possible laps; the range is
sent to review rather than rounded. Seconds-level clocks use a one-second interval.

FastF1 lap 1 begins at the racing start, while a steward clock can reflect the scheduled start or the
formation-lap period. If a clock is no more than five minutes before the first stored lap and the
incident is otherwise a Race/Sprint decision, the mapper emits a separately labeled lap-1 candidate.

The method is validated against every previously coded exact lap. The validation reports whether the
known lap falls inside the generated window, not whether the algorithm happened to choose it. Damage
models use a participant's own lap interval; global Race Control announcement laps remain a separate
upper-bound field.
