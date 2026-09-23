# Click 412 Binding Adjudication

**Verdict: CONTRACT_BINDING_HOLD. No successor contract is issued.**
This is source-author adjudication, not an independent review or native result.
The original unsupported obligation tag is an adapter-construction error, not
proof of generic-core breakage. The original packet remains unchanged.

## Semantic Finding
The exact property requires the cleanup callback to retain access to its active
Context and object token, followed by context removal after cleanup.

- **O1 does not establish this property.** Its requirement is a sole authoritative
  committed owner of declared persistent fields, not current-context lookup
  availability. The sealed identity/token observations do not establish that
  ownership role or distinguish lost lookup from changed ownership.
  [O1 definition](F:/Abaqus%20learning/code%20learning/M-2026-003_S08_EXECUTION_20260905/manuscript/source/main_s08.tex#L141).
- **O2 does not establish this property.** There is no declared non-accepting
  evaluation and pre/post authoritative C/P preservation relation. Matching the
  table's words "callback-order-dependent mutation" without its required relation
  would be a semantic relabel, not a narrow binding.
  [O2 definition](F:/Abaqus%20learning/code%20learning/M-2026-003_S08_EXECUTION_20260905/manuscript/source/main_s08.tex#L142).
- **O3 cannot cover the whole sealed property.** Post-scope absence resembles an
  empty-entry restoration endpoint, but does not entail that cleanup preceded
  restoration. Even granting that endpoint analogy, the two callback-time
  relations remain unbound. The sealed source expectations predict this endpoint
  true on both revisions; that is not a native result. Removing the callback
  relations would change the property and weaken the unchanged rich comparison.
  [O3 definition](F:/Abaqus%20learning/code%20learning/M-2026-003_S08_EXECUTION_20260905/manuscript/source/main_s08.tex#L143).

The partial bindings in s06_methods.tex retain real shared-state preservation
(O2) or restoration (O3) predicates. They do not license arbitrary lifecycle
relations under those names. A literal native commit/reject API is **not** required,
so its absence alone is not the rejection reason. The missing correspondence is
semantic: authoritative roles, entry relation and event meaning for this exact
callback-lifetime property.
[Partial-binding limits](F:/Abaqus%20learning/code%20learning/M-2026-003_S08_EXECUTION_20260905/manuscript/source/s06_methods.tex#L10),
[restricted relations](F:/Abaqus%20learning/code%20learning/M-2026-003_S08_EXECUTION_20260905/manuscript/source/s06_methods.tex#L6).

## Disposition
No O1/O2/O3 relabel, invented rollback/commit, relation deletion, or new semantic
obligation is adopted. Treating lifetime/availability or teardown ordering as an
additional obligation would require a separately governed semantic scope extension;
this adjudication does not establish that core implementation changes are needed.
Historical fix authority remains intact and separate from contract admissibility.

BINDING_ADJUDICATION.json records the source hashes, exact original artifact hashes,
and per-obligation reasoning. The original contract, fixture, baseline, protocol and
stored QA match their original packet entries. Core was neither read nor hashed.
No source query, target import, native call or result rewrite occurred. The original
nonauthor HOLD remains; this record grants no native release.

