# L0 scalar replay benchmark specification

Status: frozen pre-execution specification v1.0

## Purpose

L0 isolates state-lifecycle behavior from finite elements, constitutive complexity, coupling physics and Abaqus. It asks one controlled question:

> At identical declared trial and committed state, can different discarded call histories change the residual only because a physics-relevant persistent value escaped rollback?

## Declared model

```text
c_n = 1
F(x;c_n) = x - c_n
alpha = 0.5
```

The replay query is always `x=1`, so the intended residual is exactly zero.

## Variants

| Variant | State rule | Expected lifecycle verdict |
|---|---|---|
| `unsafe_persistent` | every evaluation writes `p <- x_trial`; reject does not restore `p` | seeded fail |
| `safe_local` | residual is a pure function of declared `x,c_n` | pass |
| `safe_transactional` | trial `p` is a candidate; reject discards it; accept promotes it once | pass |

## Scenarios and frozen expectations

| Scenario | Histories compared | Unsafe expected `Delta R` | Safe expected `Delta R` |
|---|---|---:|---:|
| discarded trial replay | rejected `x=2` before replay versus direct replay | `2 alpha = 1.0` | `0.0` |
| call-order permutation | rejected `2,3` versus `3,2` before replay | `alpha = 0.5` | `0.0` |
| terminal-call noninterference | inserted terminal `x=4` versus no terminal call | `4 alpha = 2.0` | `0.0` |

All chosen values are exactly representable in binary floating point. The frozen tolerance is therefore `0.0` for L0-1.0.

## Hard gates

1. The two replay histories have identical declared-state fingerprints.
2. Every residual and `Delta R` is finite.
3. All three unsafe scenarios match the predeclared nonzero values.
4. Both safe variants return exact zero for all three scenarios.
5. Rejected transactional candidates leave committed state unchanged.
6. Duplicate complete executions produce identical summaries and ledgers.
7. The expected matrix is stored before execution in `expected_results.json`.

## Interpretation

A benchmark pass means that the harness detects its seeded defect and accepts its seeded safe controls. It does not show that Abaqus, cp189 or another framework contains the defect. It does not establish physical accuracy, convergence, conservation, performance or cross-framework generality.

## Outputs

- `results/l0_summary.json`: scenario-level verdicts.
- `results/l0_call_ledger.csv`: every evaluation/reject event and before/after fingerprints.
- `results/l0_manifest.json`: source and result SHA-256 plus runtime identity.
