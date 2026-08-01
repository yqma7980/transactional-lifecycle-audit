# L6-D1 external-host lifecycle benchmark specification

**Design version:** L6-D1.0  
**Design status:** FROZEN_NOT_IMPLEMENTED  
**External host:** SciPy 1.17.1 `least_squares(method="trf")`

## Scientific question

Can a transaction-safe state adapter preserve committed-state immutability, callback-order robustness and accepted-output provenance when an independently maintained nonlinear host generates genuine nonaccepted trust-region evaluations; and can the same host expose finite drift from a deliberately rollback-external persistent cache?

## Frozen scalar problem

The host minimizes one half of the squared residual

```text
r(x;h) = x^3 - 2x + 2 + beta h
J(x)   = 3x^2 - 2
```

with `x0=1`. For safe cases, `beta=0` and every evaluation reads immutable committed history `h_c=0`. The positive local minimum has the independent stationary oracle

```text
x_star = sqrt(2/3)
r_star = 2 - (4/3)sqrt(2/3)
cost_star = 0.5 r_star^2.
```

For the unsafe negative control, `beta=1/20`. A rollback-external scalar `h_p` is initialized to zero. Each residual call reads the prior `h_p`, returns its residual, then incorrectly sets `h_p=x_trial` even when that host trial is not accepted. The Jacobian formula, load, host settings and committed state are unchanged.

## Host settings

- method: `trf`
- analytic Jacobian unless the callback-order case explicitly uses `2-point`
- `tr_solver="exact"`
- `x0=[1.0]`
- `ftol=xtol=gtol=1E-12`
- `max_nfev=100`
- `x_scale=1.0`
- `loss="linear"`
- no bounds
- finite-difference mode: `jac="2-point"` and `diff_step=1E-6`
- one process and one thread
- two independent processes per formal case

## State and event definitions

- Committed state: `(history, accepted_version)`, immutable during a host invocation.
- Trial candidate: call-local `(x, candidate_history=x, source_event_id)`.
- Residual packet: residual value plus declared committed/trial version.
- Tangent packet: Jacobian value plus declared state version.
- Host-accepted iterate: an iterate delivered by SciPy's callback.
- Nonaccepted residual evaluation: a residual event since the previous accepted callback that is not the matching accepted event.
- Physical accept: performed once, only after SciPy returns success and the final returned state passes validation.
- Accepted output: emitted once after physical accept; no residual, Jacobian or accepted-iterate callback may write accepted output.

## Case families

1. `L6-EH-RT-01`: safe transaction with genuine rejected host trials.
2. `L6-EH-OP-01`: accepted-output provenance.
3. `L6-EH-CO-01`: analytic-Jacobian versus host 2-point callback-order replay.
4. `L6-EH-RT-02`: seeded unsafe persistent-cache negative control.
5. `L6-EH-TV-01`: finite residual/Jacobian packet with deliberately mismatched state-version metadata, rejected before the host receives the Jacobian.

## Scope boundary

This is a scalar external-host lifecycle benchmark. It does not validate SciPy generally, arbitrary optimization hosts, thread safety, performance, Abaqus, production UEL behavior, two-way poromechanics, fault mechanics or CO2 plume predictions.
