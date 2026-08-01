# L1 material-point and one-element lifecycle benchmark

Status: **L1-MP PASS / L1-E1 NOT IMPLEMENTED OR EXECUTED**  
Design version: `L1-D1.0`  
Date: 2026-07-21

## Purpose

L1 moves the L0 replay principle into a genuine path-dependent constitutive update and a one-integration-point finite-element operator. It remains independent of Abaqus and of the production UEL.

The design has two sequential gates:

1. `L1-MP`: a one-dimensional elastoplastic material point;
2. `L1-E1`: a two-node, one-integration-point bar element evaluated at prescribed states.

`L1-E1` may be executed only after `L1-MP` passes. Neither gate includes a global nonlinear solve. Forced Newton cutback trajectories and accepted-field parity belong to L2.

## What is frozen

- governing equations and analytical reference values;
- committed, trial, persistent and output state ownership;
- unsafe seeds and safe controls;
- replay histories and case matrix;
- numerical tolerances and hard stop rules;
- call-ledger, summary and provenance schemas;
- implementation order and claim boundaries.

## Observed L1-MP result

- all 12 L1-MP cases and all 25 scenario-variant outcomes passed;
- safe local and transactional controls produced no replay false positives;
- seeded unsafe trial-cache and output-feedback paths produced finite nonzero drift;
- the primary discarded-plastic-trial seed reproduced `Delta stress = -205/121` within `1e-12`;
- the 40-column ledger contains 202 call rows and the accepted-state table contains 9 rows;
- six deterministic artifacts were byte identical across two complete executions;
- 24 unit, schema, lifecycle, oracle and artifact tests passed;
- no Abaqus process or production model was used.

`MP-LC-02` received a documented pre-execution seed erratum: the original monotonic permutation left the same hidden plastic state, so it was replaced before formal execution by the same `+0.03/-0.03` discarded packets in opposite order. Equations, tolerances and expected classifications were unchanged.

## What remains open

`L1-E1` was neither implemented nor executed. Full L1, host integration and L2-L6 therefore remain open. No global nonlinear solve, conservation test, coupled-flow benchmark or application result is implied.

## File map

```text
README.md                              scope and status
L1_benchmark_spec.md                  equations, variants and reference values
L1_state_contract.md                  ownership and event contract
L1_case_matrix.csv                    predeclared cases and expected verdicts
L1_acceptance_gates.md                metrics, tolerances and branch rules
L1_data_contract.md                   output artifacts and provenance rules
L1_implementation_execution_plan.md   gated implementation and execution order
expected_results_template.json        frozen constants and expected classifications
schemas/l1_call_ledger_columns.csv    call-level audit schema
L1_MP_execution_freeze.json           concrete MP packets and seed erratum
src/                                  standalone MP implementation
tests/                                independent oracle and lifecycle tests
run_l1_mp.py                          one complete MP execution
finalize_l1_mp.py                     duplicate-run hard gate and finalizer
results/                              final evidence, summaries and hashes
schemas/l1_run_summary.schema.json    machine-readable summary schema
```

## Claim boundary

The observed pass applies only to the standalone L1-MP harness. It shows that this harness detects its seeded material-point lifecycle defects without flagging its safe references. It does not establish L1-E1, Abaqus safety, global Newton robustness, conservation, poromechanics accuracy, two-phase-flow validity, cross-framework generality or CO2 application validity.
