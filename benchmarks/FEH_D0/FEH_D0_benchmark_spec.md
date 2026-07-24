# FEH-D0 benchmark specification

Status: `FROZEN_BEFORE_IMPLEMENTATION`

## Scientific question

Can a transactional lifecycle audit distinguish safe and rollback-external state handling in a nontrivial open two-dimensional finite-element host that owns increments, Newton iterations, line-search probes, cutbacks, accepted integration-point history, checkpoints, restarts, and accepted output?

## Open host and environment

- Host: scikit-fem 12.0.2 (BSD-3-Clause), used for the quadrilateral mesh, finite-element basis, quadrature fields, residual assembly, and tangent assembly.
- Linear algebra: SciPy sparse direct solve.
- Process model: one Python process and one numerical thread per formal run.
- Repetitions: two fresh-process repetitions per formal case.
- Abaqus and the private production UEL are excluded.

## Governing problem

The domain is the unit square.  The scalar displacement `w(x,y)` represents anti-plane shear.  Equilibrium is

`div(tau) = 0`,

with shear strain `gamma = grad(w)` and shear stress

`tau = G (gamma - p)`.

The integration-point internal variables are the two-component plastic shear strain `p` and accumulated plastic shear `kappa`.  The yield function is

`f = ||tau_trial|| - (tau_y(x,y) + H kappa_n)`.

For `f > 0`, the radial return is

`delta_lambda = f / (G + H)`,

`p_trial = p_n + delta_lambda n`,

`kappa_trial = kappa_n + delta_lambda`,

where `n = tau_trial / ||tau_trial||`.  The algorithmic tangent is evaluated from the same declared material packet as the residual.  A spatially heterogeneous yield stress creates a soft inclined band and a nonuniform plastic field.

## Discretization and loading

- Primary mesh: 8 by 6 bilinear quadrilateral elements.
- Quadrature: tensor-product 2 by 2 Gauss rule, 192 material points.
- Hold-out mesh: 10 by 7 bilinear quadrilateral elements, 280 material points.
- Boundary conditions: `w=0` on the bottom; monotonically prescribed `w=lambda*w_max` on the top; traction-free sides.
- Material constants: `G=10`, `H=1`, base `tau_y=0.55`, band factor `0.72`.
- Primary accepted load levels: `lambda = [0.2, 0.4, 0.6, 0.8, 1.0]`, `w_max=0.12`.
- Hold-out accepted load levels: `lambda = [0.15, 0.35, 0.55, 0.75, 0.9, 1.0]`, `w_max=0.11`.
- Newton tolerance: `max(1e-11, 1e-10*||R_free,0||_2)`.
- Maximum Newton iterations: 20.
- Line-search acceptance: Armijo residual decrease with `c=1e-4`; allowed alphas `[1, 0.5, 0.25, 0.125]`.
- Rejected-line-search history: at the first Newton correction toward `lambda=0.8`, evaluate a predeclared `alpha_probe=8`, require it to fail the same Armijo test, reject it, and continue with the ordinary allowed alphas.
- Cutback history: from the accepted `lambda=0.6` state, attempt `lambda=1.0` with a predeclared one-iteration attempt cap, reject and roll back, then accept the ordinary `lambda=0.8` and `1.0` sequence.
- Restart history: checkpoint immediately after accepted `lambda=0.6`, instantiate a fresh host, restore the authoritative payload, and continue at `lambda=0.8` and `1.0`.

## Declared state and semantic output

The declared replay packet contains the primary vector, load, committed integration-point state hash, persistent-state version and hash, residual version, tangent version, serializer version, mesh identity, and material identity.  Diagnostic run IDs, event IDs, timestamps, and file paths are excluded from semantic comparison.

Accepted output is emitted only after commit and contains the accepted displacement, reactions, integration-point stress and internal variables, convergence metrics, and their authoritative provenance.  Trial output may be logged but is unreachable from accepted output.

## Admissible histories

All compared histories start from an identical authoritative committed-state fingerprint, use the same mesh, equations, boundary data, material data, operator versions, deterministic environment, and accepted load sequence, and terminate at the same replay call or accepted endpoint.

Allowed nonaccepting events are `BeginAttempt`, `TrialEvaluate`, `FormResidual`, `FormTangent`, `RejectLineSearch`, `RejectAttempt`, `Rollback`, `CutbackAndRetry`, `CheckpointWrite`, and `RestartRead`.  The direct history omits deliberately inserted rejected probes.  Forbidden disturbances are parameter changes, mesh changes, boundary changes, random seeds, accepted output feedback in the safe path, and external file mutation.

## Implementations

- `safe_transactional`: every trial is reconstructed from immutable committed integration-point state; reject restores the attempt snapshot; output reads only accepted state.
- `unsafe_trial_cache`: a seeded hidden integration-point cache is updated by each trial and is not rolled back.  Its coupling strength is fixed by each case.
- `unsafe_output_feedback`: a trial-derived output mirror is updated before acceptance and feeds the next material evaluation.
- `operator_version_mismatch`: tangent metadata differs from the residual packet while numerical values remain finite; the host must reject before correction, commit, checkpoint, or accepted output.

## Reference and balance observables

The uniform-material patch subcase has a homogeneous anti-plane solution and is used as an analytical assembly/reference check.  The heterogeneous lifecycle case is compared against the safe direct accepted trajectory frozen by hash.  Conventional gates use finiteness, Newton convergence, free-DOF residual, top/bottom reaction balance, accepted-field error, and internal-variable bounds.  TLA uses equal-declared-state replay of residual, tangent, candidate and semantic output provenance.

## Evidence boundary

Passing FEH-D0 supports an open-host, two-dimensional, multi-element and multi-integration-point lifecycle claim.  It does not establish Abaqus semantics, parallel callback safety, finite-strain plasticity, two-way flow-mechanics coupling, or a carbon-storage application.
