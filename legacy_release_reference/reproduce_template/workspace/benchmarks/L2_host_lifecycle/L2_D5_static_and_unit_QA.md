# L2-D5.0a static and directed-unit QA

## Status

`IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED`

This is an implementation and directed-unit-test record, not formal L2-D5
evidence. No CP-01 formal run existed when this record was written.

## Implemented contract

- A checkpoint is written only from an accepted D1 `AcceptedCheckpoint`.
- The payload is canonical ASCII JSON with `float.hex` fields, a payload hash,
  schema, model, operator and configuration identities.
- Reading rejects schema, payload-hash, configuration, model or committed-state
  mismatches before fresh-host continuation.
- Restore sets only accepted displacement and committed state in a fresh safe
  host; open attempts and trial candidates are not restored.
- Reference and restored paths then solve to force `6/5` and compare fields at
  `1E-12`, while committed and physical fingerprints require exact equality.

## Analytical and runtime separation

The independent Fraction oracle gives checkpoint `u=21/1000`,
`epsilon_p=kappa=1/100` and continuation `u=4/125`,
`epsilon_p=kappa=1/50`. D1 Newton runtime fingerprints use the actual accepted
IEEE-754 packets; the analytical fractions are not substituted into byte-level
hash gates.

## QA results

- Four implementation Python files passed AST parsing.
- The independent Fraction oracle reproduced every frozen analytical value.
- Directed unit tests: `10/10 PASS` in one process and one thread.
- Corrupted payload and configuration mismatch were rejected.
- The no-authorization runner probe exited with code `1` before creating a
  result root.
- Runner execution requires both `--execute-authorized` and
  `L2_D5_EXECUTION_AUTHORIZED=YES`.
- Abaqus and the production model were not used.

## Evidence boundary

This QA does not establish `OBSERVED-L2-D5`, Abaqus restart parity, production
readiness, conservation, performance, coupled-physics validity or application
physics. Formal evidence requires CP-01 in two independent single-process,
single-thread runs followed by immutable-result verification.

Implementation manifest SHA-256 is reported externally to avoid a self-hash
cycle.
