# P5 mechanics-gate recording erratum

Status: `IMPLEMENTED_NOT_FORMALLY_EXECUTED`

## Trigger

The preserved `P5_formal_20260731_fullFE_v1c` execution reached
`P5-SCALE-F05-DEV/run_13` at the frozen strength `eta=2^-12`.  The nonlinear
solve returned a positive SNES reason and finite values, but the frozen yield
consistency mechanics gate failed.  The original history driver then called
`commit()`, whose contract correctly rejected the candidate and raised an
exception before a structured strength-sweep observation could be written.

## Correction boundary

The v4 execution layer does not alter the model, mesh, load path, mutation
site, strength grid, null thresholds, mechanics gates, selector, or any prior
result.  It makes two recording corrections:

1. a converged candidate that fails a mechanics gate is not committed and is
   returned with `FAILED_NORMAL_MECHANICS_GATE`;
2. metrics with unequal array shapes after that early stop are marked
   `comparison unavailable`, rather than padded or assigned a fabricated
   distance.  Residual and tangent replay metrics remain required and numeric.

Such a strength is `conventional_quiet=false` and is therefore ineligible for
selection.  The frozen requirement to execute all 15 strengths remains in
force, and lower eligible adjacent strengths are evaluated by the unchanged
selector.

## Evidence status

This file documents an implementation-contract correction only.  It is not a
formal P5 result.  Formal evidence requires a new execution tag and a complete
fresh-process matrix.
