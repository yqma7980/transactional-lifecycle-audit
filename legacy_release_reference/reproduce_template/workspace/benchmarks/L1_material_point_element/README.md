# L1 material-point and one-element lifecycle benchmark

Status: **L1-MP AND L1-E1 PASS / L2-L6 OPEN**  
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

## Observed L1 result

- all 12 L1-MP cases, eight L1-E1 cases, and 45 scenario-variant outcomes passed;
- safe local and transactional controls produced no replay false positives;
- seeded trial-cache, output-feedback, and version-mismatch controls were detected;
- the primary seed reproduced `Delta stress = Delta R = -205/121` within `1e-12`;
- the combined 40-column ledger contains 345 rows and the accepted-state table contains 11 rows;
- six deterministic MP artifacts and six deterministic E1 artifacts were byte identical across their duplicate executions;
- 33 unit, schema, lifecycle, oracle, element, and artifact tests passed;
- no Abaqus process, production UEL, or production model was used.

`MP-LC-02` and `E1-LC-02` each received a documented pre-execution seed erratum. Their original monotonic permutations reached the same hidden state, so each formal matrix uses the same `+0.03/-0.03` discarded packets in opposite order. Equations, tolerances, common replay packets, and expected classifications were unchanged.

## What remains open

L2-L6, host integration, global forced-retry behavior, conservation, coupled-flow benchmarks, physical accuracy, performance, and application results remain open. A complete L1 pass does not imply Abaqus rollback safety or a valid CO2 simulation.

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
L1_E1_execution_freeze.json           authorized E1 packets and seed erratum
src/                                  standalone MP and E1 implementation
tests/                                independent oracle and lifecycle tests
run_l1_mp.py                          one complete MP execution
finalize_l1_mp.py                     duplicate-run hard gate and finalizer
run_l1_e1.py                          one complete E1 execution
finalize_l1_e1.py                     full-L1 duplicate-run finalizer
results/                              final evidence, summaries and hashes
schemas/l1_run_summary.schema.json    machine-readable summary schema
```

## Claim boundary

The observed pass applies only to the standalone L1-MP and L1-E1 harnesses. It shows that this single-threaded reference detects its seeded material/element lifecycle defects without flagging its safe controls. It does not establish Abaqus safety, restart parity, global Newton robustness, conservation, poromechanics accuracy, two-phase-flow validity, cross-framework generality, production performance, or CO2 application validity.
