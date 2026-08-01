# L5-D0 independent two-phase validation specification

Status: FROZEN_NOT_IMPLEMENTED

## Physical problem

The domain, phase model and dimensionless parameters match L4-D1: H=phi=q=k=mu_w=mu_n=1, initial non-wetting saturation zero, injected saturation one, krn=Sn^2, krw=(1-Sn)^2, incompressible immiscible phases, no gravity and no capillary pressure. The pre-breakthrough entropy shock has saturation 1/sqrt(2), speed (1+sqrt(2))/2 and breakthrough time 2/(1+sqrt(2)).

Pressure is reconstructed from the independently computed total mobility with right pressure zero. The scalar mechanical observable is u=(alpha/Kd) integral p dx, alpha=1 and Kd=4. It is one-way only.

## Independent discretization

L5 uses piecewise-linear minmod reconstruction, a Rusanov numerical flux with frozen global characteristic bound 2, and SSPRK2. The time step is dt=CFL dx/2 with exact closure of requested output times. Saturation clipping and mass repair are prohibited.

The independent reference uses a separately coded entropy root and fixed eight-point Gauss-Legendre quadrature, splitting each interval at the analytical shock.

## Formal cases

- L5-IV-REF-01: independent reference accuracy at t=0.1, 0.2 and 0.4.
- L5-IV-CV-01: N=80,160,320 convergence at t=0.2.
- L5-IV-MB-01: separate wetting and non-wetting phase balance to t=0.6.
- L5-IV-FR-01: front parity at t=0.1,0.2,0.4,0.6.
- L5-IV-OP-01: accepted-output provenance with a live unaccepted trial.
- L5-IV-RT-01: safe retry/rollback parity.
- L5-IV-RT-02: seeded unsafe finite-drift negative control.
- L5-IV-XP-01: field parity against hash-verified L4 formal profiles at t=0.1,0.2,0.4.

Every case is run twice in independent single-process, single-thread processes. No in-process repetition is permitted.
