# L2 host-lifecycle benchmark

Status: **D1 MINIMAL SLICE FROZEN AND IMPLEMENTED / NOT EXECUTED**

## Purpose

L2 is the first benchmark level that introduces a global nonlinear host and an
actual retry/cutback lifecycle. It tests whether equal accepted bases and equal
declared replay packets remain invariant under changed host call histories.

L2 does not reuse or simplify the production two-phase UEL. The D1 minimal
slice is a new standalone reference host built from the frozen L1 equations
and an independent fraction oracle.

## Current deliverables

- 'L2_D0_benchmark_spec.md': model, lifecycle histories and frozen questions.
- 'L2_D0_case_matrix.csv': proposed formal cases and expected classifications.
- 'L2_D0_acceptance_gates.md': design, implementation, execution and stop gates.
- 'L2_D0_data_contract.md': call-ledger and accepted-checkpoint fields.
- 'L2_D0_execution_boundary.md': authorization and claim limits.
- 'L2_D1_execution_freeze.json': frozen host, retry and numerical controls.
- 'L2_D1_minimal_case_matrix.csv': five authorized, unexecuted cases.
- 'L2_D1_implementation_plan.md': implementation and claim boundaries.
- 'src/': standalone host, model, state, variants and case definitions.
- 'oracle/': independent fraction-only equilibrium oracle.
- 'schemas/': frozen event, checkpoint and result columns.
- 'tests/': defined tests; not executed in the implementation-only turn.
- 'run_l2_d1.py': double-gated runner; no run has been authorized.

## Design boundary

The D0 package remains the roadmap for all 14 cases. D1 freezes and implements
only 'REF-01/02 + RT-01/02/03'. Host execution, duplicate-run comparison and
all remaining case families still require a separate authorization. No result
or PASS/FAIL conclusion exists at D1 implementation time.

## Claim boundary

Even a future L2 pass would establish only lifecycle behavior for one minimal
host finite-element problem. It would not establish:

- complete Abaqus/UEL safety;
- restart parity;
- coupled flow-mechanics accuracy;
- conservation or spatial convergence;
- thread safety beyond tested settings;
- production robustness;
