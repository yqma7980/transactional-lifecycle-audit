# L2-D3 Tangent-Path Benchmark: Static Implementation Plan

**Design version:** L2-D3.0  
**Host baseline:** L2-HOST-D1.0  
**Reserved extension name:** L2-HOST-D3.0  
**Status:** FROZEN_NOT_IMPLEMENTED  
**Execution authorized:** No  
**Abaqus used:** No  
**Results exist:** No

## 1. Purpose and claim boundary

L2-D3 freezes three standalone host tests that separate accepted-field parity, iteration-path parity, and residual-tangent version compatibility:

- L2-TG-01 repeats the exact-current tangent path from two fresh hosts.
- L2-TG-02 compares exact-current and explicitly declared one-iteration lagged tangents while keeping the residual definition, load and accepted target fixed.
- L2-TG-03 rejects a seeded, undeclared residual-tangent state-version mismatch before any correction or interpretation.

This design does not test Abaqus, the production UEL, coupled-physics convergence, conservation, performance, CO2 transport, fault behavior or field-scale production readiness. Analytical values below are frozen expectations, not executed evidence.

## 2. Reused host and model

Any later implementation must reuse L2-HOST-D1.0 without changing its constitutive equations:

| Item | Frozen value |
|---|---|
| Material | E=100, sigma_y=1, H=10 |
| Element | A=1, L=1, u1=0 |
| Equilibrium | R=A*sigma-F |
| Exact current tangent | K_current=A*E_alg/L |
| Newton correction | delta_u=-R/K_used |
| Initial committed state | epsilon_p=0, kappa=0, accepted_version=0 |
| Authoritative committed hash | f5045dd74424efe25edaaebfa84802eeba5e8ca376816835f58145764a2efc01 |
| Equilibrium target | F=11/10 from u=0 |
| Accepted target | u=21/1000, sigma=11/10, epsilon_p=kappa=1/100 |
| Process/thread setting | one process, one thread |

If a source extension is later authorized, it must use L2-HOST-D3.0. It may expose tangent histories and version checks, but it must not duplicate or alter the D1 material law, element equation, state serializer or acceptance semantics.

## 3. Frozen tangent contracts

### 3.1 Exact-current tangent

The residual and tangent are evaluated at the same current trial state:

    R_k = R(u_k; C_n)
    K_used,k = K_current(u_k; C_n)

This is the MATCHED_SAME_STATE contract.

### 3.2 Declared one-iteration lagged tangent

The residual remains current, but the tangent is explicitly taken from the preceding iteration:

    R_k = R(u_k; C_n)
    K_used,1 = K_current(u_accepted; C_n) = 100
    K_used,k = K_current(u_(k-1); C_n), k > 1

This is an explicitly declared inexact-Newton path, not a same-iteration consistent tangent. Its iteration count may differ from the exact path. The acceptance gate compares accepted primary/history fields separately from iteration count.

### 3.3 Undeclared version mismatch

For TG-03, the matched control uses the same trial-state version for residual and tangent. The seeded negative control attaches the same finite numeric tangent to a different, undeclared state-version identifier. The host must reject the packet before Newton correction, state commit, accepted output, or lifecycle/physical interpretation.

## 4. Frozen analytical paths

### 4.1 Exact path used by TG-01 and TG-02

| Eval | u | R | K_used | Correction | Next/action |
|---:|---:|---:|---:|---:|---|
| 1 | 0 | -11/10 | 100 | 11/1000 | u=11/1000 |
| 2 | 11/1000 | -1/11 | 100/11 | 1/100 | u=21/1000 |
| 3 | 21/1000 | 0 | 100/11 | none | accept |

TG-01 repeats this semantic ledger on two fresh hosts. Required expectation: exact equality of every residual, tangent, correction and accepted-state fingerprint.

### 4.2 Declared lagged path used by TG-02

| Eval | u | R | K_current | K_used | Correction | Next/action |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 0 | -11/10 | 100 | 100 | 11/1000 | u=11/1000 |
| 2 | 11/1000 | -1/11 | 100/11 | 100 | 1/1100 | u=131/11000 |
| 3 | 131/11000 | -10/121 | 100/11 | 100/11 | 1/110 | u=21/1000 |
| 4 | 21/1000 | 0 | 100/11 | 100/11 | none | accept |

The expected evaluation counts are 3 for exact and 4 for lagged. This difference is recorded, not failed. Both paths must accept exactly the same u, stress, plastic strain, hardening variable and force.

### 4.3 Version packet used by TG-03

At u=3/100, F=1/2, from the default committed state:

    sigma       = 13/11
    epsilon_p   = 1/55
    kappa       = 1/55
    R           = 15/22
    K           = 100/11

The matched control labels both operators trial:TG03:1. The negative control labels the residual trial:TG03:1 and the tangent trial:TG03:seeded_other, with no declared relation. Numeric values remain finite and unchanged; only the incompatible metadata contract causes rejection.

## 5. Per-case gates

### L2-TG-01

Expected classification: PASS_SAME_TRACK_REPEATABILITY.

- Both tracks start from fresh hosts and the same committed fingerprint.
- Residual and tangent ledgers match exactly.
- Accepted state and its fingerprint match exactly.
- Evaluation counts both equal 3.
- No hidden state is shared between tracks.

### L2-TG-02

Expected classification: PASS_DECLARED_LAGGED_TANGENT_PARITY.

- Residual definition and boundary load are identical.
- The lag relation is declared before execution.
- Accepted u, sigma, epsilon_p, kappa and force agree within the frozen analytical tolerance.
- Iteration counts are reported independently and are expected to differ.
- The result must not be described as proof that the lagged tangent is exact or faster.

### L2-TG-03

Expected classification: REJECT_VERSION_MISMATCH_BEFORE_LIFECYCLE_VERDICT.

- The matched control passes the version gate.
- All seeded mismatch values remain finite.
- The undeclared mismatch is rejected before any Newton correction.
- Committed state and accepted output remain unchanged or unreachable.
- No lifecycle, physics, convergence or production verdict is drawn from the rejected packet.

## 6. Frozen tolerances and repetitions

| Gate | Value |
|---|---:|
| Analytical absolute tolerance | 1e-12 |
| Analytical relative tolerance | 1e-12 |
| Exact same-track equality | exact zero |
| Accepted-field parity | 1e-12 absolute and relative |
| Version compatibility | exact identifier contract |
| Finite absolute limit | 1e100 |
| Formal independent repetitions | 2 |
| Processes per repetition | 1 |
| Threads per process | 1 |

## 7. Future implementation contract

Only after separate authorization may the following files be created:

    src/l2_d3_tangent_path.py
    oracle/l2_d3_fraction_oracle.py
    tests/test_l2_d3_tangent_path.py
    run_l2_d3.py
    L2_D3_implementation_manifest.json
    L2_D3_static_implementation_QA.md

The future implementation should expose immutable evaluation packets containing primary state, committed-state fingerprint, residual-state version, tangent-state version, current tangent, used tangent, residual, correction, candidate state and acceptance decision. Module import must be side-effect free. A future runner must default to refusal and require explicit command-line and environment authorization before creating output directories.

No implementation may change the frozen force, displacement sequence, lag rule, version identifiers, tolerances or expected classifications after observing results.

## 8. Future output contract

If separately implemented and executed, each case/run should emit:

    tangent_event_log.csv
    path_comparison.csv
    case_result.json
    case_manifest.json

The result must keep accepted-field parity, iteration-count parity and version-compatibility verdicts as separate fields. TG-03 must record that rejection occurred before correction and that the candidate was unreachable from accepted output.

## 9. Static acceptance checklist

- [x] TG-01/02/03 match the L2-D0 identifiers and classifications.
- [x] Exact and declared-lagged paths are analytically discriminating.
- [x] TG-02 accepted-field and iteration-count gates are separate.
- [x] TG-03 uses finite equal-valued operators and an explicit metadata mismatch.
- [x] Tolerances and future repetitions are frozen.
- [x] No implementation, test or execution is authorized.
- [x] No Abaqus or production claim is made.
- [ ] Source implementation: NOT AUTHORIZED.
- [ ] Formal execution: NOT AUTHORIZED.
- [ ] Evidence registration and manuscript synchronization: OPEN pending execution.

## 10. Stop boundary

This plan ends at static design. It must not create source, tests, runners or results and must not run L2-D3, any other benchmark, Abaqus or a production calculation. The next action requires separate user authorization for L2-D3 implementation only; implementation must still end before execution.
