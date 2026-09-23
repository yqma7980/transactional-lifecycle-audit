# Auditable Lifecycle Contracts: v7.0.0

Version-specific archived software and evidence:
[Zenodo DOI 10.5281/zenodo.22916803](https://doi.org/10.5281/zenodo.22916803).
This citation was added after automatic archiving; the v7.0.0 tag is unchanged.

The current evidence addition is [studies_route_a](studies_route_a/README.md):
Django/Celery equal-information comparison and Click/Trio applicability-boundary
records supporting **Auditable Lifecycle Contracts for Stateful Software:
Equal-Information Comparisons and Applicability Boundaries**.

Both methods detect 6/6 manifestations with 0/18 normal false positives. LCMA
pure-decision evaluation is approximately 2.171/2.164 times slower. Click and
Trio remain HOLD cases; the depth-1500 negative evidence is retained. There are
two historical defect lineages, not 24 independent defects. No studies were
rerun for this archival release. Frozen scientific results are unchanged.

The addition includes author-created source and sanitized retained records.
It is not a verified one-command native reproduction environment. Read its
README for environment/path reconstruction limits and exact provenance hashes.

```text
python -B studies_route_a/verify_archive.py
```

This command checks only archived bytes and saved-result consistency. It does
not import or execute any study or repeat timing. Cite the v7.0.0 release for
these later materials, not v6.0.0. Earlier evidence below remains separately
bounded historical material and is not additional Route A independent evidence.

## Historical v6.0.0 description

The verification/install commands in this historical section apply to a v6.0.0
checkout, not to the updated v7.0.0 root metadata. For the current addition use
the read-only `studies_route_a/verify_archive.py` command above.

This release is the public software and evidence companion for the evolving lifecycle-aware metamorphic-testing study. Version 6.0.0 adds a sanitized, independently frozen SQLite transaction adapter and retained R3 evidence without rewriting the v3.0.0 parent results or the separately published v4.0.0 and v5.0.0 OpenSees extensions.

It extends the earlier finite-element and mutation artifacts with the complete JSS P5 evidence chain:

- P5B: a four-way adjudication contract (`PASS_INVARIANT`, `DETECT_LIFECYCLE_DRIFT`, `INVALID`, and `NOT_SUPPORTED`) exercised by 20 cases and 40 fresh-process runs;
- P5C: a 12-case fault-localization study using one frozen eight-candidate ontology for generic replay and full lifecycle evidence;
- P5D: a gated cost study with 18 cells, 36 unreported warm-ups, and 180 timed fresh processes.

The release preserves failed contracts and errata. It does not contain downloaded SQLite executables, temporary databases, Python caches, pilot outputs, the private Abaqus/UEL production project, unpublished production meshes, or long-window carbon-storage outputs.

## Directory map

```text
studies_jss_p5/
  P5B_four_way_adjudication/  adjudication API, adapters, tests, and formal results
  P5C_localization_v2/        common ontology, ranking code, tests, and formal results
  P5D_performance/            equivalence gates, timing runner, tests, and formal results
studies_r3_sqlite/             SQLite adapter, preregistration, conditional model, and retained R3 records
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
- GitHub v6.0.0 release: https://github.com/yqma7980/transactional-lifecycle-audit/releases/tag/v6.0.0
- Software version 6.0.0 DOI: https://doi.org/10.5281/zenodo.22285603
- Dataset version 6.0.0 DOI: https://doi.org/10.5281/zenodo.22288732
- Software concept DOI: https://doi.org/10.5281/zenodo.21536450
- Dataset concept DOI: https://doi.org/10.5281/zenodo.21536560

The stable concept DOIs resolve to the latest archived versions. Earlier v3.0.0, v4.0.0, and v5.0.0 records remain immutable and independently citable.

## Authors and funding

The v6.0.0 metadata lists Yangqi Ma, Weiji Sun, Bing Liang, Shi He, and Jianfeng Hao. Funding is acknowledged from the National Natural Science Foundation of China (Grant 52474038; recipient Weiji Sun) and the Liaoning Provincial Department of Education project (Grant LJ212410147066; recipient Jianfeng Hao).

## Licenses

Software is licensed under BSD-3-Clause. The separately archived numerical source data are licensed under CC BY 4.0.
