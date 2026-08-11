# Transactional Lifecycle Audit v3.0.0

This release is the reproducibility software for the study **Lifecycle-aware metamorphic testing for stateful simulation software: verdict validity, fault localization, and instrumentation cost**.

It extends the earlier finite-element and mutation artifacts with the complete JSS P5 evidence chain:

- P5B: a four-way adjudication contract (`PASS_INVARIANT`, `DETECT_LIFECYCLE_DRIFT`, `INVALID`, and `NOT_SUPPORTED`) exercised by 20 cases and 40 fresh-process runs;
- P5C: a 12-case fault-localization study using one frozen eight-candidate ontology for generic replay and full lifecycle evidence;
- P5D: a gated cost study with 18 cells, 36 unreported warm-ups, and 180 timed fresh processes.

The release preserves failed contracts and errata. It does not contain the private Abaqus/UEL production project, unpublished production meshes, or long-window carbon-storage outputs.

## Directory map

```text
studies_jss_p5/
  P5B_four_way_adjudication/  adjudication API, adapters, tests, and formal results
  P5C_localization_v2/        common ontology, ranking code, tests, and formal results
  P5D_performance/            equivalence gates, timing runner, tests, and formal results
benchmarks/                   earlier standalone benchmark layers
benchmarks_v2_15/             earlier DOLFINx/PETSc and projection layers
```

## Environment

The P5 host-side tests use Python 3.12 with NumPy 2.4.3 and SciPy 1.17.1. Native DOLFINx/PETSc evidence retains its frozen container identity in the archived protocol files. Formal cases are not rerun by the verification commands below.

```powershell
python -m venv .venv-jss
.\.venv-jss\Scripts\python.exe -m pip install -r requirements-jss-p5.txt
$env:PYTHONDONTWRITEBYTECODE='1'
```

## Verify the release

First verify every indexed byte:

```powershell
.\.venv-jss\Scripts\python.exe verify_release.py
```

Then run the implementation tests without executing the formal matrix. The
test harness copies each implementation to a temporary source-only tree so
that no-write guards are not confused by the archived formal-result folders:

```powershell
.\.venv-jss\Scripts\python.exe run_release_tests.py
```

These tests validate implementation and schema contracts. They do not replace
or rerun the archived fresh-process formal evidence.

## Releases and data

- GitHub: https://github.com/yqma7980/transactional-lifecycle-audit
- Software concept DOI: https://doi.org/10.5281/zenodo.21536450
- Dataset concept DOI: https://doi.org/10.5281/zenodo.21536560

The version-specific v3.0.0 DOIs are recorded in the associated manuscript and Zenodo metadata.

## Licenses

Software is licensed under BSD-3-Clause. The separately archived numerical source data are licensed under CC BY 4.0.
