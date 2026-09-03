# Transactional Lifecycle Audit v6.0.0

## Added

- A sanitized R3 SQLite lifecycle study with a frozen 12-case diagnostic matrix.
- Retained 63-process diagnostic and guarded-containment records.
- A separate six-run differential reproduction of the reported SQLite 3.50.1/3.50.2 WAL/savepoint behavior.
- Conditional depth-8 finite-state corroboration and source/configuration hashes.
- Jianfeng Hao as the fifth author and the second funding source in release metadata.

## Preserved

- No v3.0.0 parent result is recomputed or overwritten.
- The separately released v4.0.0 and v5.0.0 OpenSees artifacts remain unchanged.
- Failed contracts, negative results, and evidence boundaries are retained.

## Excluded

- Downloaded SQLite executables and archives.
- Temporary database and WAL files, Python bytecode, caches, and pilot outputs.
- Private Abaqus/UEL code, production meshes, confidential engineering data, and unlicensed article full texts.

## Funding

- National Natural Science Foundation of China, Grant 52474038 (recipient: Weiji Sun).
- Liaoning Provincial Department of Education project, Grant LJ212410147066 (recipient: Jianfeng Hao).

## Claim boundary

The constructed SQLite integration faults are author-created tests, not defects in SQLite. The historical reproduction is one public defect differential and is not pooled with the constructed cases. Depth-8 exploration is finite corroboration, and test-harness containment is not production validation.
