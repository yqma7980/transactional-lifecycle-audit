# P4d.2 full implementation protocol

Status: `IMPLEMENTATION_IN_PROGRESS_NOT_FORMALLY_EXECUTED`

## Scope

P4d.2 implements every code path required by the frozen P4d.0 nine-case matrix. It does not execute those case IDs and therefore creates no `OBSERVED-P4D` evidence. The P4d.0 design, thresholds, load path, material constants and expected verdicts remain authoritative.

## Host architecture

The implementation has four separated owners:

1. DOLFINx owns the deterministic mesh, P1 primary field and UFL forms.
2. PETSc SNES owns nonlinear iteration and native backtracking line search.
3. The P4d transaction driver owns committed integration-point state, increment acceptance, retry, checkpoint and accepted output.
4. The unchanged P4d.1 PETSc C observer is rebuilt as a read-only shared library and attached to the DOLFINx-owned SNES only for the native line-search path.

For P1 triangles, the primary gradient is constant within each cell. P4d nevertheless stores all three degree-2 quadrature records per cell in the frozen `(32,3,2)` and `(32,3)` arrays. Cellwise DG0 stress and tangent coefficients are exact assembly representatives of those three identical P1-strain packets; no integration-point history is collapsed in the committed store.

## Transaction rule

Every residual or Jacobian request first fingerprints the PETSc primary vector and immutable committed source. A call-local material packet is reconstructed from that source. The packet cache is keyed by primary vector, committed source, target load and declared tangent relation. A matching Jacobian reuses the same packet; no residual or Jacobian callback commits history.

`AcceptCommit` is reachable only after a positive SNES reason and the frozen finite, equilibrium, history and version gates. `AcceptedOutput` and `CheckpointWrite` occur only after `AcceptCommit`.

## Implemented histories

- `H_REFERENCE`: analytical elastic manufactured solution on N=4/8/16.
- `H_MATERIAL_PACKET`: independent Fraction elastic/plastic packets.
- `H_DIRECT`: exact-current accepted load path.
- `H_NATIVE_LINESEARCH`: the same path with the frozen accepted-state-lag relation on reload 0.08 to 0.16 and the C observer attached.
- `H_DRIVER_RETRY`: frozen max-iteration-one failed attempt from 0.08 to 0.20, exact restoration, then replay at 0.10.
- `H_RESTART`: reads a direct-history checkpoint at 0.12 in a fresh formal process and continues.
- `H_CACHE_NEGATIVE`: exactly one rollback-external hidden-cache mutation at scale 1e-6.
- `H_OUTPUT_NEGATIVE`: exactly one failed-attempt candidate is made reachable from the accepted-output channel.
- `H_VERSION_GUARD`: numerically identical operator packets with incompatible tangent metadata are rejected before correction.

## Formal execution lock

The formal runner accepts one frozen case and one run ID. Before creating any output path it requires both `--execute-authorized` and `P4D2_EXECUTION_AUTHORIZED=YES`. This implementation turn does not satisfy either lock.

## Evidence boundary

A successful implementation QA means only `IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED`. It does not establish native line-search coverage for the physical path, the forced-retry trigger, restart parity, negative-control detection, or any manuscript claim. Those findings require the separately authorized two-fresh-process formal matrix.
