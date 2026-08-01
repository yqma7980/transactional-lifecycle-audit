# L0 scalar unsafe/safe replay benchmark

This standalone benchmark implements the scalar counterexample in M1.4 without Abaqus or external dependencies.

## Run

From this directory:

```powershell
python -m unittest discover -s tests -v
python run_benchmark.py
```

The benchmark uses only the Python standard library.

## What it tests

Three variants are replayed under three discarded-call histories:

- `unsafe_persistent`: a deliberately defective hidden cache;
- `safe_local`: pure call-local evaluation;
- `safe_transactional`: explicit candidate/reject/accept ownership.

The compared histories reach the same declared replay state. A nonzero finite residual difference is expected only for the seeded unsafe variant.

## Predeclared results

`expected_results.json` freezes parameters, tolerance and all nine expected outcomes before execution. See `benchmark_spec.md` for the mathematical definition and claim boundary.

## Result meaning

`overall_pass=true` means the benchmark correctly detects all unsafe negative controls and accepts all safe controls. It is a lifecycle unit-test result, not evidence of multiphysics accuracy or production readiness.

## File map

```text
l0_model.py             evaluator implementations and call ledger
run_benchmark.py        scenario runner and result writer
expected_results.json   predeclared acceptance matrix
benchmark_spec.md       frozen model, gates and interpretation
tests/test_l0.py        automated unit and determinism tests
results/                generated summary, ledger and manifest
```
