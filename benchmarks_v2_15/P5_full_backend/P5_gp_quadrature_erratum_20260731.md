# P5 integration-point backend erratum (2026-07-31)

## Preserved stopped execution

Execution tag `P5_formal_20260731_fullFE_v1a` completed all 14 null
calibration/confirmation processes and then stopped before producing a scaled
case result. The preserved `P5-SCALE-F01-DEV/run_1` process log has SHA-256
`a2c13f60517157478d36fc8076d6852e58055454678084ed4864b2e87f6bed90`.

The null envelope and confirmation passed. Their preserved SHA-256 values are:

- `null_envelope.json`:
  `b318e735a2514dcbc357349919d6bde5ece127d2ea05752dc29bafba411cebb6`
- `null_confirmation.json`:
  `075031e998fd9633a52a3ee9a90b8fa0468453b65dd1fc7b0f273f3d3be5dee9`

No scaled `case_result.json` was produced under this tag.

## Root cause

The frozen F01 binding intentionally mutates only
`trial_cache.gamma_p[0,0,0]`. This makes the three material packets in the
affected P1 triangle nonidentical. The inherited P4d demonstrator used a
representative-cell fast path that rejects nonidentical integration-point
stress or tangent packets. That fast path was valid for the earlier uniform
P4d states but was incomplete for the frozen P5 point-local fault binding.

## Bounded correction

Revision `CMAME-P5.2b-FE-GP-INTEGRATION` preserves the F01/F02 field bindings.
For identical integration-point packets it returns the first point exactly,
thereby retaining the original P4d arithmetic. For a nonidentical packet it
reduces stress and tangent with the frozen degree-2 triangle quadrature. The
three frozen weights are equal, so this is the exact cell average for the
constant P1 strain-displacement operator.

No equation, mesh, material parameter, fault binding, amplitude, threshold,
selector, process count, acceptance gate, image, or historical result was
changed.

## Verification

- Four new Python files pass AST parsing.
- Three directed quadrature tests pass.
- An in-memory F01 FE smoke at `eta=2^-48` completes all 10 accepted states,
  remains conventionally quiet, and retains the expected lifecycle violation.
- The protected source and implementation manifests remain unchanged.
- `__pycache__` count remains zero.

The replacement formal execution tag is
`P5_formal_20260731_fullFE_v1b`.
