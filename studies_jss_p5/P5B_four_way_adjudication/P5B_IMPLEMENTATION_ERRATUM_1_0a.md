# P5B implementation-contract erratum 1.0a

## Reason for revision

The static preflight implementation correctly encoded verdict precedence, but
formal review identified two trust-boundary gaps before any formal case was
executed.

First, the subject adapter accepted a runtime-provided precomparison relation
without independently checking it against the frozen case contract. Second,
the runtime result validator did not fully constrain each outcome to its
declared stopping stage and evaluation flags.

## Correction

`JSS-P5B-IMPL-1.0a` adds the following checks:

- runtime and frozen precomparison relations must match;
- observed replay-packet differences must equal the mechanism-specific frozen
  difference tuple;
- execution errors stop at `EXECUTION`;
- `NOT_SUPPORTED` stops at `APPLICABILITY`;
- `INVALID` stops at `ELIGIBILITY`;
- `PASS_INVARIANT` and `DETECT_LIFECYCLE_DRIFT` require complete lifecycle
  evaluation;
- pass results cannot carry active violation signals, while detection results
  must name at least one active signal;
- formal requests are restricted to a declared partition;
- a separate DEVELOPMENT guard uses exact case lists, protected hashes, and
  two authorization locks while refusing all held-out IDs.

## Scientific boundary

This erratum changes no case ID, subject, mechanism, history, expected verdict,
threshold, oracle, partition, or held-out rule. No formal P5B case existed when
the correction was made. The original `JSS-P5B-IMPL-1.0` package is retained as
a read-only snapshot under `00_frozen_inputs/P5B_preflight`.
