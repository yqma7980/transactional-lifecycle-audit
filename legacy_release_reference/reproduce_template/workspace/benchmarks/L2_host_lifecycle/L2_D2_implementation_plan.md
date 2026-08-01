# L2-D2 Callback-Order Lifecycle Benchmark: Static Implementation Plan

**Design version:** L2-D2.0a  
**Host baseline:** L2-HOST-D1.0  
**Reserved extension name:** L2-HOST-D2.0  
**Status:** FROZEN_NOT_IMPLEMENTED  
**Execution authorized:** No  
**Abaqus used:** No  
**Results exist:** No

## Revision note

L2-D2.0a aligns the declared committed-state fingerprint with the only authoritative serializer for this reused host: `src.l2_state.canonical_json(CommittedState())`. The earlier static hash encoded the two history variables as rational strings; it was never executed and is not an L2-HOST-D1.0 fingerprint. This revision changes only serialization identity. It does not change the accepted state, equations, load, callback schedules, safe/unsafe semantics, tolerances, repetitions, or analytical oracle.

## 1. Purpose and claim boundary

L2-D2 is a standalone host-lifecycle benchmark for one narrow question: if extra, non-accepting trial callbacks are inserted before replaying the same declared state, does the callback history change the replayed residual, tangent, or state fingerprint?

The design covers only:

- `L2-CO-01`: `safe_transactional`, expected `PASS_CALLBACK_INVARIANCE`;
- `L2-CO-02`: `unsafe_trial_cache`, expected `DETECT_CALLBACK_HISTORY_DRIFT`.

The design does not test callback permutation. It tests callback-count insertion while keeping the physical equations, boundary load, committed state, replay state, residual version, and tangent version fixed.

No result in this document supports Abaqus, production-model, performance, conservation, coupled-physics, or application-validity claims. The remaining nine L2 cases, L3-L6, Abaqus, and the production model remain OPEN.

## 2. Reused D1 host contract

Any later implementation must reuse the L2-HOST-D1.0 one-element bar, exact rational oracle, accepted-state definition, and deterministic environment:

| Item | Frozen value |
|---|---|
| Material | `E=100`, `sigma_y=1`, `H=10` |
| Element | `A=1`, `L=1`, `u1=0` |
| Equilibrium | `R=A*sigma-F` |
| Tangent | `K=A*E_alg/L` |
| Accepted state | `epsilon_p=0`, `kappa=0`, `accepted_version=0` |
| Authoritative fingerprint serializer | `src.l2_state.canonical_json(CommittedState())` |
| Authoritative committed-state hash | `f5045dd74424efe25edaaebfa84802eeba5e8ca376816835f58145764a2efc01` |
| Replay primary state | `u=1/200` |
| Load for every callback | `F=1/2` |
| Residual version | `L2-R-D1.0` |
| Tangent version | `L2-K-D1.0` |
| Process/thread setting | one process, one thread |

If the D1 source requires an extension to expose callback histories, the implementation identity must be `L2-HOST-D2.0`. The constitutive equation, load, return mapping, accepted-state semantics, and oracle must not change.

## 3. Frozen callback histories

### 3.1 Direct history

| Order | Event | State or action | Acceptance effect |
|---:|---|---|---|
| 1 | `BeginAttempt` | `DIRECT_REPLAY` | none |
| 2 | `TrialEvaluate` | `u=1/200`, `F=1/2`, committed hash fixed | candidate only |
| 3 | `FormResidual` | `L2-R-D1.0` | none |
| 4 | `FormTangent` | `L2-K-D1.0` | none |
| 5 | `RejectAttempt` | discard candidate | committed state unchanged |

### 3.2 Extra non-accepting callback history

| Order | Event | State or action | Acceptance effect |
|---:|---|---|---|
| 1 | `BeginAttempt` | `EXTRA_CALLBACK_BATCH` | none |
| 2 | `TrialEvaluate` | `u=3/100`, `F=1/2`, same declared committed state | candidate only |
| 3 | `FormResidual` | `L2-R-D1.0` | none |
| 4 | `TrialEvaluate` | `u=-3/100`, `F=1/2`, same declared committed state | candidate only |
| 5 | `FormResidual` | `L2-R-D1.0` | none |
| 6 | `RejectAttempt` | discard inserted candidates | committed state unchanged |
| 7 | `BeginAttempt` | `EXTRA_REPLAY` | none |
| 8 | `TrialEvaluate` | `u=1/200`, `F=1/2`, same committed hash | candidate only |
| 9 | `FormResidual` | `L2-R-D1.0` | none |
| 10 | `FormTangent` | `L2-K-D1.0` | none |
| 11 | `RejectAttempt` | discard replay candidate | committed state unchanged |

Neither history may contain `AcceptIncrement`, output feedback, checkpoint, restart, cutback, terminal/zero-increment callbacks, or a different boundary load. No inserted candidate may be reachable from accepted output.

## 4. Case semantics

### 4.1 L2-CO-01: safe transactional

Every `TrialEvaluate` must reconstruct from the immutable accepted state. Candidate history is call-local and is discarded after a rejected attempt. The two inserted callbacks may form finite candidates, but they must not alter either the committed state or the later replay.

Required later classification: `PASS_CALLBACK_INVARIANCE` only if:

- replay residuals are exactly equal;
- replay tangents are exactly equal;
- replay state fingerprints are byte-identical under the frozen serializer;
- the committed-state hash is unchanged;
- no inserted callback is represented in accepted output.

Expected exact values are `Delta R=0` and `Delta K=0`.

### 4.2 L2-CO-02: unsafe trial cache

The negative control must start from the same explicit cache seed as the accepted state, then incorrectly overwrite that cache after every trial evaluation even though no attempt is accepted. The cache is intentionally outside the transactional committed-state channel.

The unsafe mutation rule is fixed before implementation:

```text
hidden_cache <- returned_trial_candidate
```

The direct history leaves the seed unchanged because its replay remains elastic. The extra history first evaluates `u=3/100`, then `u=-3/100`; these rejected candidates mutate the hidden cache before the common replay.

Required later classification: `DETECT_CALLBACK_HISTORY_DRIFT` only if:

- all values remain finite and below `1e100` in magnitude;
- the two declared replay contexts are identical;
- no accept event occurs;
- the measured drift matches the frozen rational oracle within `1e-12` absolute/relative tolerance;
- the residual drift magnitude is at least `1e-8`.

## 5. Exact analytical oracle

The seed is analytically discriminating before any code or case is run.

### 5.1 Safe path

The inserted positive and negative callbacks reconstruct from the same committed state. Their candidates are discarded. The common replay therefore remains elastic:

```text
R_direct = R_extra = 0
K_direct = K_extra = 100
Delta R = 0
Delta K = 0
```

### 5.2 Unsafe path

After `u=3/100`:

```text
epsilon_p(cache) = 1/55
kappa(cache)     = 1/55
sigma            = 13/11
```

After the rejected `u=-3/100` callback:

```text
delta_gamma      = 4/121
epsilon_p(cache) = -9/605
kappa(cache)     = 31/605
sigma            = -183/121
```

At the common replay `u=1/200`, `F=1/2`:

```text
sigma_trial      = 481/242
yield_excess     = 115/242
delta_gamma      = 23/5324
sigma            = 4141/2662
R_extra          = 1405/1331
K_extra          = 100/11
```

Against the direct replay:

```text
Delta R = 1405/1331 = 1.0555972952667168
Delta K = -1000/11 = -90.9090909090909
```

Both drifts are finite and nonzero. This proof is a design oracle, not an executed benchmark result.

## 6. Future implementation contract

Only after separate user authorization may an implementation:

1. Extend the D1 host under the reserved identity `L2-HOST-D2.0` without changing equations or loading.
2. Represent callbacks as explicit immutable packets containing event type, primary state, load, committed-state hash, residual version, and tangent version.
3. Serialize the replay fingerprint deterministically.
4. Implement safe and deliberately unsafe state ownership as separate variants.
5. Execute each case in two independent processes with one thread per process.
6. Compare every measured value with the exact rational oracle.

No future implementation may tune the unsafe seed after seeing execution output. A mismatch must be treated as an implementation or oracle discrepancy, not repaired by silently changing the frozen schedule.

## 7. Frozen tolerances and repetitions

| Gate | Value |
|---|---:|
| Analytical absolute tolerance | `1e-12` |
| Analytical relative tolerance | `1e-12` |
| Safe same-track equality | exact zero |
| Unsafe finite-drift floor | `1e-8` |
| Finite absolute limit | `1e100` |
| Formal independent repetitions | `2` |
| Processes per repetition | `1` |
| Threads per process | `1` |

## 8. Static acceptance checklist

- [x] CO-01 and CO-02 match the L2-D0 identifiers and classifications.
- [x] Both callback histories are fully frozen.
- [x] The common replay context is identical by construction.
- [x] The unsafe seed produces a finite nonzero analytical drift.
- [x] Tolerances and future repetitions are frozen.
- [x] No implementation or execution is authorized.
- [x] No Abaqus or production-model statement is made.
- [ ] Source implementation: NOT AUTHORIZED.
- [ ] Two-process execution: NOT AUTHORIZED.
- [ ] Result registration and manuscript synchronization: OPEN pending execution.

## 9. Stop boundary

This plan ends at static design. It must not create source, tests, runners, execution artifacts, or results; it must not run L2-D2, L2-D3, Abaqus, or any production calculation. The next action requires separate user authorization for L2-D2 implementation only.
