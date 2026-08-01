# P4d minimal two-dimensional finite-element host specification

Protocol ID: `P4d_DOLFINx_PETSc_MINIMAL_FE_HOST`  
Design version: `P4d.0`  
Status: `FROZEN_NOT_IMPLEMENTED`

## 1. Bounded research question

P4d asks whether a small but genuinely path-dependent finite-element problem can expose, in one auditable host stack, all of the following:

1. DOLFINx finite-element residual and Jacobian assembly;
2. PETSc-native nonlinear and line-search events;
3. author-owned integration-point trial, commit and rollback state;
4. author-owned load-increment acceptance, retry and fresh-process restart;
5. accepted-output provenance; and
6. pre-correction rejection of an undeclared residual/tangent version pair.

This freeze does not claim that DOLFINx or PETSc natively owns constitutive commit, increment cutback, checkpoint payloads or accepted scientific output. It defines an application-level transaction around documented host events and retains the official PETSc C observation layer established by P4c.

## 2. Mechanical model

The domain is the unit square

```text
Omega = [0,1] x [0,1].
```

The primary unknown is an anti-plane displacement `w(x,y)`. Its engineering shear strain and stress are

```text
gamma = grad(w) = [dw/dx, dw/dy]^T,
tau   = [tau_xz, tau_yz]^T.
```

For every test function `v` that satisfies the homogeneous essential boundary conditions, the equilibrium residual is

```text
R(w; C_n, lambda)[v]
  = integral_Omega tau(w; C_n) dot grad(v) dx
    - integral_Omega b(lambda) v dx
    - integral_Gamma_t t_bar(lambda) v ds.
```

The lifecycle problem uses `b=0` and traction-free vertical sides. The bottom boundary has `w=0`. The top boundary has

```text
w(x,1) = lambda * (1 + 0.2 sin(pi x)).
```

All quantities are nondimensional. The nonuniform top displacement creates a spatially varying integration-point history while retaining a compact mesh.

## 3. Path-dependent constitutive update

Each integration point owns committed state

```text
C_n^gp = (gamma_p,n, alpha_n),
gamma_p,n in R^2, alpha_n >= 0.
```

The frozen material constants are

```text
G = 10, tau_y0 = 1, H = 2.
```

For one trial strain `gamma`, define

```text
e_tr   = gamma - gamma_p,n,
tau_tr = G e_tr,
q_tr   = ||tau_tr||,
y_n    = tau_y0 + H alpha_n,
f_tr   = q_tr - y_n.
```

If `f_tr <= 0`, the response is elastic:

```text
tau = tau_tr,
gamma_p,cand = gamma_p,n,
alpha_cand = alpha_n,
C_alg = G I.
```

If `f_tr > 0`, use the radial return

```text
n       = tau_tr / q_tr,
Delta_l = f_tr / (G + H),
tau     = tau_tr - G Delta_l n,
gamma_p,cand = gamma_p,n + Delta_l n,
alpha_cand   = alpha_n + Delta_l.
```

With `beta=(q_tr-G Delta_l)/q_tr`, the declared consistent algorithmic tangent is

```text
C_alg = G [ beta (I - n tensor n)
            + H/(G+H) (n tensor n) ].
```

The `q_tr=0` branch is elastic and never divides by `q_tr`. Trial candidates are call-local. Only the candidate associated with a converged outer load increment can be committed.

## 4. Discretization

The lifecycle mesh is frozen as:

- unit-square structured recipe with `4 x 4` squares;
- every square split along the same declared diagonal into two triangles;
- 32 triangular cells and 25 scalar P1 nodes;
- continuous first-order Lagrange approximation for `w`;
- degree-2 triangle quadrature with three points per cell;
- 96 ordered integration-point records;
- one MPI rank and one thread.

The implementation preflight must record coordinates, connectivity, boundary-DOF ordering, quadrature points, quadrature weights and their canonical hashes before any formal case. A topology or ordering mismatch is a stop, not a reason to regenerate an oracle after execution.

## 5. Accepted load history

The common accepted load-factor sequence is

```text
[0.00, 0.04, 0.08, 0.10, 0.12, 0.16, 0.20, 0.14, 0.08, 0.16, 0.20].
```

It includes loading, unloading and reloading. The direct history accepts exactly these values.

The driver-retry history differs only after accepted `lambda=0.08`:

1. attempt `lambda=0.20` with `snes_max_it=1`;
2. require a negative PETSc SNES converged reason;
3. discard the trial primary vector and all trial integration-point candidates;
4. restore the accepted `lambda=0.08` state;
5. continue through `0.10, 0.12, 0.16, 0.20, ...`.

This is a predeclared author-driver retry triggered by a PETSc terminal reason. It is not described as PETSc-native time-step cutback. If the frozen attempt converges within one iteration, the retry prerequisite is not met and dependent cases stop without changing the load or iteration cap.

The host-line-search history uses the same accepted load sequence and a declared lagged tangent relation on the reload `0.08 -> 0.16`. It must produce at least one PETSc-native nonaccepted line-search candidate identified by the retained C observer. If no such event is observed, host-native line-search coverage is `NOT_SUPPORTED_BY_FROZEN_HISTORY`.

## 6. Manufactured elastic reference

The independent assembly reference uses the same unit square with all boundaries prescribed by

```text
w_exact = A sin(pi x) sin(pi y), A = 1e-3,
b       = 2 G pi^2 A sin(pi x) sin(pi y).
```

The amplitude keeps the response strictly elastic. Uniform meshes `N=4,8,16` are used only in `P4D-REF-01`. The predeclared reference gates are:

- monotone decrease of the relative `L2` and `H1` errors;
- fitted relative `L2` order at least `1.70`;
- fitted relative `H1` order at least `0.80`;
- finest-grid relative `L2` error at most `5e-2`;
- finest-grid relative `H1` error at most `2e-1`.

This analytical reference checks assembly and boundary conditions. It does not validate the plastic constitutive lifecycle.

## 7. Solver contract

The pinned nonlinear configuration is:

```text
SNES type                 newtonls
line-search type          bt
absolute tolerance        1e-11
relative tolerance        1e-10
step tolerance            1e-12
maximum iterations        25
KSP type                  preonly
PC type                   lu
error if not converged    true for normal accepted attempts
```

The direct, retry, restart and negative-control histories use the consistent tangent. The designated line-search case uses a predeclared current-residual/accepted-state-lagged tangent relation. The accepted fields, rather than iteration counts, are compared with the direct consistent-tangent history.

## 8. Conventional and lifecycle observables

Conventional observables:

- PETSc terminal reason and nonlinear/linear iteration counts;
- residual norm and free-DOF equilibrium;
- top/bottom reaction balance;
- finite primary, stress and history arrays;
- `alpha >= 0` and nondecreasing at every accepted integration point;
- yield consistency at committed plastic points;
- manufactured-solution errors in `P4D-REF-01`.

Lifecycle observables:

- committed-state hashes before and after each native or driver-owned event;
- trial-candidate hash and reachability;
- persistent-state projection and restoration;
- residual/tangent state-version relation;
- PETSc C line-search vector, lambda and reason ledger;
- accepted-output source candidate and committed version;
- checkpoint payload identity and fresh-process restart parity;
- operator replay drift as a secondary observable.

Finite values and convergence do not substitute for lifecycle findings. A negative-control contract can pass while its primary scientific verdict is a lifecycle failure.

## 9. Evidence boundary

A future successful P4d execution could support a bounded single-rank DOLFINx/PETSc host-integration claim for this anti-plane plasticity model. It would not establish MPI/thread safety, large-scale performance, contact, damage, two-way multiphysics, Abaqus behavior, production UEL correctness, carbon-storage validity or completeness of the fault taxonomy.
