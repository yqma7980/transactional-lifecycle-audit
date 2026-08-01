# PERF-D1 static freeze QA

Date: 2026-07-22  
Status: PASS  
Design status: FROZEN_NOT_IMPLEMENTED

- Case rows: 45 unique family-size-configuration cells.
- Families: L3, L4 and L6.
- Sizes: small, medium and large.
- Configurations: C0-C4 cumulative audit layers.
- Warm-up processes: 90, excluded from statistics.
- Formal measured processes: 450.
- Threads per worker: one.
- Frozen affinity: CPU 0, mask 1.
- Windows native capability probe passed for SetProcessAffinityMask and GetProcessMemoryInfo/PeakWorkingSetSize.
- All protected L3/L4/L6 source hashes and Claim/manuscript v2.0 hashes were verified before freeze.
- Source manifest SHA-256: $manifestHash.
- The non-formal scale pilot is retained only as size-selection evidence.
- No implementation, tests, formal performance result, Abaqus, COMSOL or production run exists.
- No positive speed claim is authorized. The only future pass classification is output-equivalent timing recorded under the frozen protocol.
- A PowerShell helper-name collision interrupted the first write after the six core design files; this QA and source manifest were generated only after those six files were read back and verified. No scientific content was changed after the interruption.