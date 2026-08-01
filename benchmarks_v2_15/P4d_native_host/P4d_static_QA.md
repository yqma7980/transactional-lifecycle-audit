# P4d static freeze QA

QA status: `PASS_STATIC_FREEZE`  
Scientific status: `FROZEN_NOT_IMPLEMENTED`

## Scope

This QA verifies a static design package. It is not a DOLFINx finite-element result, PETSc lifecycle result, constitutive validation result or manuscript claim.

## Completed checks

| Check | Result |
|---|---|
| v2.13 baseline | 931/931 files present; zero size/hash mismatches; aggregate `d5c8dbae6275171a7bb314cb6582457ca3a6145c0ba773f1f83eff34fe65d919` |
| P2 manifest | exact protected hash match |
| P3 execution freeze and manifest | exact protected hash match |
| P4 manifest | exact protected hash match |
| P4c manifest | exact protected hash match |
| P4c evidence boundary | retained as conditional API readiness; not promoted to FE evidence |
| JSON syntax | execution freeze, oracle contract and state-I/O schema parse successfully |
| Case matrix | 9 rows, 9 unique case IDs, two future fresh-process repetitions per case |
| Fault mapping | 9 rows and one mapping per case |
| Official-source register | 14 records, official DOLFINx/Basix/PETSc sources only |
| Oracle arithmetic | elastic packet and plastic `Delta_l=1/12`, returned stress `7/6`, tangent diagonal `5/3,35/6` are internally consistent |
| Ownership partition | DOLFINx, PETSc, driver and C observer responsibilities are separated |
| Native-event rule | line-search nonacceptance requires structured C vector/lambda/reason evidence |
| Retry semantics | explicitly author-driver owned; not labelled PETSc TS rollback |
| Output/checkpoint | accepted-only output and fresh-process author checkpoint schemas frozen |
| Multi-axis verdict | scientific verdict and negative-control case-contract outcome are separate |
| Forbidden artifacts | no implementation source, test, runner, result, execution, checkpoint, binary or figure artifact is part of the package |
| Runtime | no P4d case, unit test, FE mesh, compilation, Abaqus, COMSOL, OpenSees or production solve was run |
| Solver workers | no active `standard`, `pre`, `SMASimUtility`, `ABQcaeK`, COMSOL, OpenSees or MPI worker was found at final QA |
| Production project | no write command was issued; its existing empty `.git` directory still makes `git status` unavailable (exit 128) |

## Important design findings

1. The anti-plane plasticity problem has real path-dependent integration-point state while remaining small enough for exact material packets.
2. PETSc-native line search and author-owned material/increment transactions are deliberately not conflated.
3. The P4c C source and executable prove the API pattern only. P4d still requires a separate attachment preflight on the DOLFINx-owned SNES.
4. The frozen failed-attempt trigger and native line-search trigger are scientific prerequisites. If either does not occur, the protocol stops rather than tuning the history.
5. Negative controls are interpreted through the v2.14 multi-axis taxonomy. Their expected lifecycle failures do not become claims that unsafe implementations passed.

## Open before implementation

- observer-only shared-library ABI and safe extraction of the existing SNES handle;
- exact DOLFINx quadrature-state storage strategy;
- static dependency inspection for all operator-relevant persistent fields;
- runner authorization lock and output directory contract;
- independent oracle source and unit-test layout.

These are implementation tasks, not reasons to alter this scientific freeze after observing results.
