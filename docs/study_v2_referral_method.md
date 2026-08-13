# Study v2 Race Control Referral Method

The referral funnel uses Race and Sprint process messages from the public Formula 1 timing feed,
accessed through FastF1 and stored session-by-session. It does not call that feed a complete FIA case
management system.

Messages are parsed into six states: noted, investigation, post-session investigation, no
investigation, no further action, and sanction announced. Nearby messages are grouped using event,
session, named car set, location, incident family, explicit incident lap, and message time. Every
named car is preserved. Terminal states take precedence over earlier process states, but the full
message sequence remains in JSON.

Episodes are linked to primary adjudications using car roles, incident family, location, explicit lap,
and whether the terminal message agrees with the broad sanction/no-action result. The algorithm
stores its score and basis. High-confidence links still require validation; close alternatives are
marked ambiguous, lower-scoring candidates remain pending, and unmatched decisions and episodes stay
visible.

This produces an observable public funnel rather than the true universe of on-track conduct. A
missing process message can mean the incident was not publicly messaged, the feed is incomplete, or
the document concerns a different path. It must not be interpreted as proof that Race Control ignored
an incident. Conversely, a noted incident is not proof of wrongdoing.
