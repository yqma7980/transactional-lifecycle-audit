# P5 execution mount erratum (2026-07-31)

## Scope

The first matrix invocation under execution tag
`P5_formal_20260731_fullFE_v1` stopped before producing a case result.
The preserved process log has SHA-256
`167c23775a40fa63dad4d1dad58de2554d1300a0d96aa48f3acc929c8275c976`.
This tag is retained as infrastructure-failure evidence and will not be reused.

## Root cause

The frozen host-side runner mounted the submission working directory at
`/working`. The in-container protected-evidence verifier intentionally resolves
manifest paths from the parent of `/working`, while those paths begin with the
submission-directory name. The protected file was therefore absent at the
resolved container path even though its mounted bytes and SHA-256 matched the
frozen manifest exactly.

The failure occurred before any FE solve, threshold calculation, strength
selection, or scientific classification.

## Bounded correction

`run_p5_matrix_mountfix.py` leaves the frozen runner and single-case runner
unchanged. It overrides only the Docker invocation to add a second read-only
bind mount at `/<submission-directory-name>`, while retaining the original
read-write `/working` mount for new results.

The correction does not change the image, equations, mesh, tolerances, case
matrix, process counts, null-envelope rule, scaled strengths, selection rule,
or acceptance gates.

## Frozen identities

- Original runner SHA-256:
  `8219a5c8593fba95d177ff877099458abdcf665be6a954f4f2f2742f6944d864`
- Mount-correction runner SHA-256:
  `2f949cf1301620dcf2ba0c314bfc7b90aa6c069374de8de39f6ae8cfacfe10e2`
- Replacement execution tag:
  `P5_formal_20260731_fullFE_v1a`

The replacement tag must pass the same dual authorization locks and all frozen
scientific gates.
