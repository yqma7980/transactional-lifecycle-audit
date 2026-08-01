# Supplementary Software S1 (manuscript package v2.15.4)

This package contains the standalone article code under the BSD 3-Clause license. The top-level FEH/MUT workflows remain executable with `requirements-feh-mut.txt`. `benchmarks_v2_15` adds the frozen DOLFINx/PETSc P4d implementation, P5 scaled-fault backend and P6R read-only projection code used by the manuscript evidence package.

## FEH/MUT smoke test

```powershell
python -m venv .venv-feh
.\.venv-feh\Scripts\python.exe -m pip install -r requirements-feh-mut.txt
$env:OMP_NUM_THREADS='1'; $env:OPENBLAS_NUM_THREADS='1'; $env:MKL_NUM_THREADS='1'; $env:NUMEXPR_NUM_THREADS='1'
$env:FEH_D0_EXECUTION_AUTHORIZED='YES'
.\.venv-feh\Scripts\python.exe benchmarks/FEH_D0/run_feh_d0.py --case-id FEH-REF-01 --run-id smoke_1 --output-root reproduction_outputs --execute-authorized
.\.venv-feh\Scripts\python.exe -m unittest benchmarks/FEH_D0/test_feh_adjudication_v2_11.py
```

## Native-host and projection layers

The P4d/P5 protocols freeze the exact DOLFINx container identity, PETSc options and explicit authorization gates in their JSON and Markdown contracts. P6R is a read-only projector over immutable formal packets. These directories are archived for audit and reproduction; no claim is made that one Windows command reproduces every historical layer or that the package contains the private Abaqus/UEL model.

The public GitHub v2.15.4 release and the versioned Zenodo software archive contain these additions:

- Software concept DOI (all versions): https://doi.org/10.5281/zenodo.21536450
- Numerical source-data DOI: https://doi.org/10.5281/zenodo.21739730

The archived packages do not contain the private Abaqus/UEL production project or unpublished carbon-storage application outputs.

## v2.15.4 canonical Git-blob checksum correction

Version 2.15.4 computes the package manifest and SHA-256 index directly from canonical Git blob bytes, avoiding platform-dependent checkout or archive line-ending conversion. Release-local metadata cites the stable software concept DOI; the version-specific DOI is assigned by Zenodo after publication and is cited in the manuscript and Zenodo metadata. No reported scientific case, equation, frozen acceptance gate, result or interpretation changes.
