# P5B implementation preflight protocol

Status target: `IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED`

## Scope

This package implements the frozen P5A four-way adjudication contract, common
case-result schema, and read-only adapters for JSS-S01, JSS-S02, and JSS-S03.
It does not execute any of the 20 frozen P5B cases.

## Frozen precedence

1. `EXECUTION_ERROR`
2. `NOT_SUPPORTED`
3. `INVALID`
4. `DETECT_LIFECYCLE_DRIFT`
5. `PASS_INVARIANT`

`INVALID` and `NOT_SUPPORTED` terminate before lifecycle drift evaluation.
The F08 contract distinguishes a pre-comparison version mismatch (`INVALID`)
from an internal version violation emitted by an otherwise eligible history
(`DETECT_LIFECYCLE_DRIFT`).

## Adapter boundary

An adapter may normalize only evidence emitted by its subject. A required token
is available only when both the frozen subject capability and the raw ledger
provide it. Missing native events remain explicit `NOT_SUPPORTED` evidence.

## Authorization boundary

The preflight runner accepts only three safe-null IDs. It requires both the CLI
flag `--preflight-authorized` and the environment lock
`JSS_P5B_PREFLIGHT_AUTHORIZED=YES`. Formal P5B IDs are rejected before any
output directory can be created.

## Tests allowed in this phase

- four-way precedence and F08 semantics;
- frozen matrix and adapter contracts;
- common result schema;
- authorization and no-write guards;
- import side effects;
- safe-null and duplicate normalization.

Unit tests are implementation QA, not formal benchmark evidence.
