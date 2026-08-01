# P4d state ownership and event contract

Status: `FROZEN_NOT_IMPLEMENTED`

## 1. Layer partition

P4d uses four explicit layers. A claim may not be promoted from one layer to another.

| Layer | Frozen responsibility | Not attributed to this layer |
|---|---|---|
| DOLFINx | mesh, function space, boundary conditions, finite-element residual/Jacobian assembly | constitutive commit, rollback, accepted output |
| PETSc SNES | nonlinear iterations, residual/Jacobian requests, line search, terminal converged reason | outer load-increment acceptance, material commit |
| P4d transaction driver | outer increment begin/accept/retry, committed integration-point state, checkpoint and accepted output | PETSc-native line-search verdict |
| PETSc C observer | read-only observation of line-search vectors, lambda and reason through documented C APIs | changing vectors, selecting a trial, committing state |

The driver may react to a native PETSc terminal reason, but a driver retry remains author-owned. The observer may serialize PETSc state, but may not manufacture an acceptance label after comparing the final solution.

## 2. Authoritative and trial state

At accepted increment `n`,

```text
S_n = (x_n, C_n, P_n, Q_n, V_n).
```

- `x_n`: accepted DOLFINx primary displacement vector.
- `C_n`: committed integration-point `gamma_p[32,3,2]`, `alpha[32,3]`, accepted load factor and accepted version.
- `P_n`: declared user-persistent state outside `C_n`, including only explicitly listed caches or negative-control fields.
- `Q_n`: accepted output/checkpoint provenance and diagnostic ledgers.
- `V_n`: mesh, material, serializer, residual, tangent, state and schema versions.

For every PETSc residual request at candidate `x_chi`, the constitutive candidate is reconstructed as

```text
T_chi = G(x_chi; C_n, pi_P(P_n), V_chi).
```

The same `T_chi` instance supplies stress to the residual and `C_alg` to the matching Jacobian packet. Rejected candidates are discarded. `C_n` is immutable until the driver observes a positive terminal SNES reason and all accepted-increment gates pass.

## 3. Ownership inventory

| Field | Class | Owner | Writable events | Rollback/commit rule |
|---|---|---|---|---|
| displacement PETSc Vec | primary | PETSc during SNES; driver between increments | PETSc trial and selected line-search updates | accepted copy only after positive SNES reason |
| `gamma_p,n` | committed physical | driver constitutive store | `AcceptIncrement` only | unchanged on residual, Jacobian, line-search reject or failed solve |
| `alpha_n` | committed physical | driver constitutive store | `AcceptIncrement` only | same as `gamma_p,n` |
| trial stress and candidate history | attempt-local | residual/Jacobian evaluator | `TrialEvaluate` | discard unless its candidate ID is selected and increment accepted |
| hidden trial cache | persistent negative control | unsafe variant | rejected `TrialEvaluate` | safe variant has no such physical cache; unsafe variant intentionally omits restore |
| load factor and accepted index | algorithmic | driver | `BeginAttempt`, `AcceptIncrement`, retry | failed target is discarded; accepted index advances only on accept |
| mesh/material metadata | immutable persistent | driver | initialization only | canonical hash must never change |
| residual/tangent versions | operator contract | driver and evaluator | packet construction | relation checked before correction |
| PETSc line-search ledger | diagnostic | C observer | native line-search callbacks | never enters physics or accepted scientific output |
| accepted-output rows | semantic output | output subsystem | `OutputAcceptedState` after commit | source candidate and committed version mandatory |
| checkpoint payload | checkpoint | driver | `CheckpointWrite` after commit | fresh process must reconstruct identical accepted state |

Any new field that influences stress, residual, tangent, a future commit candidate or accepted scientific output must be added to this table before implementation. It cannot be relabelled diagnostic after a failed run.

## 4. Canonical event mapping

| Canonical event | Native/owned evidence in P4d | Required record | Forbidden inference |
|---|---|---|---|
| `BeginIncrement` | driver-owned | accepted source version, target load, attempt ID | calling this PETSc-native |
| `BeginAttempt` | driver-owned | target, solver options hash, committed hash | hidden option changes |
| `TrialEvaluate` | PETSc residual request plus DOLFINx assembly callback | primary Vec fingerprint, committed hash, candidate history hash | re-evaluation when logging |
| `FormResidual` | PETSc/DOLFINx | residual norm, packet version, candidate ID | residual with no state provenance |
| `FormTangent` | PETSc/DOLFINx | matrix checksum, packet version, candidate ID | stale tangent accepted silently |
| `NonacceptingTrial` | PETSc C line-search observation | old/correction/work vectors, lambda, reason, cross-layer candidate ID | final-discrepancy labelling |
| `RollbackOrRetry` | driver reacting to negative SNES reason | before/after `x,C,P,Q,V` projections | calling author restore a PETSc TS rollback |
| `AcceptCommit` | driver after positive SNES reason and gates | selected candidate ID, old/new committed hashes | commit inside a residual callback |
| `AcceptedOutput` | driver output after commit | source candidate, committed version, semantic projection | copying a rejected trial row |
| `CheckpointWrite` | driver after commit | schema, payload and source-state hashes | arbitrary same-process memory dump |
| `RestartRead` | fresh driver process | payload hash, reconstructed state hash, environment hash | reusing old process memory |

## 5. Declared replay packet

The equal-declared-state replay boundary for retry and negative-control cases is the first residual/Jacobian packet at accepted target `lambda=0.10` after source state `lambda=0.08`.

```text
D_star = (
  primary_vector_hash,
  committed_state_hash,
  load_factor=0.10,
  mesh_hash,
  material_hash,
  residual_version,
  tangent_version_relation,
  serializer_version
).
```

The direct and perturbed histories must have identical `D_star`. Post-history persistent-state restoration is a finding, not an eligibility prerequisite. An external perturbation applied after rollback and outside the declared history is an ineligible sensitivity experiment rather than a lifecycle comparison.

## 6. Version contract

Three tangent relations are frozen:

1. `EXACT_CURRENT`: residual and tangent use the same current trial candidate and state version.
2. `DECLARED_ACCEPTED_STATE_LAG`: current residual is paired with a tangent derived from the declared accepted state; the relation is explicit and may change iteration count but must converge to compatible accepted fields.
3. `UNDECLARED_MISMATCH`: a finite tangent packet carries a state version outside the declared relation. The guard must reject it before correction, commit or output.

Exact numeric equality is not required between direct and declared-lagged iteration histories. Accepted fields are compared with the predeclared `1e-10` scaled relation. The mismatch case uses identical finite numbers but incompatible metadata so that protective rejection cannot be attributed to NaN or matrix singularity.

## 7. PETSc C observation-layer correlation

P4d retains the P4c official-C observation approach. A future observer-only shared library must attach to the DOLFINx-owned `SNES` without patching DOLFINx or PETSc. It records:

- solve and line-search epoch;
- nonlinear iteration;
- `X, F, Y, W` vector values in canonical hexadecimal form;
- selected lambda;
- line-search reason;
- callback order.

The Python assembly ledger independently records the primary-vector fingerprint and material-candidate hash. In the frozen single-rank setting, the ledgers are joined only when the canonical PETSc vector values and solve/iteration identifiers agree. Event order alone is insufficient.

Before any physical formal run, a zero-case attachment preflight must prove that this observer can attach to the exact `dolfinx.fem.petsc.NonlinearProblem.solver` object and reproduce P4c line-search observations. Failure gives `BLOCKED_C_BRIDGE_ATTACH`; it may not be bypassed by parsing text monitor output.

## 8. Accepted output

Accepted output is written only after `AcceptCommit` and contains:

- accepted load factor and version;
- primary vector hash and selected candidate ID;
- committed `gamma_p` and `alpha` hashes;
- reaction and residual summaries;
- material, mesh and serializer versions;
- semantic provenance projection.

Run ID, wall-clock timestamp and local path are diagnostic fields excluded from semantic parity. Trial diagnostics remain in a separate ledger and cannot be promoted to accepted output.

## 9. Checkpoint and restart

Checkpoint/restart is author-owned and is never described as a PETSc trajectory result. The payload is written only at accepted `lambda=0.12` and is read by a fresh process. It includes the deterministic mesh recipe and hash, boundary ordering, primary vector, integration-point committed arrays, accepted index/load, all version identifiers and a payload manifest.

No pickle or same-process object reference is permitted. The restarted history must match the continuous history at every later common accepted load within the frozen field tolerances and must have exact discrete/version hashes.

## 10. Claim boundary

Passing this contract would support one serial DOLFINx/PETSc host-integrated lifecycle example. It would not prove that PETSc owns material transactions, that DOLFINx provides native checkpoint semantics, or that the method is complete under MPI, threads, contact, damage, coupled flow-mechanics, commercial solvers or production UELs.
