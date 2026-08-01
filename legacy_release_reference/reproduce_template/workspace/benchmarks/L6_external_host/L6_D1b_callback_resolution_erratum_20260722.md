# L6-D1b pre-execution callback-resolution erratum

**Date:** 2026-07-22  
**Status:** IMPLEMENTATION-CONTRACT CORRECTION BEFORE FORMAL EXECUTION

The repeated directed preflight showed that SciPy TRF's callback reports the current accepted state after an outer iteration even when every new trust-region trial in that iteration is rejected. In that situation there is no new residual event with the callback's `x`; the callback repeats the previously accepted `x`.

The original adapter incorrectly required every callback to match a new same-`x` residual event. The correction preserves the last accepted residual event ID, classifies all residual events in the rejected batch as `HOST_NONACCEPTED`, and records the callback as `HOST_ACCEPTED_STATE_UNCHANGED`. A callback with neither a new matching residual nor the previously accepted `x` still raises an error.

This changes no residual, Jacobian, SciPy option, unsafe mechanism, tolerance, case matrix or acceptance threshold. It makes the event resolver conform to the frozen external host's actual callback semantics. No runner, formal case or result directory existed when corrected.

Old adapter SHA-256: `13dfcfcf46e1458571428c5c95ce0309b56c907283eb76660b8dcb462e6a0dd5`.  
Corrected adapter SHA-256: `c3cfb96ff618c019bb577b631b8b618abb76ece983f8252325ffa6aa7f599055`.
