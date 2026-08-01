# P4d.3 native line-search postmortem and P4d.4 static freeze

## Final status

PASS_P4D3_POSTMORTEM_AND_P4D4_DIAGNOSTIC_FREEZE

## Findings

The seven protected P4d.2 hashes match their frozen values. P4D-SAFE-LS-01/run_1 contains 29 candidate/selected pairs. Every candidate and selection used lambda=1, reason=0, and identical X/F/Y/W/G vectors; all 29 candidates correlate exactly to Python TrialEvaluate primary vectors. No structured unselected candidate occurred.

The P4d.1 zero case contains 1 structured unselected candidate, proving that the same public PETSc observation pattern can distinguish a full-step candidate from the selected backtracked state. The evidence therefore supports FROZEN_HISTORY_DID_NOT_TRIGGER_NATIVE_REJECTION rather than an observer limitation.

## Adjudication

- Preserved raw verdict: P4D-SAFE-LS-01_CONTRACT_FAIL.
- Read-only derived adjudication: NOT_SUPPORTED_BY_FROZEN_HISTORY.
- The run is not relabeled PASS, numerical failure, or observer failure.
- The complete P4d matrix remains not passed.

## P4d.4 freeze

DIAG-LS-00 records the existing 0.08 -> 0.16 observation without rerun. DIAG-LS-01/02/03 statically freeze targets 0.20, 0.24, and 0.28 from the same 0.08 cyclic reload state with declared accepted-state lag. All future diagnostic outputs remain EXPLORATORY_NOT_FORMAL_EVIDENCE. The held-out mapping is fixed at 0.22, 0.26, or 0.30 according to the first trigger.

## Evidence boundary

No FE solve or benchmark was executed for this postmortem. No old result, threshold, manuscript, claim matrix, figure, GitHub, Zenodo, DOI, Abaqus, COMSOL, OpenSees, or production artifact was modified.
