# L2-D5 checkpoint-provenance implementation plan

**Design:** `L2-D5.0a`  
**Frozen status:** `FROZEN_NOT_IMPLEMENTED`  
**Case:** `L2-CP-01` only  
**Abaqus used:** no
**Revision:** analytical fractions are unchanged; D1 runtime canonical fingerprints now use the actual accepted IEEE-754 packets observed in the pre-implementation dry-run. No equation, path, tolerance or case gate changed.

## Purpose

Test one bounded question: whether a checkpoint created only from an accepted primary state and committed physical history can be validated, restored into a fresh standalone host and continued to the same accepted state as an uninterrupted reference path.

This test is deliberately narrower than restart parity. It does not invoke Abaqus, restart files, coupled fields, external I/O concurrency or the production model.

## Frozen implementation sequence

1. Reuse the D1 material, element, state serializer, safe transactional variant and Newton host without modifying them.
2. Solve the one-element bar from accepted version 0 to `F=11/10` and verify the frozen analytical state.
3. Construct a versioned checkpoint payload using only the accepted displacement, force, reaction, committed state and model/operator identity.
4. Serialize the payload with the D1 canonical serializer, store its SHA-256 in a strict envelope and verify that writing does not mutate the source host.
5. Deserialize into a fresh host only after schema, payload hash, configuration identity and committed-state fingerprint validation.
6. Continue both the uninterrupted host and restored host to `F=6/5`.
7. Require exact final committed and physical-checkpoint fingerprints and fieldwise `1E-12` analytical parity.
8. Reject corrupted payloads in unit tests before any continuation, commit or output.

## Planned files

- `src/l2_d5_checkpoint_provenance.py`
- `oracle/l2_d5_fraction_oracle.py`
- `tests/test_l2_d5_checkpoint_provenance.py`
- `run_l2_d5.py`
- implementation manifest and static/unit QA

## Future formal execution

After implementation QA, `L2-CP-01` will run twice in independent single-process, single-thread processes. Formal execution will require the runner argument `--execute-authorized` and `L2_D5_EXECUTION_AUTHORIZED=YES`. The case must stop on any schema, hash, source-mutation, restore, finite or continuation-parity failure.

## Evidence boundary

A pass supports only `PASS_CHECKPOINT_ROUND_TRIP` in the frozen standalone host. It does not establish Abaqus restart parity, production checkpoint safety, thread safety, conservation, performance or coupled-physics validity.
