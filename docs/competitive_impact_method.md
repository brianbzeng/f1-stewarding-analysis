# Competitive Impact Method

Competitive impact is reported as a property of an observed sanction, not as proof that the
underlying decision was correct or incorrect.

## Evidence tiers

| Tier | Label | Allowed claim |
|---|---|---|
| A | `mechanical` | remove a post-race-added time and re-rank the official same-lap cohort |
| B | `bounded` | report a defensible range when direct cost is observed but race response is not fixed |
| C | `modeled` | estimate an outcome only with an independently validated counterfactual model |
| D | `not_estimable` | describe the mechanism without a numerical alternate result |

## Mechanical algorithm

For a post-race-added time penalty:

1. Start with the official final classification and completed-lap total; visually inspect tables
   that are not text-extractable.
2. Compare the official table with the normalized timing feed, then convert result timing to a
   classification gap with the race winner fixed at zero.
3. Subtract only the announced penalty from the penalized driver's official gap.
4. Re-rank against drivers who completed the same number of laps.
5. Retain official order on an exact tie.
6. Recalculate standard finishing-position points; handle fastest-lap or other bonuses separately.

This is deterministic classification arithmetic. It does not simulate a different on-track race.

## Pilot examples, pending review

- Sergio Perez, 2023 Abu Dhabi: removing a five-second post-race addition changes the calculated
  classification from P4 to P2 and standard finishing points from 12 to 18.
- Franco Colapinto, 2025 Austria: removing five seconds leaves the calculated classification at P15.
- Yuki Tsunoda, 2025 Austria: the ten-second penalty was served during the race, so no mechanical
  finishing-position counterfactual is reported.
- Kimi Antonelli, 2025 Austria: the three-place drop applies at the next event, so no Austrian-race
  counterfactual is reported.

All four rows are `single_coded_pending_human`. These are pipeline demonstrations, not final study
findings.
