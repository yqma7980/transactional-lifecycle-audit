# Pre-native review findings and bounded repair

No formal native G4 process has run. The first reviewer snapshot and all failures
remain preserved. The parent copies of lcma_arm.py, g4_native.py and g4_config.py
are retained under harness/superseded_preflight01 before this repair.

## Transport correction, not core replacement

The first wrapper treated a list containing the two envelope key strings as a
missing-observation envelope, and inherited a type-equality loophole for a custom
non-JSON Python object. The wrapper now checks a plain-object envelope and validates
plain finite JSON values using explicit type identity, rejecting ancestor cycles.
The core and independently authored R02 rich baseline are byte-identical to their
prior versions. No property, native trigger/control, literal or diagnostic rule
has changed. The extra LCMA-side validation cost remains in measured evaluator
cost; it is not removed to improve the ratio.

## Retained capability failure

A finite acyclic Python object nested 1,500 levels deep causes the frozen core to
return ERROR through its wrapper, whereas the iterative rich baseline can return
INVARIANT. This is a real negative capacity result and remains in the reviewer
records. It is not reclassified as a successful test. No baseline depth cap or
core recursion change is added to manufacture parity. Arbitrary-depth finite-JSON
support is not claimed. The formal r79/r94 inputs are the fixed shallow whitelist
projections, supplied equally to both arms; depth and shape must be verified before
scoring. This case-bound comparison does not repair or validate the unrestricted
Python-object API. Any observed formal-input discrepancy is reported, not hidden.

## Operational root correction

The local copied capture helper only owns this new task root, whereas immutable
native drivers require their historical anchor's new run subtree. Native G4
dispatch now loads each anchor's original byte-identical capture helper by explicit
module path and checks both runner and launcher hashes. Its ownership guard is
not broadened or disabled. The new task's helper continues to own outer coordinator
and evaluator jobs. Only the two authorized fresh G4 subtrees may be appended.
One review guard probe omitted required cwd, producing a test-invocation failure;
that probe is not evidence of a native run. All old target source/runtime files
and failed attempts remain unchanged.
