# L1 acceptance gates

Status: predeclared design `L1-D1.0`; no outcome has been observed

## 1. Gate order

Evaluate gates in this order. A later pass cannot repair an earlier failure.

1. schema and provenance validity;
2. declared-state equality for compared histories;
3. committed-state and candidate lifecycle;
4. seeded unsafe detection and safe-control false-positive result;
5. analytical constitutive/operator accuracy;
6. thermodynamic sanity;
7. output/checkpoint provenance;
8. reproducibility;
9. reporting-only performance.

`L1-E1` is blocked unless every hard `L1-MP` case passes.

## 2. Frozen numeric envelopes

### 2.1 Exact same-implementation lifecycle replay

For safe variants under identical canonical packets:

```text
declared packet hash: exact equality
committed IEEE-754 state hash: exact equality
candidate reachability after reject: none
accepted version after reject: exact equality
stress/residual/tangent replay hash: exact equality
numeric Delta stress or Delta R: exactly 0.0
```

Exact equality is appropriate here because the standalone reference is single-threaded and replays the identical instruction path. This tolerance must be revisited before threaded, compiled-cross-language or host-level comparisons.

### 2.2 Analytical reference accuracy

For stress, state, residual and tangent reference values:

```text
absolute tolerance = 1.0e-12
relative tolerance = 1.0e-12
scale = max(1, abs(reference)).
```

### 2.3 Directional tangent check

Use a central difference with frozen perturbation

```text
h = 1.0e-7
```

at points separated from the yield surface by at least `1.0e-4` in `abs(f_trial)`. Require

```text
relative directional error <= 1.0e-6.
```

The yield kink itself is excluded from this differentiability gate and must not be used to relax lifecycle rules.

### 2.4 Seeded unsafe detection

The primary rejected-trial seed must match the analytical value:

```text
Delta stress = Delta R = -205/121
```

within the analytical tolerance. Other seeded unsafe cases must satisfy:

```text
all values finite,
abs(drift) > 1.0e-8,
abs(drift) >= 1000 * max(safe_replay_envelope, 1.0e-15).
```

If an unsafe seed is not detected, the harness fails. If a safe control exceeds its envelope, the harness fails. Neither result may be relabeled as an implementation inconvenience.

## 3. State and provenance hard gates

- Every compared replay packet has an identical declared fingerprint.
- Every rejected evaluation leaves the committed state and accepted version unchanged.
- No rejected candidate is reachable after attempt invalidation.
- A candidate can be accepted no more than once.
- Stress, residual and tangent carry compatible state-version metadata.
- Terminal/output calls are read-only for safe variants.
- Accepted output names an accepted source version and no trial candidate.
- Checkpoint restore reproduces the complete committed state and configuration identity.
- Normal calls contain no NaN, Inf or overflow sentinel.

Any violation is a hard L1 failure even if stress, residual or tangent remains finite.

## 4. Physical-reference gates

- `MP-REF-01`, `MP-REF-02`, `E1-REF-01` and `E1-REF-02` meet the analytical envelope.
- The accepted load-unload-reload path matches an independent return-mapping oracle.
- Incremental plastic dissipation is not less than `-1.0e-12`.
- Constitutive accuracy and lifecycle are reported in separate columns.

## 5. Reproducibility gates

- Two clean complete executions produce identical scenario summaries and call ledgers.
- Source, specification, expected-results and output hashes are recorded.
- No timestamp, random identifier or unordered mapping may enter deterministic result files.
- Human-readable decimal output is not used as the authoritative equality representation.

## 6. Performance reporting

Measure evaluation count, wall time and peak memory for safe and unsafe variants, but do not use performance as a L1 pass criterion. L1 is too small for stable production-performance claims. Report overhead as descriptive evidence only.

## 7. Branch rules

### Branch A: L1-MP pass

Proceed to L1-E1 only if all MP hard gates pass and both unsafe seeds are detected.

### Branch B: safe false positive

Stop. Audit packet canonicalization, floating representation, candidate invalidation and event ordering. Do not widen tolerance until the exact cause is recorded.

### Branch C: unsafe false negative

Stop. Audit whether the seed actually reaches the later physical operator and whether histories are genuinely different only in hidden state.

### Branch D: analytical-reference failure

Stop. Repair the constitutive oracle or implementation before interpreting lifecycle results.

### Branch E: L1-MP pass and L1-E1 fail

Localize the failure to element assembly, version propagation, output provenance or element-level persistence. Do not start L2.

### Branch F: complete L1 pass

Mark only L1 as observed pass. L2-L6 remain open. Draft the L2 protocol separately before any host solve.
