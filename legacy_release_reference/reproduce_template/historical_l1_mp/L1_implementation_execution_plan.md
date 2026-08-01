# L1 implementation and execution plan

Status: approved design sequence only; implementation and execution require a separate user instruction

## 1. Boundaries

- Work only in `${NCS_WORKSPACE}\benchmarks\L1_material_point_element`.
- Treat `${PRODUCTION_WORKSPACE_EXCLUDED}` as read-only.
- Do not import, copy or adapt production UEL source into L1.
- Do not run Abaqus, datacheck, Standard, restart or any production case.
- Do not create a Git commit unless separately requested.
- Do not mark L1 pass from design files or unit-test syntax alone.

## 2. Planned implementation modules

Use Python 3.12 standard library only for the first reference implementation.

```text
src/l1_state.py       immutable committed/candidate packets and canonical hashes
src/l1_material.py    pure 1D return mapping and analytical helper
src/l1_variants.py    safe_local, safe_transactional and isolated unsafe seeds
src/l1_element.py     one-point bar residual and tangent assembly
src/l1_cases.py       histories generated only from L1_case_matrix.csv
run_l1.py             gated runner and deterministic artifact writer
tests/test_oracle.py
tests/test_state_contract.py
tests/test_mp_cases.py
tests/test_e1_cases.py
tests/test_artifacts.py
```

No module-level mutable physical state is permitted except inside the deliberately named unsafe seed classes. Those classes must never be selected by default.

## 3. Stage I: static design validation

Before model code exists:

1. parse `L1_case_matrix.csv` and require 20 unique case IDs;
2. expand `variants_required` and require 45 scenario-variant outcomes;
3. validate `expected_results_template.json`;
4. validate the run-summary schema with one synthetic valid and one synthetic invalid document;
5. require every hard case to have an oracle and expected classification;
6. require all design files to have SHA-256 entries in a pre-execution manifest.

Failure stops before implementation.

## 4. Stage II: independent analytical oracle

Implement the reference calculations first with `fractions.Fraction` for frozen rational values and with a separate direct formula for the monotonic bar equilibrium. Unit tests must reproduce:

```text
delta_gamma = 1/55
sigma_plastic = 13/11
E_alg = 100/11
sigma_unsafe_replay = -289/242
Delta sigma = -205/121
u(F=1.1) = 21/1000.
```

The runtime evaluator must not call the oracle implementation. Shared code would remove independence.

## 5. Stage III: L1-MP implementation

Implement in this order:

1. immutable material data and committed-state records;
2. pure material evaluator returning a candidate;
3. explicit transactional candidate registry;
4. event ledger and canonical fingerprints;
5. `unsafe_trial_cache` seed;
6. `unsafe_output_feedback` seed;
7. MP reference and lifecycle cases.

Run the static/unit-test suite, then execute only the 12 MP cases. Run the complete MP matrix twice and compare output hashes.

### MP stop rules

Stop immediately if:

- an analytical value misses its envelope;
- any safe replay is nonzero;
- the primary unsafe replay does not equal `-205/121` within tolerance;
- a rejected call changes committed state;
- accepted version changes more than once;
- terminal/output provenance is invalid;
- any normal numeric output is nonfinite;
- duplicate complete runs differ.

Do not implement or execute E1 after an MP hard failure.

## 6. Stage IV: L1-E1 implementation

Only after MP passes:

1. implement the bar operator as a thin consumer of material return packets;
2. keep `u`, `F`, `C_n` and operator version explicit in every packet;
3. assemble `R=A*sigma-F` and `K=A*E_alg/L` without a global solve;
4. propagate candidate and accepted version IDs without reinterpretation;
5. implement output and checkpoint adapters as read-only consumers;
6. execute the eight E1 cases twice.

### E1 stop rules

Stop immediately if:

- analytical `R` or `K` fails;
- an equal declared replay differs for a safe variant;
- the seeded unsafe residual drift is not detected;
- residual and tangent state versions disagree without the seeded mismatch flag;
- trial output is emitted as accepted output;
- checkpoint restore changes the operator;
- duplicate complete runs differ.

## 7. Artifact freeze

After each successful sublevel:

1. write deterministic summary, case-result, ledger and checkpoint files;
2. generate a manifest with source/result SHA-256;
3. rerun the complete sublevel once;
4. require byte-stable deterministic artifacts;
5. write one result report separating `OBSERVED_L1` from `PROPOSED/OPEN`;
6. retain all seeded failures as source data.

Do not write frequent progress files.

## 8. Expected execution cost

The standalone scalar/reference workload is expected to complete in seconds to minutes on one CPU, but this is a planning estimate, not observed performance. Record actual wall time and peak memory without using them as hard gates.

## 9. Decision after execution

### Complete L1 pass

- update `G3` to `L0-L1 PASS; L2-L6 OPEN`;
- update Figure 2 only at the L1 row;
- prepare, but do not run, an L2 host-level forced-retry protocol.

### Any L1 failure

- preserve the complete ledger;
- classify the earliest failed gate;
- make the smallest correction in the standalone harness;
- rerun from the beginning of the failed sublevel;
- keep L1 and all later levels open.

## 10. Claims prohibited after L1

Even a complete L1 pass cannot support claims of:

- complete UEL rollback safety;
- Abaqus restart parity;
- global Newton robustness;
- mass conservation or spatial stability;
- two-phase poromechanics accuracy;
- cross-framework generality;
- correct CO2 plume, fault response or surface displacement;
- production performance improvement.
