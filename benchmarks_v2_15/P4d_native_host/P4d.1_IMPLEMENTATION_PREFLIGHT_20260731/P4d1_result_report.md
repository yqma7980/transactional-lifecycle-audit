# P4d.1 implementation preflight result

## Terminal status

`PASS_P4D1_PREFLIGHT_READY_FOR_FULL_IMPLEMENTATION`

This is a preflight result only. It is not `OBSERVED-P4D` evidence and does not
authorize or report the frozen nine-case matrix.

## Gate results

| Gate | Result |
|---|---|
| G0_PROTECTED_EVIDENCE | PASS |
| G1_HOST_IDENTITY | PASS |
| G2_C_BRIDGE_ATTACH | PASS |
| G3_FE_TOPOLOGY_AND_STATE | PASS |
| G4_REFERENCE_ORACLE | PASS |
| SAFE_INCREMENT_SMOKE | PASS |
| DIRECTED_TESTS | PASS |

## Native observer

The shared library attaches to `NonlinearProblem.solver` through the verified
same-process petsc4py SNES handle. Observer-disabled and observer-enabled runs
have exact equality in solution, SNES reason, iteration count and residual
sequence. Both fresh observer processes expose a native full-step candidate
that differs from the selected work vector. All post-check change flags remain
false.

Observer C source SHA-256: `e21ca0077f4f6bc8e850d25886a81bf33e19d5e5f40fc709f3743e10117b9a75`.
Observer binary SHA-256: `b9f9cfeb0750bb77e87d063363d1e13407c3442237db8f95364d0362f002a291`.

## Oracle and topology

- Maximum Fraction packet error: `0x1.0000000000000p-50`.
- Maximum directional tangent relative error: `0x1.3360333333335p-33`.
- The manufactured reference smoke used only `N=4`; relative L2/H1 diagnostics
  are `0x1.43e49f9ed7141p-3` and
  `0x1.8289f43f4b3c4p-2`. No convergence
  sequence or formal error-order claim was made.
- Topology: 32 cells, 25
  nodes and 96 integration points.
- Trial evaluation left committed arrays unchanged.

## Safe increment smoke

Only `H_DIRECT`, load `0.00 -> 0.04`, was run. SNES converged with reason
2 in 1 iteration. The relative
free-DOF residual and reaction imbalance are
`0x1.73c6a7f064077p-52` and
`0x1.1d887995c78cep-57`. Exactly one candidate was committed,
and accepted output was generated afterward from that candidate id. The run did
not continue to `0.08`.

## Preserved implementation evidence

The first pkg-config lookup failure and first topology JSON serialization
failure are retained and explained in the pre-execution erratum. Neither
changed a scientific input or threshold.

## Boundary

No Abaqus, COMSOL, OpenSees, production UEL, P3, formal P4d case, manuscript,
Claim Matrix, Figure, GitHub, Zenodo or DOI action occurred.
