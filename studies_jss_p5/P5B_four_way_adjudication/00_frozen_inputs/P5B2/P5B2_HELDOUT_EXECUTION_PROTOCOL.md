# P5B.2 held-out execution protocol

Current status: HELD_OUT_STATIC_ACCESS_PREREQUISITES_SATISFIED_EXECUTION_NOT_AUTHORIZED.

This freeze does not execute or authorize a held-out case. A separate task must
qualify a held-out-only runner and require both --execute-authorized and
JSS_P5B_HELDOUT_AUTHORIZED=YES before creating output. Only the four frozen IDs
may run, each in two fresh single-process, single-thread processes. No replacement,
reseeding, tuning, threshold change, or additional case is permitted. Every null,
adverse, invalid, unsupported, execution-error, or duplicate-failure result is retained.
