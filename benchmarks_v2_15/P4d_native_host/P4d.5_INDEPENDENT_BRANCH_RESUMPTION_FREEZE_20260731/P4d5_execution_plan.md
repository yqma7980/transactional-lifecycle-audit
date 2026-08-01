
# P4d.5 future implementation and execution plan

Current status: `FROZEN_STATIC_NOT_IMPLEMENTED`

## Phase A - compatibility implementation

Create a new P4d.5 runner and matrix orchestrator without modifying P4d.2. The numerical case implementation may be imported read-only only after a compatibility audit proves that equations, case histories, thresholds and output schemas are unchanged. P4d.5 dependency evaluation must come from `P4d5_case_matrix.csv`, not the older dependency strings in `p4d_config.py`.

The future runner must use two authorization locks and reject all case IDs outside the five-row matrix before creating an output directory. It must execute one case and one run ID per fresh container and write only to a new dated P4d.5 results root.

## Phase B - static and unit preflight

Required checks include protected hashes, AST/import safety, frozen case identity, branch-DAG evaluation, authorization-before-write, committed immutability, retry trigger, checkpoint schema, accepted-output ordering, version guard and duplicate normalization. Unit tests are implementation QA, not formal evidence.

## Phase C - separately authorized formal execution

Wave 1 contains retry, restart and version-guard branches. Wave 2 contains the two negative controls and is eligible only if retry formally passes. A failure in one Wave 1 branch does not suppress unrelated branches. Each eligible case runs twice in fresh single-process, single-thread containers.

## Future output contract

Each run must include a case result, event ledger, state/operator comparison, environment record and manifest. Final aggregation must preserve skipped, unsupported and failed branches and must not relabel the native line-search branch.

## Prohibited shortcuts

Do not rerun the inherited prerequisite cases, modify P4d.2, add a fourth line-search diagnostic, select a post hoc held-out target, relax thresholds, substitute another host or update manuscript/public artifacts before evidence synchronization.
