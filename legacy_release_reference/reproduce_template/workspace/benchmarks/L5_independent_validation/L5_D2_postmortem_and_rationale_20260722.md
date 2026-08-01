# L5-D2 convergence-protocol postmortem and rationale (2026-07-22)

Status: `DESIGN_RATIONALE_ONLY`

## Preserved L5-D1 outcome

L5-D1 remains `PRECHECK_FAIL_NOT_FORMAL_EVIDENCE`. Its three-level convergence prerequisite used the minimum of all adjacent-pair orders as a hard gate. The front sequence produced an observed order of `0.6294266281954826`, below the frozen `0.7` threshold, so no formal L5-D1 case was executed. This record is not reclassified as an implementation failure or a formal L5 result.

The post-failure `N=640` and `N=1280` calculations are diagnostic only. They are not promoted into L5-D2 formal evidence and are not used to change the `0.7` threshold, any absolute-error threshold, the solver, the reference, or the physical model.

## Numerical-analysis basis for a revised estimator

`[ESTABLISHED]` For a positive error model `e(h)=C h^p`, the observed order is the slope of `log(e)` against `log(h)`. NASA's grid-convergence guidance explicitly permits a least-squares slope when several grid levels are available and warns that a small number of points is less reliable.

`[ESTABLISHED]` Eca and Hoekstra recommend redundant systematically refined grids and least-squares fitting when scatter is expected. Their procedure uses fit scatter as a quality diagnostic and identifies monotonic convergence as the well-behaved case. The locally archived paper is `literature/method_support/Eca_Hoekstra_2014_grid_refinement_least_squares.pdf`, DOI `10.1016/j.jcp.2014.01.006`.

`[ESTABLISHED]` Banks and Aslam show that convergence-rate estimates for discontinuous solutions can depend strongly on how three approximations are compared. Their analysis explains why a single adjacent triplet can give an apparently irregular estimate even when a uniformly refined sequence has a predictable aggregate trend. The locally archived paper is `literature/method_support/Banks_Aslam_2013_Richardson_discontinuities.pdf`, DOI `10.1007/s10915-013-9693-0`.

`[INFERRED]` These sources support replacing the L5-D1 single-worst-adjacent-pair veto with a predeclared five-level log-log regression plus strict monotonic-error gate. They do not establish that Richardson extrapolation is valid at the moving front, so L5-D2 will not extrapolate the front to zero grid size and will not report a Richardson uncertainty band. The front regression is only a bounded empirical convergence statistic against the independent exact front location.

## Frozen L5-D2 convergence statistic

For each metric `m` and each predeclared level `N_i in {80,160,320,640,1280}`:

```
h_i = 1/N_i
x_i = log(h_i)
y_i = log(e_m,i)
p_m = sum((x_i-x_bar)(y_i-y_bar)) / sum((x_i-x_bar)^2)
```

The formal convergence gate is:

1. all five errors are finite and strictly positive;
2. `e_80 > e_160 > e_320 > e_640 > e_1280` for every metric;
3. `p_m >= 0.7` for saturation L1, pressure relative L2, front absolute error, and one-way displacement absolute error.

All four adjacent-pair orders, `R^2`, slope standard error, intercept, and log-fit residuals are recorded. They are diagnostics, not additional pass/fail thresholds. This avoids introducing an unreferenced fit-quality threshold after inspecting the diagnostic sequence. Existing absolute-error, phase-balance, provenance, safe/unsafe, parity, finite, bounds, repetition, and source-independence gates remain unchanged.

## Design-only diagnostic audit

The stored L5-D1 failure packet was evaluated only to check that the proposed statistic is defined and discriminating. This calculation is `DESIGN_DIAGNOSTIC_ONLY`, not formal evidence:

| Metric | Five-level OLS order | R2 | Slope SE | Strictly monotone |
|---|---:|---:|---:|---|
| Saturation L1 | 0.820780763580593 | 0.997088042827739 | 0.0256089799216483 | yes |
| Front absolute | 0.808594669261771 | 0.996579605889894 | 0.0273496846866381 | yes |
| Pressure relative L2 | 0.869966377152014 | 0.999741557583838 | 0.00807569418324251 | yes |
| One-way displacement absolute | 0.873960184223913 | 0.999803329709272 | 0.00707690084458121 | yes |

The revised protocol is therefore mathematically defined and does not make the old diagnostic sequence unusable. This table must not be copied into the eventual OBSERVED-L5 result as a formal run.

## Evidence boundary

`[OPEN]` L5-D2 has not been implemented or run. Passing the revised convergence gate would support independent-code agreement for this frozen one-dimensional problem only. It would not prove Abaqus correctness, production readiness, two-way flow-mechanics validity, CO2 plume prediction, fault stability, performance, or general solver independence.
