# L1 state and event contract

Status: frozen design `L1-D1.0`

## 1. State ownership

| Symbol | Meaning | Authoritative owner | Writable during evaluation | Survives reject |
|---|---|---|---:|---:|
| `D` | immutable material and element data | constructor/configuration | no | yes |
| `C_n` | accepted `(epsilon_p,kappa,version)` | transaction host | no | yes, unchanged |
| `X` | declared trial packet `(epsilon)` or `(u,F)` | caller | no | caller-controlled |
| `T_j` | disposable candidate history | evaluator/candidate registry | yes, candidate only | no |
| `O_j` | stress, tangent, residual and state fingerprints | evaluator return | yes, return only | no physical authority |
| `M_n` | accepted output snapshot with source version | output layer | only after accept | yes, diagnostic authority only |
| `P` | user-persistent cache | implementation | immutable/versioned/diagnostic only | never as unregistered physical history |
| `A` | attempt, call and operator-version metadata | harness | yes | declared and logged |

## 2. Evaluation packet

Every call must carry a complete packet:

```text
run_id
case_id
history_id
call_index
event
attempt_id
candidate_id
accepted_version
material_parameters_hash
configuration_hash
epsilon or (u,F)
committed epsilon_p and kappa
requested outputs
operator_version
```

Equal-state replay is valid only when the canonical packet fingerprint is identical between compared histories.

## 3. Events

| Event | Reads | May write | Commit effect | Reject/rollback effect | Forbidden effect |
|---|---|---|---|---|---|
| `BeginAttempt` | `C_n,D,A` | attempt metadata | none | discard attempt metadata | mutate physical history |
| `EvaluateMaterial` | `X,C_n,D,A` | `T_j,O_j` | none | discard `T_j` | overwrite `C_n` or unregistered `P` |
| `EvaluateElement` | `X,C_n,D,A` | material candidate and `R,K` | none | discard all candidates | use output mirror as history |
| `RejectCandidate` | candidate registry | invalidation marker | none | remove candidate | repair `C_n` after prior mutation |
| `RejectAttempt` | attempt registry | invalidation marker | none | remove all attempt candidates | leave candidate reachable as accepted state |
| `AcceptCandidate` | one valid candidate | `C_(n+1),version+1` | promote once | not applicable | double commit or accept rejected candidate |
| `OutputAccepted` | `C_n,M_n` | accepted snapshot and provenance | none | read-only | evaluate or mutate trial physical history |
| `TerminalRead` | accepted snapshot and metadata | diagnostics only | none | read-only | mutate any physical source |
| `CheckpointWrite` | full `C_n` and configuration identity | serialized copy | none | read-only | omit a required physical state field |
| `CheckpointRead` | serialized copy | restored transaction base | creates declared restored base | exact invalidation of stale candidates | merge with stale hidden state |

## 4. Required invariants

1. **Committed immutability:** evaluation and rejection leave `C_n` byte-identical.
2. **Candidate isolation:** no rejected candidate remains reachable by a later physical evaluation.
3. **Call-order replay:** equal declared packets produce equal operator fingerprints for safe controls.
4. **Version compatibility:** stress, residual and tangent report the same accepted and candidate version identifiers.
5. **Accept once:** one candidate can advance the accepted version at most once.
6. **Terminal noninterference:** inserted output/terminal reads do not change the next physical operator.
7. **Accepted-output provenance:** every physical output names an accepted version and cannot name a trial candidate.
8. **Checkpoint completeness:** restored committed state and configuration hashes match the written transaction base.
9. **Single authority:** no output mirror or cache is read as physical history unless it is the declared committed source.
10. **Finite is not sufficient:** a finite operator can still fail lifecycle replay.

## 5. Operator-version declaration

The material return packet must include:

```text
residual_state_version
tangent_state_version
tangent_kind = consistent | declared_lagged | finite_difference_check
```

L1 does not require exact Newton globally. It requires that the operator version be declared and that the residual/stress and tangent in one packet do not silently use different hidden history.

## 6. Fingerprints

Record separate canonical SHA-256 fingerprints for:

- declared input packet;
- committed physical state before and after the call;
- candidate state;
- hidden/persistent state, when a seeded unsafe variant is active;
- stress/residual/tangent operator tuple;
- accepted output snapshot;
- checkpoint payload.

Floating values must be serialized as IEEE-754 hexadecimal strings for exact same-implementation replay. Human-readable decimal columns are additional, not authoritative.
