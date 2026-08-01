# L1 data and provenance contract

Status: frozen design `L1-D1.0`

## 1. Required delivery tree

```text
L1_material_point_element/
  README.md
  L1_benchmark_spec.md
  L1_state_contract.md
  L1_case_matrix.csv
  L1_acceptance_gates.md
  L1_data_contract.md
  L1_implementation_execution_plan.md
  expected_results_template.json
  schemas/
    l1_call_ledger_columns.csv
    l1_run_summary.schema.json
  src/                         created only during implementation
  tests/                       created only during implementation
  results/                     created only after pre-execution freeze
    l1_run_summary.json
    l1_call_ledger.csv
    l1_case_results.csv
    l1_accepted_checkpoints.csv
    l1_manifest.json
    l1_result_report.md
```

The current design task creates no `src`, `tests` or `results` directory and makes no pass claim.

## 2. Canonical value representation

Every floating value used in equality or hashing must have two representations:

1. IEEE-754 hexadecimal text from `float.hex()` for authoritative same-implementation comparison;
2. decimal scientific notation for human inspection.

Canonical JSON uses UTF-8, sorted keys, compact separators and no timestamps. CSV uses UTF-8, a fixed column order and `\n` line endings. Dictionaries and candidate registries must be sorted by explicit identifiers before serialization.

## 3. Call ledger

`l1_call_ledger.csv` records every begin, evaluation, reject, accept, output, terminal and checkpoint event. The authoritative columns are defined in `schemas/l1_call_ledger_columns.csv`.

The ledger must make the following questions answerable without inspecting source code:

- Which accepted state version was read?
- Which candidate was created or invalidated?
- Did committed state change during a disposable call?
- Was hidden/persistent physical state present?
- Which state versions generated stress, residual and tangent?
- Did an output row come from an accepted state?
- Are the two replay packets actually identical?

## 4. Scenario result table

`l1_case_results.csv` has one row per case and implementation variant. Required fields:

```text
design_version, implementation_hash, case_id, sublevel, variant,
history_1, history_2, declared_packet_equal,
expected_classification, observed_classification,
delta_stress, delta_residual, delta_tangent,
committed_hash_equal, operator_hash_equal,
accepted_source_valid, checkpoint_equal,
finite, gate_failed, passed.
```

No row may be marked passed when `declared_packet_equal=false`; that comparison is invalid and must be rerun.

## 5. Accepted checkpoints

`l1_accepted_checkpoints.csv` records only explicit accept events:

```text
run_id, case_id, accepted_version, candidate_id,
epsilon_or_u, force, sigma, epsilon_p, kappa,
plastic_dissipation, committed_state_hash, source_call_index.
```

Trial, rejected, terminal and diagnostic states are forbidden in this file.

## 6. Run summary

`l1_run_summary.json` must validate against `schemas/l1_run_summary.schema.json`. It reports gate families separately:

```text
schema_provenance
lifecycle
seed_detection
analytical_reference
thermodynamic_sanity
output_checkpoint
reproducibility
performance_reporting
```

The overall L1 verdict is pass only when every hard family passes for both L1-MP and L1-E1. Performance remains reporting-only.

## 7. Manifest

`l1_manifest.json` must include:

- design version and execution identifier;
- Python and operating-system identity;
- single-thread declaration;
- SHA-256 of every source, test, specification, schema and expected-results file;
- SHA-256 of every result artifact;
- exact command lines;
- case count and scenario-variant count;
- no-Abaqus declaration and process scan result;
- production-project read-only verification result.

## 8. Evidence labels

Every result claim must use one of:

```text
OBSERVED_L1
ESTABLISHED_ANALYTICAL_REFERENCE
INFERRED
PROPOSED
OPEN
INVALID_COMPARISON
```

Design expectations remain `PROPOSED/OPEN` until execution. A seeded defect outcome is `OBSERVED_L1` only after the expected seed and both safe controls pass the predeclared matrix.

## 9. Prohibited substitutions

- Finite values do not substitute for lifecycle replay.
- A converged or zero-residual packet does not substitute for analytical accuracy.
- Analytical accuracy does not substitute for output provenance.
- One safe implementation does not substitute for both safe controls.
- L1 does not substitute for L2 global solve, L3-L4 physical references, L5 cross-host evidence or L6 application evidence.
