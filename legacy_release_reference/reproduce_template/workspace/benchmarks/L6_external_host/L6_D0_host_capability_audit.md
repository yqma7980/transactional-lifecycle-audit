# L6-D0 external-host capability audit

**Status:** CAPABILITY CONFIRMED / NOT FORMAL L6 EVIDENCE  
**Host:** SciPy 1.17.1 `scipy.optimize.least_squares(method="trf")`  
**Environment:** Python 3.12.10, NumPy 2.4.3, one process, one thread

## Host-lifecycle capability

The local SciPy TRF implementation evaluates `fun(x_new)` before deciding whether actual reduction is positive. It updates the current state and Jacobian only when `actual_reduction > 0`, then invokes the public callback with the current accepted iterate. Local source locators are `scipy/optimize/_lsq/trf.py:340,368,393-399` for the bounded path and `:514,543,568-574` for the no-bounds path. The frozen source SHA-256 values are recorded in the capability JSON and execution freeze.

A deterministic scalar probe used `r(x)=x^3-2x+2`, `J(x)=3x^2-2` and `x0=1`. The host made 20 residual evaluations, 9 Jacobian evaluations and 8 accepted-iterate callbacks. Ten residual evaluations were not accepted host iterates. This establishes that the installed host exposes a real trial/accept distinction suitable for a lifecycle benchmark.

## Interpretation boundary

The probe is API capability evidence only. It is not a formal L6 case, not a performance measurement and not evidence for Abaqus, production, two-way coupling or CO2 applications. Formal L6 claims require a frozen adapter, case matrix, duplicate independent executions and source-data audit.
