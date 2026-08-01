# P6R static and unit QA

Status: `PASS_P6R_IMPLEMENTATION_PREFLIGHT_READY_FOR_FORMAL_PROJECTION`.

This is implementation preflight evidence only. It is not `OBSERVED-P6R`, does not execute the ten planned projection processes, and does not change the frozen P5 evidence.

## Checks

- Frozen P6R source manifest SHA-256 matched `88e32f884eb2f99236dae4d2dacc5d9bd74cf5a02417c0fae52eb4d644e53aee`.
- All 70 immutable P5 files matched the frozen SHA-256 records.
- Twenty accepted-output/event-ledger CSV files satisfied the required read-only schemas.
- Ten Python files passed AST compilation.
- Twenty-one synthetic unit tests passed with zero failures and zero errors.
- `M2_CKPT` and `M3_STATE` return not-applicable packets without reading a raw bundle.
- The applicable projectors remove all forbidden family, expected-verdict, selection and observed-classification fields.
- Detector modules do not import the post-detection oracle.
- M6 history IDs are pseudonymized before detector access.
- The runner's missing-authorization smoke test failed closed before creating `results`.
- No formal projection, FE solve, Abaqus process, Docker process or manuscript update was performed.

## Interpretation boundary

M5 reports a method-generic equal-input operator replay drift. It cannot localize F05 versus F07 from forbidden owner/event/source fields. Family-specific cause labels remain post-detection oracle annotations and may only be attached after detector outputs are frozen.

