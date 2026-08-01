# L4-D0 canonical two-phase displacement benchmark specification

Status: `FROZEN_NOT_IMPLEMENTED` for design `L4-D1.0`. No execution result is
claimed by this document.

## Primary question

Can the transaction-safe lifecycle contract be carried from the L3
single-phase column into a nonlinear two-phase displacement problem while
entropy-reference accuracy, front location, phase-wise conservation, pressure
reconstruction, one-way mechanical response and retry provenance remain
separate validation gates?

## Scope and claim boundary

The benchmark is a one-dimensional, incompressible, immiscible displacement
problem. It contains a moving saturation front and nonlinear phase mobility.
Capillary pressure, gravity, compressibility, residual saturation, hysteresis,
fault contact and permeability feedback are deliberately excluded so that an
independent Buckley-Leverett entropy solution remains available.

The mechanical quantity is a declared one-way flow-to-mechanics observable.
It does not feed strain, stress or displacement back into porosity,
permeability, pressure or saturation. Passing `L4-MECH-01` therefore cannot be
described as two-way poromechanical coupling.

## Frozen flow problem

The dimensionless domain is `0 <= x <= H`, with

```text
H = 1
phi = 1
q_t = 1
k = 1
mu_w = mu_n = 1
S_n(x,0) = 0
S_n(0,t) = 1
p(1,t) = 0
```

There are no residual saturations. The closures are

```text
k_rn(S_n) = S_n^2
k_rw(S_n) = (1-S_n)^2
lambda_n = k_rn/mu_n
lambda_w = k_rw/mu_w
lambda_t = lambda_n+lambda_w
f_n(S_n) = lambda_n/lambda_t
f_w = 1-f_n
```

With constant total Darcy flux, the nonwetting saturation equation is

```text
phi*dS_n/dt + q_t*d(f_n(S_n))/dx = 0.
```

The wetting saturation is `S_w=1-S_n`. Before breakthrough, the exact phase
mass balances are

```text
d/dt integral(phi*S_n dx) = q_t*(f_n,in-f_n,out)
d/dt integral(phi*S_w dx) = q_t*(f_w,in-f_w,out).
```

## Independent entropy oracle

For the frozen equal-viscosity quadratic closures,

```text
f_n(S) = S^2/(S^2+(1-S)^2)
f_n'(S) = 2*S*(1-S)/(S^2+(1-S)^2)^2.
```

The shock saturation and dimensionless shock speed are

```text
S_star = 1/sqrt(2)
v_shock = (1+sqrt(2))/2
x_shock(t) = v_shock*t
t_breakthrough = 1/v_shock.
```

For `xi=x/t`, the entropy solution used by the oracle is

```text
S_n = 0                         for xi > v_shock
f_n'(S_n) = xi, S_star<=S_n<=1 for 0 < xi <= v_shock
S_n = 1                         at xi = 0.
```

The root is obtained by an oracle-local bisection on `[S_star,1]` with a
residual target of `1E-14`. Cell averages and pressure integrals are evaluated
by an oracle-local adaptive quadrature split exactly at `x_shock`; its absolute
target is `1E-13`. The oracle must not import the finite-volume update,
lifecycle variants or case dispatcher.

## Pressure and one-way mechanical observables

Because `p_n=p_w=p` when `p_c=0`, total-pressure resistance follows from

```text
dp/dx = -q_t/(k*lambda_t(S_n)),  p(H,t)=0,
p(x,t) = integral_x^H q_t/(k*lambda_t(S_n(y,t))) dy.
```

The flow solver reconstructs pressure from accepted cell saturation and face
resistances. The independent oracle integrates the entropy saturation instead.

The declared one-way mechanical observable uses `K_d=4` and `alpha=1`:

```text
u_top(t) = alpha/K_d * integral_0^H p(x,t) dx.
```

This scalar measures the response to accepted pressure only. It is not fed
back into the flow problem.

## Frozen discretization

The numerical saturation is a cell average on a uniform finite-volume mesh.
The accepted update is first-order conservative upwinding:

```text
S_i^(m+1) = S_i^m - dt*q_t/(phi*dx)
            * (f_n(S_i^m)-f_n(S_(i-1)^m)),
```

with boundary flux `f_n(S_in)=1`. The frozen maximum characteristic speed is
`max f_n'=2`; a listed CFL therefore means `dt=CFL*dx/2`, except for the final
step required to land exactly on a checkpoint. No clipping or post-update mass
repair is permitted.

Cell pressure is reconstructed from the accepted saturation by summing
piecewise-constant resistance from the right pressure boundary. The mechanical
observable is the midpoint integral of that accepted pressure field.

## Lifecycle contract

The authoritative committed state contains accepted time, accepted saturation,
cumulative wetting/nonwetting boundary transfer and accepted version. Every
trial is an immutable candidate. Accepted profiles and mechanical observables
are generated only from the accepted committed state.

`L4-RT-01` compares a direct `dt=0.005` step with a rejected `dt=0.01` trial
followed by the same declared `dt=0.005` replay. The safe variant discards the
trial candidate and must reproduce the direct accepted state exactly.

`L4-RT-02` seeds one defect only: the rejected trial saturation escapes into a
persistent previous-state cache and is used as the replay source even though
the declared committed state is unchanged. The negative control must produce
finite, reproducible field and declared phase-mass drift. Detecting that drift
validates the harness, not the unsafe algorithm.

## Frozen schedules

- Reference checkpoints: `t=0.1,0.2,0.4`, `N=800`, `CFL=0.4`.
- Spatial refinement: `N=80,160,320`, `CFL=0.4`, `t=0.2`.
- Temporal refinement: `N=800`, `CFL=0.4,0.2,0.1`, compared with a frozen
  same-mesh time reference at `CFL=0.0125`, `t=0.2`.
- Phase mass balance: `N=256`, `CFL=0.4`, `t=0.6`.
- Front history: `N=800`, `CFL=0.4`, `t=0.1,0.2,0.4,0.6`.
- One-way mechanics: `N=800`, `CFL=0.4`, `t=0.1,0.2,0.4`.
- Stability: `N=256`, `CFL=0.4`, `t=0.6`.
- Retry controls: `N=32`, rejected `dt=0.01`, replay `dt=0.005`.

All reference checkpoints precede breakthrough. Accuracy, conservation,
stability, lifecycle safety and reproducibility are independent gates; passing
one cannot substitute for another.

