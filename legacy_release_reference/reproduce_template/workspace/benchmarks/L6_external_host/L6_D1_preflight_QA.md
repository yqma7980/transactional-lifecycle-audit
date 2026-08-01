# L6-D1 implementation and preflight QA

**Status:** PASS / IMPLEMENTED_PREFLIGHT_PASS_NOT_FORMALLY_EXECUTED  
**Date:** 2026-07-22

## Directed results

- AST parsing: PASS for all implementation, oracle, test and runner modules.
- Unit/directed tests: 8/8 PASS in one process and one thread.
- Formal result root before/after preflight: absent.
- Bytecode cache under L6: 0.
- Safe host path: genuine nonaccepted residual trials detected; oracle and transaction gates passed.
- Accepted-output path: one output after HostReturn and Commit; rejected candidates unreachable.
- Callback-order path: analytic and SciPy 2-point paths met the frozen accepted-field/cost parity gates while residual-call histories differed.
- Unsafe control: a nonaccepted host residual mutated rollback-external state and produced finite drift above the frozen floor.
- Version mismatch: finite packets were rejected before the Jacobian reached SciPy, with no callback, commit or output.

## Pre-execution corrections

Two dated implementation-only errata are preserved. The first bypasses unrelated legacy L2 package initialization while loading the exact hash-protected serializer file. The second recognizes SciPy's repeated callback of an unchanged accepted state after a fully rejected trial batch. Neither correction changes the model, unsafe seed, host options, thresholds or case matrix.

## Implementation hashes

| File | SHA-256 | Bytes |
|---|---|---:|
| `benchmarks/L6_external_host/src/__init__.py` | `bd7af87c76d6f50e38833a7bb3b260dd1b123fd756ce3b867cc3e106f32d4e47` | 60 |
| `benchmarks/L6_external_host/src/l6_state.py` | `c9f00d95198a8a99ec4dac073dc3cab7cbebd1360bd2833a86fb213b861d8885` | 4309 |
| `benchmarks/L6_external_host/src/l6_scipy_adapter.py` | `c3cfb96ff618c019bb577b631b8b618abb76ece983f8252325ffa6aa7f599055` | 18459 |
| `benchmarks/L6_external_host/src/l6_cases.py` | `5c423b3f59ccae6a158eb23d2020b964d90d9ab449b99d05e004b52d92f5a1c9` | 20621 |
| `benchmarks/L6_external_host/oracle/__init__.py` | `1ed38fd3860fa0c7564b30b615258695d918b0b0ea7a302396a6c1fe8a755652` | 46 |
| `benchmarks/L6_external_host/oracle/l6_stationary_oracle.py` | `f36312c402d45512ef9458070bdfeb072f8ef518b0a5731feeeffe1ff9f70505` | 796 |
| `benchmarks/L6_external_host/tests/__init__.py` | `1a02b1867459aeee7d380f44b391d2040ad87a4a5622a6094d87084c17ac8b54` | 33 |
| `benchmarks/L6_external_host/tests/test_l6_d1.py` | `5f09f99313278e6e2263b11cb91e2cf7d229ca2c55f8618311bbe89c163a6b7b` | 4329 |
| `benchmarks/L6_external_host/run_l6_d1.py` | `5a09e15c83ebab3c9dd15cfe1aa8d19f75db3db36532ac8680cc5c5d532d03c7` | 5765 |

Implementation manifest SHA-256: `a577edd27d84f554f8d989667405dee5a606b05352d0edce15920abde4daa933`.

## Boundary

No formal L6 result exists yet, so no `OBSERVED-EXTERNAL-HOST` claim is authorized. The active long goal authorizes formal execution only in frozen case order, two independent single-process/single-thread runs per case, with immediate stop at the first failed prerequisite.
