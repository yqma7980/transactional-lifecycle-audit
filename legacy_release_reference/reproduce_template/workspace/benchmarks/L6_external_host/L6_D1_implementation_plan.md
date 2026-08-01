# L6-D1 implementation plan

**Status:** FROZEN_NOT_IMPLEMENTED

## Files to add after static QA

- `src/l6_state.py`: immutable state, packets and canonical fingerprints.
- `src/l6_scipy_adapter.py`: SciPy callbacks, event resolver, commit and output gates.
- `src/l6_cases.py`: five frozen case classifiers.
- `oracle/l6_stationary_oracle.py`: Decimal-based independent stationary oracle.
- `tests/test_l6_d1.py`: directed unit and host capability tests.
- `run_l6_d1.py`: one-case/one-run process entry with dual authorization.
- implementation manifest and preflight QA.

## Preflight sequence

1. Verify source/freeze hashes and installed SciPy host.
2. Parse and import implementation without side effects.
3. Run unit tests in one process and one thread.
4. Run capability-only safe, callback-order, unsafe and mismatch directed tests without creating formal result directories.
5. Verify all output schemas, unauthorized-case rejection and no accepted output before commit.
6. Stop on any frozen-gate failure.

## Formal sequence

Run cases in frozen order, each in two independent processes. Each run writes event ledger, host comparison, accepted output, case result and manifest in a unique directory. The first failed prerequisite stops the remaining matrix. Raw results are immutable before any evidence synchronization.

## Forbidden changes

Do not change the model, unsafe seed, host options, tolerances, source-hash requirements or case order after preflight. A scientific change requires a dated new design version; an implementation-only correction requires a dated erratum before any formal execution.
