# P4d.2 full implementation result

Final status: `IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED`

## Implemented scope

The P4d.2 code now contains all nine frozen P4d.0 case paths: manufactured
reference, independent Fraction constitutive packets, direct lifecycle,
native PETSc line search, forced driver retry, checkpoint/restart, hidden-cache
negative control, rejected-output negative control and pre-correction operator
version rejection.  The formal runner requires both authorization locks before
it creates a result directory and executes only one case/run per process.

## Nonformal verification

- Fixed-container contract tests: 10/10 pass.
- Python AST checks: 25/25 pass.
- Two fresh-process environment records agree after `run_id` normalization.
- Two fresh-process `P4D2-INTEGRATION-01` records are byte-exact.
- The bounded direct smoke accepted 4 increments through load 0.12, exercised
  plasticity, reached maximum alpha 0.07010539424648907,
  and passed the frozen finite/equilibrium/yield gates.
- The unchanged observer C source was rebuilt against PETSc 3.24.0 and placed
  at the formal runner's frozen runtime location.

## Evidence boundary

No formal P4d case ID was executed and no formal result directory exists.
The direct integration smoke is implementation preflight only.  Native
line-search coverage, forced-retry support, restart parity and both negative
controls remain OPEN until the separately authorized 9-case, two-fresh-process
formal matrix is executed.  This status is not `OBSERVED-P4D` and does not
authorize manuscript, Claim Matrix, figure, GitHub, Zenodo or DOI changes.

## Boundary note

No Abaqus solver worker was running and no production write command was issued.
The local `D:` and `F:` production `.git` views were not usable as Git
repositories in this session, so the historical Git-status fingerprint is
reported as not independently verifiable rather than asserted unchanged.
