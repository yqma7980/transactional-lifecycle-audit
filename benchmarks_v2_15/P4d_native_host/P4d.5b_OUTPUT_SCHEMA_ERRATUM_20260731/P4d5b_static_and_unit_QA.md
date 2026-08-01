# P4d.5b static and unit QA

Status: PASS_P4D5B_STATIC_AND_UNIT_QA_READY_FOR_FORMAL_OUTPUT_RERUN

This is implementation preflight evidence, not a formal finite-element result.

- The erratum changes only the accepted-output CSV serialization contract.
- The frozen schema contains 18 columns and adds source_load_factor explicitly.
- Ordinary accepted rows serialize an empty source_load_factor; the injected rejected-trial row retains its numeric source load.
- Unknown output fields still fail closed.
- In-memory accepted-output rows and their canonical rows_sha256 are unchanged.
- P4d.2 model, mesh, load history, state lifecycle, solver, thresholds, oracle, events, and verdict logic are unchanged.
- Eleven of eleven unit tests passed.
- All Python sources passed AST parse and compile checks.
- The runner authorizes only P4D-NC-OUTPUT-01, run_1, and run_2, with CLI and environment locks.
- The pinned DOLFINx image is present locally; no container or Abaqus process was active.
- No formal case has been executed and no results or formal_execution_logs directory existed at this QA point.

The next authorized action is two fresh-process, single-thread reruns under a new P4d5b_output_schema_* tag. Success would validate this bounded output-provenance negative control only; it would not establish native PETSc rejected line-search coverage or a complete P4d matrix pass.
