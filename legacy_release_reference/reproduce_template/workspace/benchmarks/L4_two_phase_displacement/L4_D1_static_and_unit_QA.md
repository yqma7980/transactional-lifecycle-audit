# L4-D1 static implementation and unit QA

Status: IMPLEMENTED_UNIT_TESTED_NOT_FORMALLY_EXECUTED

This is a pre-execution implementation audit. It is not formal benchmark evidence and does not establish OBSERVED-L4.

## Frozen-contract checks

- Design version: L4-D1.0.
- Formal case count: 10 unique IDs.
- All source-manifest hashes matched disk.
- Frozen scientific specification, oracle, case matrix and tolerances remained unchanged.
- Runner authorization locks are present for the explicit flag, execution environment and single-thread environment.
- No results directory or __pycache__ existed at the end of QA.

## Implementation checks

Eight Python files passed AST parsing. The implementation reuses the authoritative L2 canonical serializer directly from its source file, avoiding the legacy L2 package initializer without introducing another fingerprint format.

The dated pre-execution erratum records three implementation-only corrections. Its SHA-256 is 38b32a7537d53cd52ac50da3d8d3112dfc4c8ed0b19d625f723c4abba2b016a4. None changes the scientific model, reference, tolerance or formal schedule.

## Directed tests

The authorized single-process, single-thread unittest run completed 10 tests in 85.623 seconds with 10 passes, zero failures and zero errors. It covered:

- freeze/matrix identity and manifest parsing;
- entropy shock identity and independent oracle finiteness;
- single-step and cumulative phase balance;
- exact safe retry/rollback parity;
- finite seeded-unsafe drift detection;
- all 10 frozen case classifiers in memory;
- unauthorized-case rejection.

The all-case in-memory check is a preflight only. It does not replace the required two independent formal processes per case.

## Boundaries

No formal L4 case was run. No accepted formal result, source-data figure or manuscript claim was created. Abaqus and the production model were not used. Production Git remained tracked=0, staged=0, untracked=53 with status fingerprint 4def4e7d6c4b5369caa9c0582324f6d2470861f5b07ce57b51e9fd08e18c6e7f.

Implementation manifest SHA-256: c9cf2a320582b0eeba2c9483e74a20c605c96732c6418bb0916a38a5b083f9a1.

An absolute-path runner smoke import also passed after a pre-result path-bootstrap correction. The failed launch created no result directory and is retained in the dated erratum.

The next authorized gate is sequential execution of the 10 frozen cases, with two independent single-process, single-thread repetitions per case and immediate stop on any prerequisite failure.
