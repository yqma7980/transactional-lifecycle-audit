# L2-D4 Output-Provenance Benchmark: Static Implementation Plan

**Design version:** L2-D4.0  
**Host baseline:** L2-HOST-D1.0  
**Reserved extension name:** L2-HOST-D4.0  
**Status:** FROZEN_NOT_IMPLEMENTED  
**Execution authorized:** No  
**Abaqus used:** No  
**Results exist:** No

## 1. Purpose and claim boundary

L2-D4 freezes two standalone host tests that separate accepted-output provenance from output-to-physics feedback:

- `L2-OP-01` asks for physical output while a finite, unaccepted plastic candidate exists. The output must still be an exact snapshot of the authoritative accepted state.
- `L2-OP-02` is a deliberately unsafe negative control. An inserted output read overwrites a persistent mirror, and the next physical evaluation incorrectly reads that mirror as history. The resulting finite operator drift must be detected.

This design does not test Abaqus output callbacks, the production UEL, restart, checkpoint round trips, coupled physics, conservation, performance, CO2 migration, fault behavior, displacement, or field-scale production readiness. Its numerical values are frozen analytical expectations, not executed L2-D4 evidence.

## 2. Reused host and model

Any later implementation must reuse L2-HOST-D1.0 without changing its constitutive equations or serializer:

| Item | Frozen value |
|---|---|
| Material | E=100, sigma_y=1, H=10 |
| Element | A=1, L=1, u1=0 |
| Residual | R=A sigma-F |
| Tangent | K=A E_alg/L |
| Initial committed state | epsilon_p=0, kappa=0, accepted_version=0 |
| Authoritative committed hash | f5045dd74424efe25edaaebfa84802eeba5e8ca376816835f58145764a2efc01 |
| Process/thread setting | one process, one thread |

If implementation is later authorized, the extension name is L2-HOST-D4.0. It may add immutable output packets, an output event ledger, provenance validation, and an isolated unsafe-output-feedback variant. It must not modify D1 material evaluation, element assembly, committed-state serialization, candidate acceptance, or rejection semantics.

## 3. Output ownership contract

The physical source of an accepted output row is the host-managed committed state only. A valid output snapshot contains:

```text
accepted_version
epsilon_p
kappa
source_version = accepted:<accepted_version>
source_candidate_id = NA
source_committed_state_hash
```

`OutputRead` is read-only. In a safe variant it must not call material or element evaluation, mutate committed state, mutate a persistent physical cache, accept a candidate, or change candidate reachability. Trial operators and candidates may appear in the diagnostic event ledger, but they cannot be labeled as accepted physical output.

The output layer is not a second state authority. An output mirror, terminal mirror, or diagnostic cache must not be read by residual or tangent formation in a safe path.

## 4. L2-OP-01: accepted-output provenance

### 4.1 Trial-then-output history

1. `BeginAttempt(TRIAL_PRESENT)`.
2. `TrialEvaluate(u=3/100,F=1/2)` forms `trial_candidate`.
3. `FormResidual` and `FormTangent` read the same evaluation packet.
4. `OutputRead(physical_accepted_state)` occurs while the trial candidate is still registered and unaccepted.
5. `RejectAttempt(TRIAL_PRESENT)` invalidates the candidate.

From the initial committed state, the trial packet is finite:

```text
sigma = 13/11
R = 15/22
K = 100/11
candidate epsilon_p = candidate kappa = 1/55
```

Those values are diagnostic trial evidence only. The output must instead be the accepted version-zero payload with `epsilon_p=kappa=0`, `source_version=accepted:0`, and `source_candidate_id=NA`.

### 4.2 Accepted-output-only history

A fresh host performs only `OutputRead(physical_accepted_state)` from the same initial committed state. Its snapshot must be byte-for-byte equivalent under the D1 canonical serializer to the snapshot from the trial-then-output history.

The frozen accepted output payload hash is:

```text
83434ef7b7f520d2f3f4904122ee77895e46533fec0a2f513d0328092863147b
```

Expected classification: `PASS_ACCEPTED_OUTPUT_PROVENANCE`.

This case does not claim that trial diagnostic rows are forbidden. It requires that they are explicitly non-accepted and never substituted for accepted physical output.

## 5. L2-OP-02: unsafe output-feedback negative control

The unsafe variant starts with a persistent output mirror equal to the declared committed state. It is deliberately incorrect and must remain isolated from the safe path.

### 5.1 Insert-output-read history

1. `OutputRead(trigger_u=3/100)` incorrectly evaluates a trial state and writes `epsilon_p=kappa=1/55` into the output mirror.
2. The resulting row has `source_version=trial_hidden`, a non-NA candidate ID, and `output_accepted_flag=false`.
3. A replay attempt evaluates `u=1/200,F=1/2`, but incorrectly reads the output mirror as physical history.
4. The replay operator is recorded and the attempt is rejected without changing committed state.

### 5.2 Direct history

A fresh unsafe variant skips the inserted output read. Its mirror is still equal to committed state when the same declared replay packet `u=1/200,F=1/2` is evaluated.

### 5.3 Exact analytical discrimination

| Quantity | Insert-output-read | Direct | Delta (insert-direct) |
|---|---:|---:|---:|
| sigma | -289/242 | 1/2 | -205/121 |
| residual | -205/121 | 0 | -205/121 |
| tangent | 100/11 | 100 | -1000/11 |
| replay candidate epsilon_p | 41/2420 | 0 | 41/2420 |
| replay candidate kappa | 47/2420 | 0 | 47/2420 |

The declared replay fingerprints must be identical because displacement, force, committed-state hash, accepted version, residual definition, tangent definition, and intended physical source are identical. The observed operator fingerprints must differ because the negative control has read an undeclared mirror.

Expected classification: `DETECT_OUTPUT_FEEDBACK_DRIFT`.

The negative control must not be described as a candidate implementation, a measured Abaqus error, or evidence that every output routine feeds back into physics.

## 6. Separate provenance and noninterference gates

The two cases answer different questions:

| Gate | Question | Required evidence |
|---|---|---|
| Accepted-source gate | Did a physical output row come from accepted state? | exact version, committed hash, no candidate ID |
| Read-only gate | Did output leave physical and persistent state unchanged? | before/after fingerprints |
| Candidate-isolation gate | Did an unaccepted candidate reach physical output? | source candidate ID and reachability |
| Feedback gate | Did output state alter a later operator? | equal declared replay plus finite nonzero Delta R and Delta K |

A finite row is insufficient. A row can be numerically finite and still fail provenance or noninterference.

## 7. Frozen tolerances and repetitions

| Gate | Value |
|---|---:|
| Analytical absolute tolerance | 1e-12 |
| Analytical relative tolerance | 1e-12 |
| Safe output snapshot equality | exact zero |
| Safe committed-state equality | exact zero |
| Unsafe finite-drift floor | 1e-8 |
| Finite absolute limit | 1e100 |
| Formal independent repetitions | 2 |
| Processes per repetition | 1 |
| Threads per process | 1 |

## 8. Future implementation contract

Only after separate authorization may D4 implementation files be created. Suggested names are:

```text
src/l2_d4_output_provenance.py
oracle/l2_d4_fraction_oracle.py
tests/test_l2_d4_output_provenance.py
run_l2_d4.py
L2_D4_implementation_manifest.json
L2_D4_static_implementation_QA.md
```

The implementation should define immutable output snapshots, output events, replay observations, and case results. `TrialEvaluate` must be performed once per declared packet; `FormResidual` and `FormTangent` must reuse the same result. Module import must be side-effect free.

Any runner must default to refusal and require both a command-line authorization flag and an environment authorization token before it creates an output directory. One process may run only one case and one run ID.

The unsafe variant may differ from the safe variant only by the frozen output-mirror mutation and feedback behavior. No other hidden seed may be introduced.

## 9. Future output contract

If separately implemented and executed, each case/run should emit:

```text
output_event_log.csv
output_provenance_comparison.csv
case_result.json
case_manifest.json
```

The result contract must keep these fields separate:

- declared and observed replay fingerprints;
- output source version and accepted flag;
- output source candidate ID;
- committed, candidate, and persistent mirror hashes before and after each event;
- output snapshot fingerprint;
- residual, tangent, stress, and exact analytical deltas;
- provenance, read-only, candidate-isolation, feedback, finite, and repetition gates.

Only valid accepted rows may be used in a future accepted-output table. Trial or unsafe output rows remain in the event ledger with `output_accepted_flag=false`.

## 10. Static acceptance checklist

- [x] OP-01/02 match the D0 identifiers and expected classifications.
- [x] OP-01 contains a live unaccepted candidate during the output request.
- [x] OP-01 freezes an exact accepted-state payload and fingerprint.
- [x] OP-02 changes only output-read history while holding the declared replay packet fixed.
- [x] OP-02 has a finite, nonzero exact Fraction oracle.
- [x] Provenance and output noninterference are separate gates.
- [x] Tolerances and two future repetitions are frozen.
- [x] No source, test, runner, result, benchmark, or Abaqus execution is authorized.
- [ ] Source implementation: NOT AUTHORIZED.
- [ ] Formal execution: NOT AUTHORIZED.
- [ ] Evidence registration and manuscript synchronization: OPEN pending execution.

## 11. Stop boundary

This plan ends at static design. It must not create source, tests, runners, results, figures, claim-matrix revisions, manuscript revisions, or execute any case. The next action requires separate user authorization for L2-D4 implementation only; implementation must still end before formal execution.
