# L3-D0 canonical single-phase poroelastic benchmark specification

Status: FROZEN DESIGN for `L3-D1.0a`; no result is claimed here.

## Primary question

Can the transaction-safe lifecycle contract be carried into a canonical
single-phase poroelastic consolidation problem while analytical accuracy,
convergence, conservation, spatial stability and retry provenance remain
separate validation gates?

## Governing problem

The constrained one-dimensional column occupies `0 <= x <= H`, measured from
the drained top. Compression is positive and a constant load `q` is applied.

```text
q = K_d*epsilon + alpha*p
epsilon = (q-alpha*p)/K_d
zeta = S*p-alpha*epsilon
j = -mobility*dp/dx
C*dp/dt-mobility*d2p/dx2 = 0
C = S+alpha^2/K_d,  c=mobility/C
```

Boundary and initial conditions are `p(0,t)=0`, `dp/dx(H,t)=0`, and
`p(x,0+)=p0=alpha*q/(K_d*S+alpha^2)` for `0<x<=H`.

Frozen dimensionless values are `H=1`, `K_d=4`, `alpha=1`, `S=1/4`,
`mobility=1/2`, `q=1`, `C=1/2`, `c=1`, `p0=1/2`, initial settlement `1/8`
and final settlement `1/4`.

## Analytical oracle

For `lambda_m=(2m+1)*pi/(2H)`,

```text
p(x,t)/p0 = sum_m 4/((2m+1)*pi)
  * sin(lambda_m*x)*exp(-c*lambda_m^2*t)
p_bar(t)/p0 = sum_m 8/((2m+1)^2*pi^2)
  * exp(-c*lambda_m^2*t)
settlement = H*(q-alpha*p_bar)/K_d
Q_out = H*C*(p0-p_bar)
```

The independent series oracle stops only when its remaining envelope is below
`1E-15`, with at most 1000 terms. Pointwise error is evaluated only at positive
times.

## Discretization

Pressure is cell-centred on a uniform finite-volume mesh. Backward Euler uses
the drained half-cell face and impermeable lower face. A deterministic Thomas
algorithm solves each tridiagonal system. Settlement is reconstructed from
mean pressure. Storage change and integrated drained flux are recorded
independently at every accepted step.

## Lifecycle contract

Accepted pressure, time and cumulative outflow form the authoritative committed
state. Trial fields are immutable candidates until acceptance. `L3-RT-01`
compares a direct `dt=0.01` step with a rejected `dt=0.02` trial followed by the
same declared `dt=0.01` replay; the safe result must be exact. `L3-RT-02` seeds
one defect only: rejected trial pressure escapes into a persistent previous-
state cache. Declared state remains equal, but finite field and declared-mass
drift must be detected.

Passing one gate cannot substitute for another. This benchmark is not Abaqus,
not two-phase flow, not a fault-zone application and not a performance study.
