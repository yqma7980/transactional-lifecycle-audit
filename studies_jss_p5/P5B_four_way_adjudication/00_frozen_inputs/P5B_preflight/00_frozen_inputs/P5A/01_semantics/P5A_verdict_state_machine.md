# P5A two-stage lifecycle verdict state machine

Version: JSS-P5A-VERDICT-1.0

## Inputs

For histories H1 and H2, the predeclared replay packet is:

D = (x, C, pi_P(P), load, nu_R, nu_J, environment).

The state machine does not infer equality from final outputs. Each component
has a predeclared serializer, tolerance, or compatibility relation.

## Precedence

### Stage 0: applicability and observability

If the host or adapter cannot expose a required lifecycle event or evidence
field under the frozen history, the verdict is NOT_SUPPORTED. This is a
coverage result, not a quiet pass or missed fault.

### Stage 1: comparison eligibility

If observable histories fail a frozen pre-comparison relation, the verdict is
INVALID. Examples are unequal primary state, incompatible committed or
persistent projections, different load or external controls, and versions that
are already incompatible before replay. Invalid comparisons are never tested
for drift.

### Stage 2: eligible lifecycle evaluation

Only an eligible comparison can produce:

- DETECT_LIFECYCLE_DRIFT when an admissible history changes a later operator or
  output, mutates authoritative state, violates ownership, commit, or output
  provenance, or emits an internally incompatible operator packet; or
- PASS_INVARIANT when all frozen lifecycle and replay relations hold.

Execution failures are recorded separately as EXECUTION_ERROR.

## F08 version semantics

The previous F08 cases remain DETECT_LIFECYCLE_DRIFT because both histories
start from the same eligible replay packet. The adverse history then emits a
residual and tangent packet whose internal version relation is incompatible.
This within-history violation is rejected before correction, commit,
checkpoint, or output.

By contrast, histories whose replay packets already declare incompatible
versions before execution are INVALID.

- PRE_COMPARISON_VERSION_MISMATCH -> INVALID
- WITHIN_HISTORY_VERSION_CONTRACT_VIOLATION -> DETECT_LIFECYCLE_DRIFT
- VERSION_METADATA_UNAVAILABLE -> NOT_SUPPORTED
- DECLARED_COMPATIBLE_LAG_WITH_INVARIANT_RESULT -> PASS_INVARIANT

## Non-converses

- Finite values do not imply lifecycle validity.
- Equal final outputs do not imply an eligible comparison.
- A missing host callback does not imply invariance.
- A version mismatch need not create a numerical delta.
- A detected anomaly does not establish universal detectability.
