# L6-D1 static freeze QA

**Status:** PASS / FROZEN_NOT_IMPLEMENTED  
**Date:** 2026-07-22

## Static gates

- Host capability is genuine and local: SciPy 1.17.1 TRF produced 10 nonaccepted residual evaluations and 8 accepted callbacks in the capability probe.
- The capability probe is explicitly not formal L6 evidence.
- Five unique cases are frozen: safe retry, output provenance, callback-order parity, unsafe persistent-cache negative control and pre-correction version rejection.
- The model, unsafe update, host settings, tolerances, process/thread count and case order are frozen before implementation.
- Freeze JSON and source manifest parse successfully.
- Case matrix contains 5 unique IDs.
- No `src`, `tests`, `oracle`, runner or `results` directory exists under `benchmarks/L6_external_host`.
- No L6 formal case, unit test, Abaqus or COMSOL job has run.
- Claim Matrix v2.0, manuscript v2.0 and L5-D2 raw evidence remain protected.

## Design-output hashes

| File | SHA-256 | Bytes |
|---|---|---:|
| `benchmarks/L6_external_host/L6_D0_host_capability_probe.json` | `ddf823a5af637cebe970ed4047ac366f4000af4dd6092fd91dcb5877d5cfc5bf` | 1959 |
| `benchmarks/L6_external_host/L6_D0_host_capability_audit.md` | `197c4f3602d3f80794de135766d97d6ea90276716b49ed8f3d9aaf6e7f96739a` | 1428 |
| `benchmarks/L6_external_host/L6_D1_benchmark_spec.md` | `47f365ba91145ad070ec738847d9cd70a7d703acee83faa278e6a336ee0476a2` | 3117 |
| `benchmarks/L6_external_host/L6_D1_host_transaction_contract.md` | `ddfaaa0b5d7110a51e8d5ad84ca1389ae378d9449281068a42354f7c7a740ded` | 2173 |
| `benchmarks/L6_external_host/L6_D1_case_matrix.csv` | `c073d796d661ef1113577f3d625c65106328a48fc83f28eb936b5f58671eee81` | 722 |
| `benchmarks/L6_external_host/L6_D1_acceptance_gates.md` | `8f394d37bf3e2e13e5e6029c57bbbfb39b2a566ac557bdcd54dd6295502e74d1` | 2880 |
| `benchmarks/L6_external_host/L6_D1_execution_freeze.json` | `7180148893dc8e17ab6d3b882939f7782c9c59622b798a248dd09adca7e7c469` | 2469 |
| `benchmarks/L6_external_host/L6_D1_implementation_plan.md` | `49742334f2fc0cc0a793733e9303236738edd5f6333f154b848fadf62109ddd1` | 1623 |

Source manifest SHA-256: `f0c7ff2e86cc66a52e79506c31090e7aac4f102143dec4143a87f3c8784a0423`.

## Evidence boundary

The frozen design can support only a future `OBSERVED-EXTERNAL-HOST` claim. It cannot be upgraded to `OBSERVED-ABAQUS`, production readiness, performance, thread safety, two-way coupling or CO2 application validity.

## Next gate

Implement L6-D1 without changing the frozen host, model, unsafe mechanism, tolerances or matrix. Preflight must stop before formal results if any directed host-lifecycle gate fails.
