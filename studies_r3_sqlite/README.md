# R3 SQLite lifecycle study

This directory contains the independent R3 cross-domain extension for
M-2026-003.  It instantiates the lifecycle transaction contract on SQLite
savepoints, application-owned persistent state, versioned policy metadata,
and commit-gated output.  It does not claim that the constructed integration
faults are defects in SQLite.

The study has three evidence layers:

1. A preregistered 12-case, four-verdict diagnostic matrix.
2. A preregistered enforcement experiment with six constructed faults and
   three benign controls.
3. A separate differential reproduction of the public SQLite WAL/savepoint
   defect reported in forum post `b490f726db`, using official 3.50.1 and
   3.50.2 Windows binaries.  This historical case is never pooled with the
   constructed cases.

The mathematical claims are conditional on the declared observation
projection and adapter assumptions.  `formal/bounded_model.py` performs
finite-state exploration only; it is corroboration, not an unbounded proof.

## Development and formal execution

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -p "test_*.py"
python run_case.py --config config/preregistration.json --case-id SQL-S01 `
  --run-id pilot-01 --mode diagnostic --output results/pilot/SQL-S01
python run_study.py --config config/preregistration.json `
  --output results/formal_20260903
python formal/bounded_model.py --output results/formal_20260903/bounded_model.json
python historical_wal_reproducer.py --output results/historical_20260903
```

Formal results must be run only after the source/configuration freeze manifest
has been generated.  Existing result directories are never overwritten.

