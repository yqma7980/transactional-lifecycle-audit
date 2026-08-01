# L2-D4 Static Implementation QA

**Design version:** L2-D4.0  
**Host version:** L2-HOST-D4.0  
**Implementation status:** IMPLEMENTED_NOT_EXECUTED  
**QA date:** 2026-07-22  
**Abaqus used:** No  
**Formal results exist:** No

## 1. Scope

This report records static implementation acceptance only. It is not an
`L2-OP-01` or `L2-OP-02` execution result and does not create
`OBSERVED-L2-D4` evidence. No benchmark case, test suite, runner, Abaqus job,
production UEL or long-window simulation was executed.

The implementation adds:

- a side-effect-free output-provenance core;
- an independent exact-rational oracle;
- unexecuted unit-test definitions;
- a one-case runner protected by two execution locks;
- this QA report and an implementation manifest.

The four frozen D4 design files were not modified.

## 2. Implemented contracts

### 2.1 L2-OP-01 safe accepted-output provenance

The safe path reuses the D1 `SafeTransactional` variant. One
`TrialEvaluate(u=3/100,F=1/2)` creates a finite, registered but unaccepted
candidate. `FormResidual` and `FormTangent` reuse that same `ElementResult`.
While the candidate is live, `OutputRead` constructs its physical snapshot
directly from the immutable host committed state; it does not call material or
element evaluation and does not change committed state, the transaction
registry or candidate reachability.

The frozen authoritative output is:

```text
accepted_version = 0
epsilon_p = 0
kappa = 0
source_version = accepted:0
source_candidate_id = NA
source_committed_state_hash = f5045dd74424efe25edaaebfa84802eeba5e8ca376816835f58145764a2efc01
output fingerprint = 83434ef7b7f520d2f3f4904122ee77895e46533fec0a2f513d0328092863147b
```

No formal safe-case observation exists yet.

### 2.2 L2-OP-02 isolated unsafe output-feedback control

The unsafe variant is isolated in the D4 module and is not added to the D1
variant registry. Its only deliberate violation is the frozen one: an output
read evaluates a trial packet, writes the trial-derived history to a persistent
mirror, and a later physical evaluation reads that mirror. Each history uses a
fresh variant, and committed state remains a separate immutable authority.

The implementation keeps two fingerprints distinct:

- the declared replay fingerprint contains only displacement, load,
  committed-state identity, accepted version, residual/tangent definitions and
  intended accepted source;
- the observed replay fingerprint adds the actual mirror source, operator
  values, candidate physical-state fingerprint and persistent mirror hash.

This separation prevents a path-specific callback label or candidate ID from
creating a false physical drift signal.

## 3. Frozen callback mapping

| Case/history | Frozen event order | Implementation mapping |
|---|---|---|
| OP-01 trial_then_output | BeginAttempt, TrialEvaluate, FormResidual, FormTangent, OutputRead, RejectAttempt | One D1 element evaluation; operator forms reuse it; committed-only output; rejection invalidates candidate |
| OP-01 accepted_output_only | OutputRead | Fresh safe host; committed-only read; zero material evaluations |
| OP-02 insert_output_read | OutputRead, BeginAttempt, TrialEvaluate, FormResidual, FormTangent, RejectAttempt | Deliberate mirror seed; one replay evaluation; operator forms reuse it; no accept |
| OP-02 direct_path | BeginAttempt, TrialEvaluate, FormResidual, FormTangent, RejectAttempt | Fresh unsafe control with mirror equal to committed state; one replay evaluation; no accept |

Forbidden accept, checkpoint, restart, cutback and terminal/zero-increment events
are absent from the D4 implementation schedules.

## 4. Independent exact oracle

An independent temporary `fractions.Fraction` calculation, performed without
importing the workspace implementation, reproduced:

```text
output seed epsilon_p = 1/55
output seed kappa = 1/55
feedback replay sigma = -289/242
feedback replay candidate epsilon_p = 41/2420
feedback replay candidate kappa = 47/2420
Delta sigma = -205/121
Delta R = -205/121
Delta K = -1000/11
```

The independent oracle module encodes the same derivation but was not imported
or executed in this implementation-only task.

## 5. Static checks

| Check | Result |
|---|---|
| Four Python files parsed with `ast.parse` | PASS |
| Four Python files compiled from source strings without import | PASS |
| Core top-level executable-expression scan | PASS; none found |
| Frozen design and case-matrix hashes | PASS |
| OP-01/02 IDs and expected classifications | PASS |
| Exact frozen callback schedules present | PASS |
| D1 canonical committed-state and accepted-output hashes encoded | PASS |
| `FormResidual`/`FormTangent` reuse contract | PASS |
| Independent Fraction discrimination | PASS |
| Runner `if __name__ == "__main__"` guard | PASS |
| CLI lock `--execute-authorized` | PASS |
| Environment lock `L2_D4_EXECUTION_AUTHORIZED=YES` | PASS |
| Both locks precede case execution and output write in `main` | PASS |
| D4 result root exists | NO |
| D4 test or runner executed | NO |
| `__pycache__` under L2 host lifecycle | 0 |
| Exact-name Abaqus solver/process count | 0 |

The future runner writes only after both locks pass, executes one case and one
run ID per process, and reserves:

```text
results/L2_D4_output_provenance/<case_id>/<run_id>/
```

No such directory was created in this task.

## 6. File identities

| File | SHA-256 | Bytes |
|---|---|---:|
| `src/l2_d4_output_provenance.py` | `1ae8f8802600b521980f0335c16a216ce1943a5bd9ca87bbc05db67cd2e83129` | 48,319 |
| `oracle/l2_d4_fraction_oracle.py` | `2c7e9c913b802ad682390ffb211dbd51ef6d656507f6965c27bb79f7482be591` | 3,748 |
| `tests/test_l2_d4_output_provenance.py` | `33996e508dff68d3a5c1f957fb96f73aa4199f4617e8f0eb4bc74e1256ece184` | 8,606 |
| `run_l2_d4.py` | `58374aea56cc44163f71d6eea53d3a203fa7227c9a86ea4fc9102a2910751949` | 4,934 |
| `L2_D4_implementation_manifest.json` | `0258d4bfa13f8503bc3f85dd8fee1ee120ecfc2a70e6562f5903c4f5106e8197` | 5,109 |

This QA file's hash is intentionally reported externally after creation.

## 7. Protected-state verification

- The 133 pre-existing L2 files retain aggregate SHA-256
  `d7ace686772acbe69a068ba0c9a7d8e6c9847114888a05bd7c47fc7c934d8547`.
- Claim Matrix v0.6 remains
  `1cb4d6d27de6678ae6336f8402b05305273702b5a1f05c7452de2bbcb0569ab9`.
- Manuscript v0.6 remains
  `47779ce51c2ca14a05e55abe3b558ae45162b210aa053f12add52804e6cafd5d`.
- The 24 Figure files retain aggregate SHA-256
  `f9ae3d860b85b49f03615ec4fc0f68348fac7cab1f195fdee4aae22448319179`.
- Production Git remains tracked=0, staged=0, with 53 `status --short`
  entries and status fingerprint
  `4def4e7d6c4b5369caa9c0582324f6d2470861f5b07ce57b51e9fd08e18c6e7f`.
- No Git add, commit, clean, move or delete operation was performed.

The three governance files were minimally updated only after static QA:

```text
STATUS.md = 5f83fb08eb2e4e11c81f58115f9736bfb792399063835d00ff945bd3b400f4bb
07_global_roadmap.md = a10d815a86b149c93a7ee01b340c6be8c65b77466c1f435c3b35e366b63660d6
08_execution_backlog.md = b776159efbf8e8e956164be80046b30184f1356665d2c672aac60944b9852b4f
```

## 8. Evidence boundary and next authorization

The valid observed range remains **10/14 L2 cases**. `L2-OP-01` and
`L2-OP-02` remain OPEN. This implementation supplies no `OBSERVED-L2-D4`,
Abaqus, production, checkpoint/restart, performance, conservation,
coupled-physics or application evidence. Claim Matrix v0.6, manuscript v0.6
and Figures 1-6 were not updated.

The next step requires a separate user authorization for formal execution:

```text
L2-OP-01: run_1 and run_2, independent one-process/one-thread runs
L2-OP-02: run_1 and run_2, independent one-process/one-thread runs
```

Until that authorization is provided, the accurate state is
`IMPLEMENTED_NOT_EXECUTED`.
