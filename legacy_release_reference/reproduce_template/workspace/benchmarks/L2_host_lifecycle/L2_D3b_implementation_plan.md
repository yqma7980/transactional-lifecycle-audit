# L2-D3.0b corrected implementation plan

## Identity

- Frozen design: L2-D3.0
- Implementation revision: L2-D3.0b
- Host version: L2-HOST-D3.0b
- Supported formal case: L2-TG-02 only
- Target state: CORRECTED_IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED

The correction is confined to TG-02 comparison and classification. It does not
alter the mathematical paths or D1 constitutive implementation.

## Reuse and comparison

Reuse the original D3 TangentPath records, exact and declared-lagged path
builders, and the D1 CommittedState and canonical hashing. Add no material
evaluation and do not alter residual or tangent packets.

The corrected audit records left and right committed-transition validity,
cross-path committed-hash equality, accepted-field deltas and isclose flags,
and accepted-fingerprint equality. Each expected committed-after hash is
reconstructed from that path's accepted epsilon_p and kappa at version 1.

## Classification

PASS_DECLARED_LAGGED_TANGENT_PARITY requires:

1. u, sigma, epsilon_p, kappa and force satisfy abs_tol=rel_tol=1E-12;
2. exact and lagged evaluation counts are 3 and 4;
3. iteration counts differ;
4. both path-local committed transitions are valid;
5. superseded candidates are unreachable; and
6. all values are finite and bounded by 1E100.

Cross-path fingerprint equality is informational and not a pass gate. TG-01
retains exact fingerprint equality.

## Targeted tests and corrective replay

The new targeted test file verifies tolerance pass and fail boundaries,
evaluation counts, independent committed transitions, candidate
unreachability, unchanged TG-01 semantics, preserved run hashes, and import
side-effect safety. It may run only in one process and one thread with
PYTHONDONTWRITEBYTECODE=1.

The old run_1 may be loaded read-only and reclassified in memory. A passing
result is labeled only CORRECTIVE_REPLAY_EXPECTED_PASS and is not formal
benchmark evidence.

## Future runner and boundary

The new runner allows only L2-TG-02 and requires both --execute-authorized and
L2_D3B_EXECUTION_AUTHORIZED=YES before creating
results/L2_D3b_tangent_path. This task must not invoke it.

TG-02 remains OPEN until two separately authorized independent repetitions
pass. TG-03, remaining L2, L3-L6, Abaqus, production, performance,
conservation, and coupled physics remain OPEN.
