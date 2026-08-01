# L2-D0 acceptance and stop gates

Status: **DRAFT / MUST BE FROZEN BEFORE IMPLEMENTATION**

## Gate 0: design completeness

All items below must be resolved before L2-D1:

- named host, exact release and execution mode;
- minimal independent element source and license boundary;
- analytical material/element oracle;
- force/load packets and common accepted checkpoints;
- forced-retry mechanism demonstrated in a dry-run design;
- exact versus engineering-parity metrics;
- same-track repeatability envelope;
- tolerance values and rationale;
- required repetition count;
- thread/scheduling support decision;
- immutable case matrix and expected classifications.

Failure of Gate 0 blocks implementation.

## Gate 1: static and build integrity

- No production UEL source is copied, included or linked.
- Every persistent variable is classified as immutable, host-managed,
  transaction-managed, diagnostic-only or deliberate negative control.
- Residual and tangent carry explicit state-version identifiers.
- Diagnostic and output data cannot enter safe-variant physics.
- Source and configuration hashes are recorded.
- Compilation and host input validation complete without warning escalation.

## Gate 2: analytical reference

- Elastic and plastic accepted states agree with an independent oracle.
- Residual and tangent signs and units agree with the frozen bar equations.
- The accepted material history agrees with the oracle.
- Tolerances are those frozen at Gate 0 and are not changed after seeing formal
  results.

## Gate 3: forced retry and rollback

For safe variants:

- a candidate is formed before the forced rejection;
- rejection does not advance committed state;
- retry begins from the same accepted-state hash;
- the common accepted checkpoint satisfies the frozen parity envelope;
- rejected candidates are unreachable after rollback.

For the unsafe trial-cache control:

- the seeded finite history drift is detected;
- the negative control must not be reinterpreted as a host defect.

## Gate 4: callback and tangent-path discrimination

- Safe extra-callback insertion does not alter replay at equal declared state.
- Unsafe callback-history mutation is detected.
- Exact versus explicitly lagged tangent runs retain the same residual
  definition and boundary loading.
- Accepted-field parity is assessed independently from iteration-count parity.
- A seeded residual-tangent version mismatch is rejected before lifecycle or
  physical interpretation.

## Gate 5: output and checkpoint provenance

- Trial output is not classified as accepted physical output.
- Every accepted output row identifies its accepted state version.
- Checkpoint restore reproduces the frozen authoritative state fingerprint.
- The checkpoint gate is not described as restart parity.
- Unsafe output feedback is detected by the negative-control case.

## Gate 6: reproducibility

- Every formal case is run at least twice under the same environment.
- Deterministic artifacts match under the frozen reproducibility rule.
- Any allowed floating-point envelope is reported separately from exact
  lifecycle equality.
- Thread/scheduling results are conditional on formal host support.

## Organic hard stops

Stop the active L2 case and do not launch subsequent cases if any safe variant
shows:

- non-finite primary, history, residual or tangent values;
- committed-state advancement on rejection;
- an output source that is not accepted state;
- an undeclared residual-tangent state-version mismatch;
- inability to prove that the forced retry occurred after candidate formation;
- analytical-reference failure;
- parity failure beyond the frozen envelope;
- source/configuration drift from the frozen manifest.

## Interpretation stops
