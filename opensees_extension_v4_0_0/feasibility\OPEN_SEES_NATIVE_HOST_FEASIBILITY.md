# OpenSees native-host feasibility audit

## Decision

`CLASSIFICATION: READY`

`LIFECYCLE_TIER: TIER_A_NATIVE_MATERIAL_API`

OpenSees 3.8.0 exposes and executes a genuine native material lifecycle through
`setTrialStrain`, `commitState`, `revertToLastCommit`, and `revertToStart`.  The
feasibility harness calls these C++ methods directly on the unmodified upstream
`Concrete01` implementation.  It is not a Python rollback wrapper and it does
not establish a Tier-B solver-managed rejected-step trajectory.

## Frozen upstream identity

- Upstream project: OpenSees
- Tag: `v3.8.0`
- Git commit: `6e55293513192aa05c7e1205e66a5a1a1ed088c4`
- Material implementation: `SRC/material/uniaxial/Concrete01.cpp`
- Upstream implementation SHA-256: `C627F6C0BFAF2408FC321B46EBE63C5D3F4D53DE53C6BC4A14757695BE2DBD25`
- Upstream copyright SHA-256: `54ED2FE97DBC30C6B8C77E094E71F20C255C52A642CE66D279A8F1B6A3676036`

The corresponding OpenSeesPy 3.8.0.0 installation was inspected but is not
used as native-lifecycle evidence.  Its public Python interface does not expose
the four C++ material lifecycle methods as independent operations.

## Source-level lifecycle evidence

In the frozen upstream source:

- `Concrete01::setTrialStrain` begins at line 147 and resets trial variables
  from committed variables before evaluating the candidate;
- `Concrete01::commitState` begins at line 403 and transfers trial variables
  into committed variables;
- `Concrete01::revertToLastCommit` begins at line 421 and restores trial strain,
  stress, tangent, and history variables from committed values;
- `Concrete01::revertToStart` begins at line 436.

These operations provide a defensible native lifecycle for a small independent
external-subject study.

## Build and execution evidence

The smoke executable was built with Visual Studio 2017 from the unmodified
OpenSees implementation plus a minimal caller.  OpenSees' bundled Win64
LAPACK/BLAS libraries and the installed Intel oneAPI runtime were linked.  The
small `unused_api_link_stubs.cpp` file supplies parser/output entry points that
are required by otherwise unused object-file paths; it does not implement or
replace any trial, commit, or revert operation.

Smoke output:

```text
committed_stress=-28.125
trial_stress=-25
restored_stress=-28.125
native_revert_bitwise_equal=1
```

The rejected trial changed the material response, while native
`revertToLastCommit` restored the committed stress bitwise exactly.

## Artifact hashes

| Artifact | SHA-256 |
|---|---|
| `smoke_main.cpp` | `76E34B28ECEC9C1519FCAFEDEDC11974AC5A7DB41D2B1003B9399C6B06FEC7D5` |
| `unused_api_link_stubs.cpp` | `1BE37E8E4A663F4446709C6A859E9A6370285369E770711B4A9F90686405444D` |
| `CMakeLists.txt` | `5B3EF1CABC470C8AFD9BD7E62C4DB013DAAEF7B27F1B16213D927ACA0F848F30` |
| `opensees_tier_a_smoke.exe` | `B9D268C881AF6EFADF8C239CE8F20F7BBC1895455C592DF725BCC26DA4DEE654` |

## Permitted next step

A prespecified 6--10 case Tier-A study may be implemented around this native
material interface.  It must use controlled integration mutants, must not imply
that upstream OpenSees contains a defect, and must remain statistically separate
from the frozen 17-, 20-, 12-, and 180-run parent studies.  The case matrix,
thresholds, candidates, repeat count, and analysis rules must be hashed before
any confirmatory execution.

## Claim boundary

This audit establishes API and build feasibility only.  It does not establish
industrial validation, field-defect prevalence, solver-level rollback coverage,
automatic recovery, or fault containment.
