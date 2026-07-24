# Transactional Lifecycle Audit

Reproducibility software for auditing rollback-external state drift in path-dependent nonlinear computational models.

This repository accompanies the manuscript **"Transactional lifecycle audits expose rollback-external path drift in stateful nonlinear finite-element simulations."** It provides the open finite-element host and mutation-strength benchmark used to test committed/trial-state ownership, rollback invariance, operator-version compatibility, and accepted-output provenance.

## Scope

The public package contains standalone Python benchmarks only. It does **not** contain or invoke Abaqus, a private UEL, unpublished doctoral-project models, long-window carbon-storage simulations, or production application outputs. A benchmark pass is not evidence that those excluded systems are verified.

## Repository layout

- `benchmarks/FEH_D0/`: open two-dimensional finite-element lifecycle host, frozen cases, tests, and runner.
- `benchmarks/MUT_D0/`: predeclared mutation-strength study, tests, reporting contract, and runner.
- `release_assets/Supplementary_Software_S1_v2_9.zip`: exact expanded supplementary-software archive used for the manuscript package.
- `release_assets/Supplementary_Software_S1_manifest_v2_9.json`: file-level manifest for the expanded archive.
- `release_manifest_v1.0.0.json` and `SHA256SUMS.txt`: file inventory and release checksums.
- `release_QA_v1.0.0.json`: source-parity, unit-test, smoke-test, privacy, and browser-upload QA.

The complete supplementary archive retains historical development material for provenance. Its `legacy_release_reference/` directory is not a second supported execution environment.

## Supported environment

- Python 3.12
- scikit-fem 12.0.2
- NumPy 2.5.1
- SciPy 1.18.0
- One process and one numerical thread for the frozen formal protocol

Install into an isolated environment:

```powershell
python -m venv .venv-feh
.\.venv-feh\Scripts\python.exe -m pip install -r requirements-feh-mut.txt
```

## Minimal smoke test

The command below runs one analytical patch case. It checks installation and the public runner; it is not a reproduction of the complete evidence matrix.

```powershell
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:NUMEXPR_NUM_THREADS = '1'
$env:FEH_D0_EXECUTION_AUTHORIZED = 'YES'
.\.venv-feh\Scripts\python.exe benchmarks/FEH_D0/run_feh_d0.py `
  --case-id FEH-REF-01 `
  --run-id smoke_1 `
  --output-root reproduction_outputs `
  --execute-authorized
```

Expected classification: `PASS_ANALYTICAL_PATCH` with `pass_flag=true`.

The runner refuses to overwrite an existing output directory. Remove or rename your local `reproduction_outputs` directory before deliberately repeating the same `run-id`.

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv-feh\Scripts\python.exe -m unittest discover -s benchmarks/FEH_D0 -p "test_feh_d0.py"
.\.venv-feh\Scripts\python.exe -m unittest discover -s benchmarks/MUT_D0 -p "test_mut_d0.py"
```

Unit tests support implementation QA but do not replace the two-fresh-process formal evidence protocol described in the manuscript supplement.

## Release integrity

The exact manuscript supplementary-software archive has SHA-256:

```text
5063faca287f81f0a5007bd8957e05c4254cb29183e0f2968464820806f22d45
```

Run the following from the repository root to inspect release hashes:

```powershell
Get-Content SHA256SUMS.txt
```

## Data

Numerical source data are not duplicated in this software repository. They are prepared as a separate dataset under the Creative Commons Attribution 4.0 International license. The permanent dataset DOI will be added after the dataset is deposited and published. See `DATA_AVAILABILITY.md`.

## Citation

Citation metadata are provided in `CITATION.cff`. The version-specific Zenodo DOI will be added after Zenodo archives GitHub Release `v1.0.0`. Until then, cite this repository by its URL and version without inventing a DOI.

## License

Source code is released under the BSD 3-Clause License. See `LICENSE`.

