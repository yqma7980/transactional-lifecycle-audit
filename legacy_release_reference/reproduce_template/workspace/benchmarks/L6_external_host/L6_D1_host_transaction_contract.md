# L6-D1 external-host transaction contract

## Host ownership

SciPy owns trust-region proposal, rejection, acceptance and convergence. The adapter does not synthesize trial order, force retries or replace the host's acceptance rule.

## Adapter ownership

The adapter owns immutable committed history, call-local candidates, residual/Jacobian version metadata, event logging, final physical commit and accepted output.

## Event-resolution algorithm

1. Every residual callback appends an unresolved `TrialEvaluate/FormResidual` event.
2. Every accepted SciPy callback identifies the latest unresolved residual event with the same float-hex `x`.
3. Earlier unresolved residual events since the previous accepted callback become `HOST_NONACCEPTED`.
4. The matched event becomes `HOST_ACCEPTED_ITERATE`.
5. Initial `x0` is initialization, not a physical accept.
6. On successful host return, the returned final `x` must match the latest accepted callback.
7. Only then may the adapter commit version 1 and emit one accepted output.
8. On version mismatch or host failure, no physical commit or accepted output is permitted.

## Safe state rule

Every residual/Jacobian packet is reconstructed from the same immutable committed state. Trial candidates are unreachable from accepted output until successful host return.

## Unsafe negative control

The only unsafe mechanism is residual-call mutation `h_p <- x_trial` after the returned residual is formed. No other equation, tolerance, Jacobian, host option or output rule changes.

## Version rule

Residual and Jacobian packets must carry the same committed-state hash and trial-state version for the same float-hex `x`. The deliberately mismatched case changes metadata only; finite numerical values remain unchanged. Mismatch must raise `OperatorVersionMismatch` before returning the Jacobian to SciPy, before correction, physical commit or output.

## Output rule

Accepted output contains host result, final candidate and committed version 1. It is written only after `result.success`, final-version validation and physical commit. Rejected/nonaccepted event IDs and candidate hashes are forbidden in accepted output.
