# P5D frozen performance protocol

## Status and question

`design_status = FROZEN_NOT_IMPLEMENTED` and `execution_authorized = false`.

P5D asks a bounded software-engineering question: what execution, memory, and
storage cost is introduced by generic replay and by the complete lifecycle
ledger when the accepted scientific computation remains unchanged? It does
not ask whether instrumentation improves nonlinear convergence or physical
accuracy.

The 450 timing runs produced for the rejected AEDS manuscript are retained as
historical development evidence only. They are excluded from JSS RQ5 because
they were not generated under this frozen protocol.

## Subjects, workloads, and modes

The matrix contains three existing JSS subjects, two workload sizes, and three
instrumentation modes, for 18 cells.

- `M0_AUDIT_OFF`: production computation with lifecycle instrumentation off.
- `M3_GENERIC_REPLAY`: generic equal-declared-state replay with its required
  replay packets but without the full ownership/provenance ledger.
- `M6_FULL_TLA`: eligibility checks, version contracts, semantic provenance,
  replay comparison, and the complete event ledger.

S01 uses 32/128 triangular cells and 96/384 integration-point states. S02 uses
the canonical grids N=80/320. S03 uses the original scalar residual system and
an eight-block direct product. Before timing, the S03 medium implementation
must demonstrate that each block is an independent copy with the same root,
accepted state, residual definition, and callback semantics as S03 small.

## Repetition and environment

Each cell uses two unreported warm-up processes followed by ten timed fresh
processes. Every process is single-rank and single-thread. CPU affinity,
processor power mode, Python/environment identity, and dependency versions are
fixed and recorded before the first warm-up. A timing process executes exactly
one cell repetition; repetitions are not looped inside one interpreter.

No warm-up result enters a summary statistic. No slow formal run is deleted.
Unexpected host activity invalidates the affected cell rather than justifying
outlier removal.

## Work accounting

All elapsed work between process initialization and validated result closure is
included in wall and CPU time. Initialization and teardown are also reported
as separate components.

Production work and audit work are recorded separately:

- production residual, tangent, trial, accepted, and rejected evaluations are
  the evaluations required by the uninstrumented scientific trajectory;
- audit-only evaluations are the additional replay or validation evaluations
  required by M3 or M6.

Audit-only evaluations remain inside total timing. Their separate count is for
interpretability, not exclusion. Any mode that silently replaces, suppresses,
or reclassifies production evaluations fails the work-equivalence gate.

## Recorded metrics

Every formal process records:

- wall time and CPU time;
- peak resident set size;
- initialization and teardown time;
- serialization and hashing time;
- production residual/tangent/trial/accepted/rejected counts;
- audit-only residual/tangent/trial counts;
- serialized audit bytes and event-ledger bytes;
- accepted-output fingerprint and production-trajectory fingerprint;
- environment, process, thread, and affinity identity.

## Statistical summary

For each cell, report every timed value, median, IQR, and a 95% percentile
bootstrap interval using 10,000 resamples and seed `20260811`. Mode overhead is
computed within each subject/workload relative to M0 only after all equivalence
gates pass. No hypothesis of universal speedup or fixed overhead is tested.

Across-workload summaries are descriptive and cannot replace cell-level
absolute times. Adverse overhead is retained and discussed.

## Interpretation boundary

P5D can support bounded cost statements for these three subjects, two sizes,
one machine, and a single-thread configuration. It cannot establish parallel
scaling, commercial-solver overhead, distributed callback safety, energy cost,
or production-model performance.

## Stop rules

Stop before timed execution if any qualification or equivalence gate in
`P5D_equivalence_gates.json` fails. Stop an active cell if accepted output,
production trajectory, solver options, environment identity, or duplicate
schema differs across modes. Preserve all stopped evidence; do not change the
workload, tolerance, instrumentation mode, or number of repetitions after
observing timing values.
