# P5 scaled-threshold selection rule

Status: `FROZEN_STATIC_NOT_IMPLEMENTED`

## 1. New binary strength grid

Each scaled mutation uses `Delta q = eta_j * s_q` with a fixed positive sign. The grid is binary and was not copied from the decimal MUT-D0 sweep.

| j | binary exponent | eta_j |
|---:|---:|---:|
| 0 | -48 | `3.5527136788005009e-15` |
| 1 | -45 | `2.8421709430404007e-14` |
| 2 | -42 | `2.2737367544323206e-13` |
| 3 | -39 | `1.8189894035458565e-12` |
| 4 | -36 | `1.4551915228366852e-11` |
| 5 | -33 | `1.1641532182693481e-10` |
| 6 | -30 | `9.3132257461547852e-10` |
| 7 | -27 | `7.4505805969238281e-09` |
| 8 | -24 | `5.9604644775390625e-08` |
| 9 | -21 | `4.76837158203125e-07` |
| 10 | -18 | `3.814697265625e-06` |
| 11 | -15 | `3.0517578125e-05` |
| 12 | -12 | `0.000244140625` |
| 13 | -9 | `0.001953125` |
| 14 | -6 | `0.015625` |

All 15 levels are executed once in ascending order in separate fresh processes. Execution cannot stop at the first apparent detection. No level outside this table may be added.

## 2. Frozen field bindings

| Family | Development field/event | Declared scale | P6 confirmation binding |
|---|---|---:|---|
| `F01` | add to `trial_cache.gamma_p[cell=0,qp=0,component=0]` during the rejected `lambda=0.20` attempt; unsafe rollback leaves it unrestored | `s_q=tau_y0/G=0.1` | same selected `eta_j` at `cell=31,qp=2,component=1`; no reselection |
| `F02` | add to declared persistent snapshot `alpha[cell=0,qp=1]`; unsafe rollback omits that field | `s_q=tau_y0/G=0.1` | no separate P3 confirmation case |
| `F05` | add the rejected trial top-reaction diagnostic to `feedback_mirror_E`; the first `lambda=0.10` replay consumes the mirror | `s_q=tau_y0*L=1` | same selected `eta_j` at the predeclared secondary callback `feedback_mirror_J`; no reselection |
| `F07` | increment declared process-global `callback_bias_F` at each extra nonaccepting residual callback; unsafe rollback omits it | `s_q=1` | no separate P3 confirmation case |

If an implementation cannot expose exactly these fields and events without changing the frozen P4d equations, it returns `NOT_SUPPORTED_FIELD_BINDING`; another site is not substituted.

## 3. Family-specific drift ratios

For each level, compute `Z_m=d_m/T_m` using the P5 null-envelope threshold for residual (`M_R`) and tangent (`M_J`). Define

```text
Z_family(eta_j) = max(Z_R(eta_j), Z_J(eta_j)).
```

For `F05`, the exact rejected-source reachability failure must also be present. For `F01`, `F02` and `F07`, the exact owner/restoration failure must also be present. Operator separation alone is never the primary lifecycle verdict.

## 4. Conventional quiet gates

A grid level is eligible only when:

- all values are finite and accepted attempts have positive SNES reasons;
- the frozen P4d M1-M3 mechanics gates pass;
- final accepted primary, stress, history, reaction and semantic output fields remain within the existing `1e-10` scaled comparison against the safe control where the P3 method contract expects them to remain quiet;
- checkpoint and final-state baselines remain quiet where P3 declares them applicable;
- no unrelated ownership, source, version or event-order relation changes.

These gates preserve the intended comparison region in which ordinary endpoint checks remain quiet while a predeclared lifecycle relation and its secondary replay consequence can be examined.

## 5. Selection algorithm

After every grid level has completed, choose the smallest index `j` satisfying all of the following:

1. `j<14`;
2. all levels `0..j+1` satisfy the applicable conventional quiet gates;
3. the expected exact lifecycle violation is present at both `eta_j` and `eta_(j+1)`;
4. `Z_family(eta_j)>=10` and `Z_family(eta_(j+1))>=10`;
5. all numeric values are finite.

Then run two new fresh-process verification repetitions at `eta_j` and two at `eta_(j+1)`. The repetitions must reproduce the exact lifecycle verdict, the quiet conventional gates and the `Z_family>=10` separation. The earlier sweep process is not counted as either verification repetition.

The selected P6 strength is `eta_j`. P3 confirmation cases receive exactly the same dimensionless value. Confirmation output may not change the strength, threshold, site or callback.

## 6. Non-support outcomes

- No qualifying adjacent pair: `NOT_SUPPORTED_AT_FROZEN_SCALE`.
- Null envelope or confirmation unstable: `NOT_SUPPORTED_NULL_ENVELOPE_UNSTABLE`.
- A conventional gate alarms before separation is established: `NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY`.
- Duplicate verification differs: `BLOCKED_FRESH_PROCESS_NONREPEATABILITY`.

No interpolation, extrapolation, added amplitude, alternate seed or relaxed gate is permitted.
