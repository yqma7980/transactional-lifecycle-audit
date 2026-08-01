# P4d retained PETSc C observation-layer contract

Status: `FROZEN_NOT_IMPLEMENTED`

## 1. Retained P4c evidence

P4c established a bounded API fact in the pinned DOLFINx image:

- pure petsc4py did not expose all structured line-search fields required by the ledger;
- the same PETSc build exposed those fields through documented C APIs;
- two C probe runs produced byte-identical structured monitor logs;
- no PETSc or DOLFINx core patch was required.

Immutable P4c anchors:

| Artifact | SHA-256 |
|---|---|
| P4c freeze | `ee16a00cd2f5d02846a236158a2f9d9d0b9cf8420069bee1bafd032f0bab026c` |
| P4c protocol | `a84c9c872074ff13c728a937d6b9a66f403b72f4e3f6157ad245e37274aa87c9` |
| P4c C source | `ae405741545e64815e08e9f6b3fdd11d00db8617205e3a2aef1f9e2c67484e49` |
| P4c C binary | `01722299521b4009906e583e2a4f5b0c055cc332b2b8829672c8cfb0ad002efb` |
| duplicate C monitor log | `930e6480f33d5e1984e03cc44ab6553543fa14f7204aeb559133cd39b58609a2` |

The P4c executable solved its own scalar SNES problem. It is evidence for the observer API pattern, not a reusable finite-element observer binary.

## 2. P4d observer-only module

A later implementation may create a new observer-only shared library with one public attachment entry point:

```text
P4dObserverAttach(existing_snes, output_sink, schema_version)
```

The exact ABI and petsc4py handle conversion must be frozen in a separate implementation preflight. This P4d static freeze does not assume that a Python SNES handle can already be passed safely to C.

The attachment module may call only documented observer/check interfaces, including:

- `SNESGetLineSearch`;
- `SNESLineSearchMonitorSet`;
- `SNESLineSearchGetVecs`;
- `SNESLineSearchGetLambda`;
- `SNESLineSearchGetReason`;
- `SNESLineSearchSetPostCheck` only as a read-only observation callback.

The post-check must leave all change flags false and may not alter `X`, `Y` or `W`. It may not set a lambda or reason, replace the line search, change solver options or invoke material evaluation.

## 3. Required C ledger fields

Each C event row must include:

```text
schema_version
observer_build_hash
solve_id
line_search_epoch
nonlinear_iteration
callback_kind
lambda_hex
line_search_reason
X_hex_values
F_hex_values
Y_hex_values
W_hex_values
vector_sizes
event_ordinal
```

All floating values are serialized by exact hexadecimal representation. The single-rank restriction is part of the scientific scope; no distributed ordering claim is made.

## 4. Cross-layer join

The Python residual/Jacobian ledger records:

```text
solve_id
assembly_call_id
primary_vec_hex_values
primary_vec_hash
committed_state_hash
material_candidate_hash
residual_version
tangent_version
```

A C event and Python event can be joined only when the solve identity and exact vector values agree. Matching event ordinal without matching vector content is diagnostic only. An unmatched event gives `INVALID_LEDGER_CORRELATION`; it may not be assigned to a material candidate by nearest time or callback count.

## 5. Native nonacceptance rule

P4d calls a line-search candidate nonaccepting only when the C layer exposes:

1. the candidate work vector;
2. the selected line-search result;
3. the selected lambda and reason; and
4. vector-based correlation to the material candidate.

A residual call absent from the final solution is not, by itself, sufficient evidence. PETSc text monitor output is retained as diagnostic corroboration only.

## 6. Mandatory attachment preflight

Before `P4D-REF-01`:

1. create no mesh or finite-element object;
2. instantiate a DOLFINx-owned `NonlinearProblem`-compatible zero-case SNES path;
3. attach the observer-only C module to that exact SNES object;
4. reproduce the P4c scalar line-search vector/lambda/reason sequence;
5. prove that all observed vectors and solver results are unchanged with and without the observer;
6. repeat in two fresh containers.

If an exact DOLFINx-owned zero-case path is technically impossible without a mesh, a minimal algebraic PETSc object obtained from the same DOLFINx process may be used only to validate the attachment ABI. The first FE run then remains blocked until attachment to the FE-owned SNES itself is proven.

## 7. Evidence boundary

The C observer provides host-event observability, not lifecycle safety. Material restoration, commit, output provenance and checkpoint completeness remain application obligations and require independent ledgers and tests.
