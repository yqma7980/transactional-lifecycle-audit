# P4d.6 final evidence consolidation

## Final status

`PARTIAL_OBSERVED_P4D_WITH_NATIVE_LINESEARCH_NOT_SUPPORTED`

This package consolidates P4d.2-P4d.5b evidence only. No new finite-element solve was run, and the nine-case design is not a complete matrix pass.

## Accounting and adjudication

Eight cases have two scientifically eligible fresh-process runs (16 formal scientific runs). `P4D-SAFE-LS-01` remains `NOT_SUPPORTED_BY_DIAGNOSTIC_ENVELOPE`. One raw native-line-search contract failure, two output-writer infrastructure failures, and three exploratory diagnostic runs are retained. The registry contains 22 process records and the contract trace contains 12 records.

The observed cases are the reference, constitutive oracle, direct transactional history, author-driver retry, author-managed restart, seeded cache negative control, output negative control after the P4d.5b schema erratum, and protective version guard. Expected negative-control detection means the detector behaved as designed; the mutated implementation is not safe.

## Native-host versus author-driver boundary

Host-native evidence covers DOLFINx assembly, PETSc residual/Jacobian evaluation and SNES reasons, and line-search candidate/selected packets exposed by the read-only C bridge. Author-driver evidence covers committed/trial ownership, retry/rollback control, checkpoint serialization, version guards, output provenance, and seeded mutations. The retry case is not PETSc TS rollback, and the restart case is not external PETSc TS restart.

## Native line-search branch

P4d.2 produced 29 candidate and 29 selected packets with complete C-to-Python correlation but zero structured unselected candidates. P4d.3 preserved the raw `P4D-SAFE-LS-01_CONTRACT_FAIL` and identified a non-triggering history rather than numerical or observer failure. P4d.4 exhausted predeclared targets 0.20, 0.24, and 0.28 without a qualifying trigger, so no held-out run was selected.

## Independent branches and preserved failures

The author-driver retry had zero residual/tangent replay drift. The cache mutation produced finite repeated drift (`1.0431e-5` residual; `14.4338` tangent). The version guard rejected a numerically equal metadata mismatch before correction. After the schema-only P4d.5b erratum, the output mutation exposed one rejected row per run at source load factor `0.08`. The two older writer failures remain infrastructure evidence because they created no case result or manifest.

## Claim boundary and next gate

This package supports bounded serial DOLFINx/PETSc evidence for the eight observed cases. It does not establish a full P4d pass, native rejected line-search coverage, parallel/thread safety, Abaqus or production readiness, multiphysics/CO2 validity, or detection completeness.

The next candidate is `P5_SCALED_THRESHOLD_AND_FRESH_PROCESS_NULL_ENVELOPE_FREEZE`. It is not authorized here and cannot retrospectively change P4d thresholds or adjudications.
