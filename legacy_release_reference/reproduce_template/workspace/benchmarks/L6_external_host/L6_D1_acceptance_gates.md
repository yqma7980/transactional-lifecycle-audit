# L6-D1 acceptance gates

## Global formal gates

- Exactly five case IDs and two independent single-process, single-thread runs per case.
- Installed host and frozen source hashes match L6-D1.0.
- All recorded numerical values are finite and have absolute value below `1E100`.
- Duplicate runs match exactly after replacing only `run_id` and process-specific timestamps, which are excluded from deterministic ledgers.
- No case reads another formal run result.
- No accepted output is written before successful host return and physical commit.
- No Abaqus, COMSOL or production code is invoked.

## RT-01 safe retry

- SciPy returns success.
- At least one genuine `HOST_NONACCEPTED` residual event occurs.
- Final `x` differs from `sqrt(2/3)` by at most `1E-6`.
- Committed-state hash is unchanged during all host callbacks.
- Residual/Jacobian versions are compatible.
- Exactly one final physical commit occurs; rejected candidates remain unreachable.
- Classification: `PASS_SAFE_EXTERNAL_HOST_RETRY`.

## OP-01 accepted-output provenance

- SciPy returns success and at least one nonaccepted trial occurs.
- Accepted-output count is exactly one.
- Output event occurs after `HostReturn` and `Commit`.
- Output `x` equals the host-returned final `x` exactly.
- No nonaccepted event or candidate hash appears in output.
- Classification: `PASS_EXTERNAL_HOST_OUTPUT_PROVENANCE`.

## CO-01 callback-order parity

- Analytic-Jacobian and frozen 2-point runs both return success from fresh adapters.
- Their committed-before hashes and physical equations are identical.
- 2-point mode performs more residual evaluations than analytic mode.
- Final `x` absolute difference is at most `1E-6`.
- Final cost absolute difference is at most `1E-8`.
- Each path independently satisfies output provenance and committed-state transition validity.
- Classification: `PASS_EXTERNAL_HOST_CALLBACK_ORDER_PARITY`.

## RT-02 unsafe finite-drift negative control

- The internal safe control satisfies RT-01.
- Unsafe SciPy execution returns success and remains finite.
- At least one unsafe persistent mutation is attributable to a nonaccepted host residual event.
- Absolute final-`x` drift from the safe control is at least `1E-8`.
- Committed physical state remains unchanged until final host return; rollback-external persistent state changes.
- Classification: `DETECT_EXTERNAL_HOST_FINITE_DRIFT`.
- This is a detected negative control, never a usable physical implementation.

## TV-01 version mismatch

- Residual and Jacobian numerical values are finite.
- Declared residual/Jacobian state versions differ.
- `OperatorVersionMismatch` is raised before the Jacobian is returned to SciPy.
- No accepted callback, correction, physical commit or accepted output occurs.
- Committed and persistent hashes remain unchanged.
- Classification: `REJECT_VERSION_MISMATCH_BEFORE_HOST_CORRECTION`.
