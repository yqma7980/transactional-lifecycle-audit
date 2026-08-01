# L5-D0 independent-validation contract

Status: FROZEN_NOT_IMPLEMENTED

## Meaning of independent

L5 is an independently written implementation of the same frozen L4 physical problem. It may share only the published control equations, physical parameters, case times and comparison tolerances. It must not import or call the L4 solver, state classes, lifecycle variants, canonical serializer, update routines, oracle routines, output projection or runner.

The L5 numerical implementation is frozen as a separate MUSCL finite-volume reconstruction with a global-wave-speed Rusanov flux and SSPRK2 time integration. The L5 reference is separately coded from closed physical definitions using bisection plus fixed Gauss-Legendre quadrature, rather than L4 adaptive Simpson integration. L5 state fingerprints use a binary length-tagged IEEE-754 serializer and cannot call the L2/L4 canonical JSON serializer.

The cross-implementation case may read immutable L4 formal CSV/JSON evidence as data. It must verify the L4 aggregate hash before use and may not import L4 Python modules.

## Independence matrix

| Component | L4 | Frozen L5 | Sharing allowed |
|---|---|---|---|
| State packets | L4 dataclasses | new L5 immutable records | no |
| Fingerprint | L2 canonical JSON reuse | independent binary tagged serializer | no |
| Flux update | first-order upwind Euler | MUSCL/Rusanov SSPRK2 | no |
| Entropy oracle | bisection + adaptive Simpson | bisection + fixed Gauss-Legendre | no |
| Pressure/output | L4 reconstruction/projection | independently written L5 reconstruction/projection | no |
| Lifecycle controls | L4 variants | independently written L5 safe/unsafe host | no |
| Runner/schema writer | L4 runner | independent L5 runner | no |
| Physics/parameters | frozen equations | same equations | yes |
| L4 formal fields | produced by L4 | read only in XP-01 | data only |

Source/AST checks must prove no L4 implementation import. Any required code reuse beyond the allowed row makes L5 NOT_SUPPORTED.
