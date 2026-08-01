# P4d.5b implementation and execution plan

1. Verify all protected P4d.2/P4d.5 hashes and the P4d.5b freeze before any write.
2. Install a process-local `AcceptedOutputStore.write` adapter with the frozen 18-column schema.
3. Add bounded erratum metadata when `case_result.json` is written; preserve the base implementation version.
4. Run AST/static checks and unit tests only. No FE case is allowed before QA passes.
5. Under separate case and pair authorization locks, execute only `P4D-NC-OUTPUT-01`, once per fresh container for `run_1` and `run_2`.
6. Verify each manifest, compare JSON/CSV semantically and NPZ exactly, then freeze a bounded final evidence package.
