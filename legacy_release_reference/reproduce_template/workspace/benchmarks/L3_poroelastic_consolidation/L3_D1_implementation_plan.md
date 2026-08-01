# L3-D1 implementation plan

Status: `FROZEN_NOT_IMPLEMENTED`.

Planned modules define immutable state packets, an independent Fourier oracle,
a conservative finite-volume/Thomas solver, transaction-safe and seeded unsafe
retry variants, frozen case dispatch, directed tests and a double-locked runner.
No L2 equation is copied; only its canonical serializer is reused.

Formal execution requires both `--execute-authorized` and
`L3_D1_EXECUTION_AUTHORIZED=YES`. One process executes one case and one run ID.
Unit and non-formal preflight must pass before formal runs. Frozen equations,
parameters, schedules and thresholds cannot be tuned from formal output.

Any failed prerequisite stops downstream cases. Negative-control detection is
evidence for the harness, not a usable physical implementation. Abaqus and the
production model are outside this benchmark.

Revision `L3-D1.0a` renames only JSON fields `C/c` to `storage_coefficient/diffusivity`; equations, values, cases and gates are unchanged.
