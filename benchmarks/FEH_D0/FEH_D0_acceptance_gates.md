# FEH-D0 acceptance gates

Status: `FROZEN_BEFORE_IMPLEMENTATION`

1. Host identity: scikit-fem 12.0.2 and the frozen dependency hashes are recorded.
2. Mesh identity: primary 48 Q1 elements/192 quadrature points; hold-out 70 Q1 elements/280 quadrature points.
3. Patch reference: relative reaction and integration-point stress errors are each at most `1e-10`.
4. Finite gate: every normal physical value has absolute magnitude below `1e100` and is neither NaN nor infinite.
5. Convergence gate: every accepted increment satisfies the frozen residual tolerance in no more than 20 Newton iterations.
6. Balance gate: `|R_top + R_bottom| / max(1, |R_top|, |R_bottom|) <= 1e-9`.
7. Bounds gate: `kappa >= -1e-14` and all committed/candidate shapes match the frozen quadrature layout.
8. Safe history parity: direct, rejected-line-search, cutback, and restart histories have semantic accepted fields within `1e-11` absolute and relative tolerance and equal committed-state fingerprints at common accepted checkpoints.
9. Safe replay invariance: residual and tangent at an equal declared replay packet differ by at most `1e-12` relative Frobenius/2-norm, and the semantic provenance packet is identical.
10. Restart gate: checkpoint serializer round-trip is exact for discrete fields and hexadecimal floating payloads; restart continuation matches the direct accepted state within `1e-11`.
11. Trial-cache negative control: the seeded strong mutation produces finite, reproducible nonzero replay drift above `1e-8` without changing the declared packet.
12. Output-feedback negative control: trial output remains unreachable in the safe path; the seeded unsafe path produces finite, reproducible replay drift above `1e-8`.
13. Version mismatch: rejection occurs before a Newton correction, state commit, checkpoint, or accepted output; committed state remains unchanged.
14. Repetition gate: two fresh-process repetitions match after removal of run ID, timestamps, and absolute paths.
15. No prerequisite threshold may be changed after a formal result is observed.
