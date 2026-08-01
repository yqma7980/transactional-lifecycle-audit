# L5-D1 static and directed-unit QA

Status: `FAIL_SCIENTIFIC_PRECHECK_GATE`

This is implementation/pre-execution QA, not formal L5 evidence.

- All eight implementation Python files parse successfully after the dated string-literal erratum.
- Frozen design/source files retained their recorded hashes.
- The implementation has independent state records, binary serializer, solver, oracle and lifecycle host; it contains no L4 implementation import.
- The runner requires the CLI authorization flag, `L5_D1_EXECUTION_AUTHORIZED=YES` and `L5_D1_THREADS=1` before creating output.
- Directed tests: 11 run, 10 pass, 1 fail, 0 errors.
- Failed prerequisite: `L5-IV-CV-01`, minimum order `0.6294266281954826 < 0.7`.
- No formal runner invocation, results directory, duplicate run or source-data synchronization occurred.
- No Abaqus process or production-model execution occurred.

The implementation cannot be promoted to `FORMALLY_EXECUTED` or `OBSERVED-L5` under the frozen L5-D1.0 acceptance contract.
