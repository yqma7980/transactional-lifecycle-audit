# P5 F02 dependency postmortem

Status: `OBSERVED_NOT_SUPPORTED_WITH_STATIC_REACHABILITY_TRACE`

All 15 F02 runs contain the exact declared-persistent-field restoration violation and remain finite. `M_R` and `M_J` are exactly zero at every strength, whereas `M_ALPHA` eventually leaves the conventional quiet region. The frozen history therefore contains no secondary operator-separation region.

The static dependency trace rules out a simple disconnected-field explanation: `declared_alpha_cache` is part of persistent state, contributes to `effective_alpha`, and is passed to the material update, where alpha enters the yield criterion. The elastic return is independent of alpha once the branch remains unchanged. That is a plausible masking mechanism, not an observed branch history, because no formal per-integration-point branch ledger was frozen. The evidence does not justify changing the history, mutation site or constitutive state after seeing the result.
