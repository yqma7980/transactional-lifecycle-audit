# Route A: equal-information comparison and applicability boundaries

This directory supplements the public v6.0.0 archive with the retained evidence
for **Auditable Lifecycle Contracts for Stateful Software: Equal-Information
Comparisons and Applicability Boundaries**. It contains previously local records
from 7 September 2026, curated for public release on 23 September 2026.
Archival packaging is not a new experiment, a new validation, or a new result.

## What the evidence says

| Retained quantity | Django r79 | Celery r94 | Combined |
|---|---:|---:|---:|
| Historical defect lineages | 1 | 1 | 2 |
| Native observations | 12 | 12 | 24 |
| Evaluation processes | 4 | 4 | 8 |
| LCMA / strong-baseline detected manifestations | 3/3 vs 3/3 | 3/3 vs 3/3 | 6/6 vs 6/6 |
| LCMA / strong-baseline normal false positives | 0/9 vs 0/9 | 0/9 vs 0/9 | 0/18 vs 0/18 |
| LCMA / baseline pure-decision time ratio (rounded) | 2.171 | 2.164 | Not pooled |

LCMA is slower in these descriptive measurements. Equal observed detection is
not a population-level equivalence test. Failed-relation IDs agree; this does
not establish superior diagnosis, localization, maintenance, or reliability.
There are two defect lineages, not 24 independent defects. No human study or
production benefit was measured.

Click #412 remains `CONTRACT_BINDING_HOLD`. Trio #55 remains
`PROVENANCE_HOLD_NO_AUTHORITATIVE_FIX_FIRST_PARENT`. Neither case underwent an
admitted native transfer experiment. Two depth-1500 JSON failures per retained
normal/optimized preflight mode remain failures.

## Start here

1. Read `EVIDENCE_MAP.md` for claim-to-record mapping and final admission status.
2. Inspect `retained/g4/r079/methods/COMPARISON.json` and its r094 counterpart.
3. Inspect each `methods/input.json` and four saved `E01.json`--`E04.json` files.
   Both arms received the same byte-identical label-free input file.
4. Read the Click binding adjudication and the Trio candidate ledger/closure
   metadata. Historical intermediate statuses are not final transfer success.
5. Run only the read-only archival verification command below if desired.

```text
python -B studies_route_a/verify_archive.py
```

The verifier uses Python's standard library, hashes files, and checks saved
records. It does not import LCMA, Django, Celery, Click, or Trio; run evaluators;
start target processes; repeat timing; or perform a new experiment.

## Directory map

- `retained/core`, `retained/baseline/successors/R02_TYPED_JSON_20260907`,
  `retained/harness`: frozen core, selected independently authored strong
  baseline, projection, evaluation, and historical orchestration source.
- `retained/contracts`: declared relations and equal-information semantics.
- `retained/g4`: native outcomes, per-observation traces/specifications,
  shared arm inputs, saved arm outputs, comparisons and historical readbacks.
- `native_records`: sanitized original event traces and process records for all
  24 observations; no unobserved or synthetic observation is added.
- `evaluation_processes`: saved resource/process records for the eight arm processes.
- `native_source`: author-created adapters, native property recipes and Django fixture.
- `environment`: historical interpreter, exact upstream commits and dependency versions.
- `retained/heldout`: prespecified screening, provenance and semantic-admission records.
- `retained/review`: historical synthetic QA, including failed depth/runner checks.
- `upstream_metadata`: selected factual issue/closure metadata; not copied issue prose.
- `PROVENANCE_MANIFEST.json`: source identifiers, original/public hashes and transformations.

## Reproduction and privacy boundary

This is an **evidence-inspection and source archive**, not a certified one-command
cross-machine native reproduction environment. The core, selected baseline and
label-free method inputs are unchanged. Absolute workstation/user paths in other
records/source have been replaced by `LOCAL_WORKSPACE`, `LOCAL_USER` or
`LOCAL_PROGRAM_FILES`; internal original hashes remain historical identifiers
and must not be confused with hashes of sanitized public copies. The provenance
manifest provides both. Path aliases identify external historical locations,
not files guaranteed to be present in this directory.

Historical orchestrators contain host/runtime bindings and guards referring to
the original sealed files. They are retained for inspection, not advertised as
portable launch commands. No guards were weakened to make sanitized files pass.
Full upstream source trees, Python installations, binary dependencies, temporary
databases/caches, private engineering assets and unrelated manuscript files are
excluded. Reconstructing a native environment requires the exact upstream commits,
matching runtimes, path rebinding and a separately checked reproduction plan.
No such rerun was undertaken for this release; exact timing is machine-dependent.

Only filesystem-prefix substitutions, redaction of host executable-search PATH
strings, and explicitly documented metadata excerpts were made. Recorded
scientific numbers, outcomes, failed relations and timing
values were not changed. Original local records remain intact. Local hash seals
are provenance records, not trusted external timestamp attestations.

## License and citation

Author-created software uses the repository's BSD-3-Clause license. Author-derived
records and documentation use CC BY 4.0, as specified in `LICENSE_DATA.md`.
Upstream notices retain their original terms; upstream packages are not relicensed.
See `THIRD_PARTY_NOTICES.md`. Cite the version-specific v7.0.0 software/evidence
archive and identify this subdirectory. Do not cite v6.0.0 as containing these
later records. Older repository directories are historical background, not
additional Route A independent evidence.
