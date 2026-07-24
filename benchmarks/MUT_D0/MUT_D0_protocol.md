# MUT-D0 mutation-strength protocol

Status: `FROZEN_BEFORE_IMPLEMENTATION`

## Operator-sensitivity question

Does a nonempty mutation-strength interval exist in which conventional finite-value, convergence, accuracy and reaction-balance gates all pass, while a seeded rollback-external state mutation produces finite residual or tangent replay drift above the frozen operator threshold?

## Frozen development sweep

- Model: FEH-D0 heterogeneous 8 by 6 mesh.
- History: one deliberately rejected line-search probe before the replay increment.
- Mutation: rollback-external trial-cache mixing only.
- Strengths: `0`, `1e-12`, `3e-12`, `1e-11`, `3e-11`, `1e-10`, `3e-10`, `1e-9`, `3e-9`, `1e-8`, `3e-8`, `1e-7`, `3e-7`, `1e-6`, `3e-6`, `1e-5`, `3e-5`, `1e-4`, `3e-4`, `1e-3`, `3e-3`, `1e-2`.
- Repetitions: two fresh single-process, single-thread runs at every strength.

## Frozen gates

- finite: all normal physical values finite and below `1e100`.
- convergence: all accepted increments meet FEH-D0 Newton tolerance and iteration cap.
- accuracy: relative accepted displacement, reaction, stress and accumulated-plastic-strain errors versus safe direct are each at most `1e-5`.
- balance: normalized top/bottom reaction defect at most `1e-9`.
- operator-replay drift detection: replay residual relative drift or tangent relative drift exceeds `1e-10`, after the zero-strength same-track envelope has first been verified not to exceed `1e-12`.
- reproducibility: both repetitions have the same boolean classification and drift values within `1e-12` absolute and relative tolerance.

The operator-sensitivity interval is the set of tested strengths for which all four conventional gates pass and operator-replay drift exceeds the frozen threshold. No interpolation between tested strengths is claimed, and the interval is not a complete TLA detection boundary.

## Predeclared confirmation configuration

Before formal execution, the confirmation configuration is declared as:

- Mesh: heterogeneous 10 by 7 Q1 mesh.
- Accepted load sequence: `[0.15, 0.35, 0.55, 0.75, 0.9, 1.0]`.
- Rejected probe: before the `lambda=0.75` accepted attempt, evaluate a trial at `lambda=0.84`, reject it, restore the declared primary state, and replay `lambda=0.75`.
- Strength selection: if the development sweep yields a nonempty distinctive-detection set, select its median tested strength after sorting; if the count is even, select the lower middle tested strength.  This rule is fixed before results.
- Repetitions: two fresh single-process, single-thread runs.
- confirmation pass: conventional gates pass, operator-replay drift exceeds the frozen threshold, and repetitions agree.

If the development set is empty, MUT-D0 is `NOT_SUPPORTED` and the confirmation configuration is not run. If the development set is nonempty but the confirmation configuration fails, the operator-sensitivity claim is rejected. Neither outcome permits threshold tuning or replacement of the confirmation configuration.

## Detection table

The final table must report every tested strength, all conventional metrics, replay drifts, both repetition outcomes, A4 status, and a four-way classification: `BELOW_OPERATOR_REPLAY_DRIFT_THRESHOLD`, `OPERATOR_REPLAY_DRIFT_DETECTED_WITH_CONVENTIONAL_GATES_PASS`, `OPERATOR_REPLAY_DRIFT_DETECTED_WITH_CONVENTIONAL_GATE_FAILURE`, or `INVALID_RUN`. With one seeded mutation family, the study reports a tested operator-sensitivity interval, not a full-TLA detection boundary or a general false-positive or false-negative rate.
