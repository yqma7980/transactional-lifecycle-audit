# P5B formal implementation review protocol

## Scope

This review evaluates `JSS-P5B-IMPL-1.0a` against the frozen P5A verdict
semantics and the 20-case P5B matrix. It is an implementation review only.
It does not execute a formal case and cannot create `OBSERVED-P5B` evidence.

## Review gates

1. Protected P5A and P5B preflight inputs retain their recorded SHA-256 values.
2. The matrix remains 16 DEVELOPMENT plus four HELD_OUT cases, with one
   held-out case for each four-way verdict.
3. The adjudication precedence remains execution error, not supported,
   invalid, lifecycle detection, invariant pass.
4. The subject adapter verifies the runtime relation against the frozen case
   relation and verifies the declared packet-difference contract.
5. The result schema enforces the stopping stage and evaluation flags for all
   outcomes.
6. A DEVELOPMENT authorization guard rejects held-out, unknown, and malformed
   run IDs before creating any path.
7. The original 27-test preflight snapshot and the revised formal-review suite
   both pass with bytecode generation disabled.
8. No formal runner, benchmark, Abaqus process, production model, or public
   repository operation is invoked.

## Activation rule

Only after every review gate passes may a separate activation manifest list
the exact 16 DEVELOPMENT case IDs. Activation requires both the CLI flag
`--execute-authorized` and environment variable
`JSS_P5B_DEVELOPMENT_AUTHORIZED=YES` for a future execution task.

The following held-out IDs remain sealed:

- `P5B-PASS-05`
- `P5B-DETECT-05`
- `P5B-INVALID-05`
- `P5B-NS-05`

They cannot be unlocked by the DEVELOPMENT activation.
