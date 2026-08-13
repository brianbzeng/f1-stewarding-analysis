# Study v2 Incident Context Method

The context worklist combines three kinds of information without pretending they have equal status:
the model-reviewed FIA decision fields, explicit Race Control message content, and machine-extracted
phrases from the FIA reason text.

An incident lap is retained when already source/timing coded. A missing lap becomes a candidate when
the linked Race Control message explicitly says `LAP n` or when the FIA incident-clock window overlaps
exactly one accused-driver lap. Two-lap clock windows remain ranges. The message's own broadcast lap
is kept only as an upper bound because investigations can be announced many laps later.

The extractor flags explicit first-lap, wet-track, Safety Car restart, inside/outside line, overlap,
corner-phase, and control-error language. It saves the sentences that triggered every flag. Those
fields are review aids, not final geometry: a reason can mention both drivers' lines, and the presence
of “inside” does not by itself identify which driver occupied it.

Close-case matching may use only independently reviewed context. Damage, finish, retirement, penalty,
and other post-incident outcomes are never context predictors.
