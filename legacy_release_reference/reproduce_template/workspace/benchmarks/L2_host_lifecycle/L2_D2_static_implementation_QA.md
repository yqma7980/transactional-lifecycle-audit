# L2-D2.0a Static Implementation QA

## 1. Decision

**Status: `IMPLEMENTED_NOT_EXECUTED`.**

This is a static implementation acceptance record. It is not a benchmark
execution result. Neither `L2-CO-01` nor `L2-CO-02` was run, no test suite was
run, and no Abaqus process was started. Consequently, this work creates no
`OBSERVED-L2-D2` evidence and does not authorize a Claim Matrix, manuscript,
or figure update.

## 2. Files created

Exactly the six authorized files were created:

1. `src/l2_d2_callback_order.py`
2. `oracle/l2_d2_fraction_oracle.py`
3. `tests/test_l2_d2_callback_order.py`
4. `run_l2_d2.py`
5. `L2_D2_implementation_manifest.json`
6. `L2_D2_static_implementation_QA.md`

No existing L2-D0, L2-D1, L2-D2 freeze, governance, manuscript, claim, or
figure file was edited.

## 3. Frozen callback schedules

### 3.1 Direct history

| Ordinal | Event | Frozen state or operator |
|---:|---|---|
| 1 | `BeginAttempt` | `DIRECT_REPLAY` |
| 2 | `TrialEvaluate` | `u=1/200`, `F=1/2` |
| 3 | `FormResidual` | `L2-R-D1.0` |
| 4 | `FormTangent` | `L2-K-D1.0` |
| 5 | `RejectAttempt` | `DIRECT_REPLAY` |

### 3.2 Extra nonaccepting history

| Ordinal | Event | Frozen state or operator |
|---:|---|---|
| 1 | `BeginAttempt` | `EXTRA_CALLBACK_BATCH` |
| 2 | `TrialEvaluate` | `u=3/100`, `F=1/2` |
| 3 | `FormResidual` | `L2-R-D1.0` |
| 4 | `TrialEvaluate` | `u=-3/100`, `F=1/2` |
| 5 | `FormResidual` | `L2-R-D1.0` |
| 6 | `RejectAttempt` | `EXTRA_CALLBACK_BATCH` |
| 7 | `BeginAttempt` | `EXTRA_REPLAY` |
| 8 | `TrialEvaluate` | `u=1/200`, `F=1/2` |
| 9 | `FormResidual` | `L2-R-D1.0` |
| 10 | `FormTangent` | `L2-K-D1.0` |
| 11 | `RejectAttempt` | `EXTRA_REPLAY` |

The implementation rejects every frozen forbidden event: acceptance, accepted
output, checkpoint, restart, cutback/retry, and terminal or zero-increment
callbacks.

## 4. Single-evaluation contract

`TrialEvaluate` is the only callback that invokes the reused D1
`evaluate_element` operator. Its returned `ElementResult` is retained as the
active immutable observation. The following `FormResidual` and `FormTangent`
events read that same result and do not call the constitutive or element
operator again.

The frozen counts are therefore one trial evaluation in the direct history and
three in the extra history. Every `RejectAttempt` checks that the committed
fingerprint remains the authoritative D1 value:

`f5045dd74424efe25edaaebfa84802eeba5e8ca376816835f58145764a2efc01`

## 5. Safe and unsafe isolation

- `L2-CO-01` creates two independent fresh `safe_transactional` instances.
  Each trial reconstructs from immutable committed state, rejection removes the
  attempt registry, and rejected candidates cannot reach accepted output.
- `L2-CO-02` creates two independent fresh `unsafe_trial_cache` instances.
  Each hidden cache is seeded from the default committed state. Every trial
  evaluation deliberately replaces that hidden cache with the returned trial
  candidate, including evaluations in a rejected attempt. This is the sole
  intended negative-control mutation.
- Direct and extra histories never share a mutable variant or cache.
- Neither path contains an accepted-state callback.

## 6. Fingerprint contract

The `declared_replay_context_fingerprint` contains only:

- displacement `u`;
- load `F`;
- authoritative committed-state fingerprint;
- residual version; and
- tangent version.

The `observed_replay_fingerprint` adds:

- residual `float.hex()`;
- tangent `float.hex()`;
- physical candidate-state fingerprint; and
- post-rejection persistent-state fingerprint.

All fingerprints reuse D1 `canonical_json` and `canonical_hash`. Candidate
physical identity excludes algorithmic labels such as candidate ID, attempt ID,
and source call index; those labels remain separately auditable in the event
ledger.

The frozen expectation is exact declared-context equality for both cases,
exact observed equality for CO-01, and observed inequality with finite drift for
CO-02.

## 7. Independent Fraction oracle

The new oracle imports only `fractions.Fraction` and standard-library typing. It
does not import the callback implementation. An independent static recomputation
confirmed:

| Quantity | Exact value |
|---|---:|
| CO-01 delta residual | `0/1` |
| CO-01 delta tangent | `0/1` |
| Positive callback sigma | `13/11` |
| Negative callback delta gamma | `4/121` |
| Negative callback sigma | `-183/121` |
| Hidden epsilon_p | `-9/605` |
| Hidden kappa | `31/605` |
| Replay sigma | `4141/2662` |
| Replay candidate epsilon_p | `-281/26620` |
| Replay candidate kappa | `1479/26620` |
| CO-02 delta residual | `1405/1331` |
| CO-02 delta tangent | `-1000/11` |

These values were frozen before any case execution and must not be tuned to a
future runtime result.

## 8. Runner authorization and future output contract

`run_l2_d2.py` has an `if __name__ == "__main__"` guard and requires both:

1. command-line flag `--execute-authorized`; and
2. environment variable `L2_D2_EXECUTION_AUTHORIZED=YES`.

AST inspection confirms that both authorization checks occur before case
execution and before any output-directory creation. The runner accepts one case
ID and one run ID per process and does not loop over repetitions.

If separately authorized later, each case/run will create only:

- `callback_event_log.csv`
- `replay_comparison.csv`
- `case_result.json`
- `case_manifest.json`

None of these result files or a D2 execution directory exists at this stage.

## 9. Static QA results

| Check | Result |
|---|---|
| Core module AST parse | PASS |
| Fraction oracle AST parse | PASS |
| Test-definition AST parse | PASS |
| Runner AST parse | PASS |
| Freeze JSON parse | PASS |
| Implementation manifest JSON parse | PASS |
| Case matrix CSV parse and unique two-case identity | PASS |
| Runner main guard | PASS |
| CLI authorization lock before execution | PASS |
| Environment authorization lock before execution | PASS |
| Independent Fraction recomputation | PASS |
| `__pycache__` absent | PASS |
| D2 execution outputs absent | PASS |
| New SVG/PDF/TIFF/PNG absent | PASS |
| Abaqus process count | `0` |

No `unittest`, `pytest`, runner, `execute_callback_order_case`, or benchmark
entry point was invoked during these checks.

## 10. File hashes

| File | SHA-256 |
|---|---|
| `src/l2_d2_callback_order.py` | `c6f2e6a758b3ff24bcfe8e94a2bc7bf539f1a359dd1766acf19c2c98b45c6491` |
| `oracle/l2_d2_fraction_oracle.py` | `8eb6f5f20ff1d0ae2d55f8fdda4153db62560fa14934088159340046cbdf31fa` |
| `tests/test_l2_d2_callback_order.py` | `f178069da4660faa4ae94f04c68847a5c1907f483820ee974d1604edc30cab9a` |
| `run_l2_d2.py` | `9d002eba5774ffeecd45133966c92ad35d349e304fac8cc6e7459c2ba1460fd2` |
| `L2_D2_implementation_manifest.json` | `a4bbc46c4813afda8b538a2129139f8912152739a1caedbd9a590c9532c07e35` |

The QA Markdown hash is intentionally reported outside the implementation
manifest after this file is finalized.

## 11. Protected boundaries

The following precheck baselines remained protected throughout implementation:

- 37 D1 source, test, oracle, runner, freeze, and result files;
- aggregate D1 baseline:
  `9d4f5fc7bd6afce8c17812a18fa710b2dae57f42c30862bfcda8fcb7d4eab977`;
- 22 STATUS/roadmap/backlog, Claim Matrix, manuscript, and Figure 1-4 files;
- aggregate governance/writing/figure baseline:
  `107e07d84c46160fd3646d35e72c6caf43a482d33c4d2e2a0a95624e83a292a9`;
- L2-D2 freeze:
  `aeb7d4060b72e9f92fb039d460b08c119a67e406a311ccf431b4adcf4cb42d8f`;
- L2-D2 plan:
  `12b02c63bdb1305978843e530341d937f80c93855dea0b44be7ac22c9ce91140`;
- L2-D2 source manifest:
  `6bee7c645f0306b2e2387e68958e63e3a058c31f93a0c648c1182a113fa82a67`;
- L2-D2 case matrix:
  `62cdbb90454cea75f9ad6af9ede1d0b444cbdf28ed83abdf51a3658296c77ca5`.

The read-only production repository remained at zero tracked changes, zero
staged changes, and 53 pre-existing untracked entries. Its `git status --short`
fingerprint remained:

`4def4e7d6c4b5369caa9c0582324f6d2470861f5b07ce57b51e9fd08e18c6e7f`

No Git add, commit, clean, move, or delete operation was performed.

## 12. Evidence boundary and next gate

This implementation supports only the statement that the frozen L2-D2.0a
design has a statically accepted implementation. It does not establish safe
callback invariance or unsafe callback-history drift as an observed L2-D2
result. It supports no Abaqus, production-model, performance, conservation, or
coupled-physics conclusion. The other L2 cases and L3-L6 remain open.

The next gate requires separate authorization to execute:

- `L2-CO-01` in two independent single-process runs; and
- `L2-CO-02` in two independent single-process runs.

Execution must not begin automatically from this implementation task.
