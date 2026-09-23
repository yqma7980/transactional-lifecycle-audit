# Independent Rich-Assertion Baseline R02

This authored baseline was implemented from the new task's
`governance/AUTHORIZED_SCOPE.md`, `contracts/COMPARISON_SEMANTICS.md`, and the
user's scoped task instructions only. R02 preserves the author's R01 files and makes the narrowly scoped change
recorded in `SOURCE_LINEAGE.md`. No frozen core, LCMA wrapper, generated
contract, prior LCMA outcome, target source, target runtime, or native result was
read or imported. The independence statement describes implementation inputs;
it is not an independent review or a claim of independent-human reproduction.

## API And Semantics

`rich_compare.py` exposes `evaluate79(trace)`, `evaluate94(trace)`, and
`normalized_evaluate(case, trace)`. The case argument must be the plain integer
79 or 94. The direct evaluators raise `TraceInputError` for malformed transport;
the normalized wrapper returns exactly `{"verdict":"ERROR","failed":[]}` for
exceptions or an invalid case. Ordinary scoring never uses Python `assert`.

The trace envelope must have exactly `context` and `samples`. All values,
including ignored extras, must be finite typed JSON. Plain null, bool, int,
float, str, list, and string-keyed dict values are accepted; subclasses,
unsupported objects, non-string keys, nonfinite floats, and cycles are rejected.
Integer and float are distinct, as are boolean and integer. Object key order is
irrelevant; list order matters. Shared acyclic containers are accepted. Validation
and equality are iterative and do not mutate input values.

Transport validation precedes scoring. Eligibility operands are resolved first,
then every relation operand in the prose order. Any missing path returns
`UNSUPPORTED`, ordered complete dot-separated `missing` paths, and `failed: []`.
This takes priority over mismatched eligibility or violated relations. Complete
eligibility mismatch returns `INVALID`, ordered `invalid` IDs, and `failed: []`.
Eligible violations return `DETECTED` with ordered `{id, obligation}` objects;
otherwise the result is `INVARIANT` with `failed: []`. No other keys are emitted.

A present terminal null or partial object is a value, not a missing operand.
Missing internal keys and extra internal keys therefore fail exact object
equality. Intermediate non-objects make descendant paths missing. Legal context
and samples extras outside fixed operand values are ignored for scoring.

The r79 six O3 checks and r94 five O5 checks are direct fixed comparisons. This
module does not load declarative rules or discover properties from target data.
Native grammar/provenance validation remains an external prerequisite for any
future method scoring; this API cannot establish native origin or eligibility
from source evidence.

## Bounded Self-Tests

Run the create-only coordinator with the specified interpreter:

```powershell
& 'LOCAL_USER/AppData\Local\Programs\Python\Python312\python.exe' -I -B `
  'LOCAL_WORKSPACE/M-2026-003_S10G4_S11_20260907_174304\baseline\successors\R02_TYPED_JSON_20260907\run_synthetic_tests.py'
```

The coordinator uses standard-library modules only. It launches sequential fresh
Python 3.12.10 test processes with `-I -B` and `-I -B -O`, a 180-second hard
timeout per child, captured stdout/stderr, exclusive run IDs, and create-only
artifacts below this successor's `runs/` directory. No target process is launched. Input files are
hashed before and after; common prose hashes must match the authored baseline's
locked inputs. All output streams are retained and checked against 16 MiB; this
post-run check is not an OS quota. The synthetic workload is deliberately bounded.

Tests enumerate all 64 r79 and 32 r94 eligible relation truth patterns and all
eight eligibility patterns per case. Other tests cover typed deep equality,
booleans versus integers, integer versus float, nested null versus missing,
ordered missing precedence, malformed envelopes, unsupported values, nonfinite
JSON decoding, cycles, aliases, deep acyclic values, exact relation values,
ignored legal extras, no mutation, fresh result containers, and hostile metaclass equality hooks. Plain type checks
use identity only; unsupported values cannot spoof membership in allowed types. The coordinator
compares complete recorded semantic reports across optimization modes, not just
exit codes or test counts. Test cases and expected outcomes are synthetic and
authored from the prose, not copied from comparator or target outcomes.

## Preservation And Scope

Manual artifacts are created via apply_patch only inside this baseline directory.
Execution-generated evidence is written create-only under exclusive baseline run
paths. There is no overwrite, cleanup, replay into an old run, or deletion. Any
future fix requires a successor source path and a new run identity; retain this
version and every failed artifact. Do not run this coordinator from a copied
location outside the authorized baseline tree without separate authorization.

This work does not run a G4 target, benchmark methods, inspect target sources,
perform projection/core/source review, download or install anything, score native
results, conduct human experiments, edit manuscripts, or publish. Other agents
own core/projection and independent source review. Passing author self-tests is
not independent review, target agreement, efficacy, generalization, production
benefit, or publication-readiness evidence. Stop after the final JSON handoff.
