# L2-D0 host-lifecycle benchmark specification

**Design version:** L2-D0.1  
**Date:** 2026-07-21  
**Status:** Draft design; no source code, deck, compilation or solve authorized.

## Primary question

Given one accepted host state, does a minimal path-dependent finite element
return the same residual-state fingerprint and reach the same accepted
checkpoint after a forced retry, changed callback count or declared tangent
path, provided that all declared physical inputs and residual definitions are
the same?

## What L2 adds beyond L1

L1 prescribes material and element packets directly and contains no global
nonlinear solve. L2 adds:

- a host-managed accepted state;
- global Newton iterations;
- at least one forced rejected attempt and retry;
- host call events and accepted-field checkpoints;
- exact versus declared lagged tangent histories with one frozen residual;
- an optional scheduling envelope where the selected host supports it.

## Minimal physical object

The primary object is a force-controlled, two-node, one-integration-point
axial bar:

- area A = 1;
- length L = 1;
- node 1 fixed;
- one displacement degree of freedom at node 2;
- the L1 linear-hardening elastoplastic update;
- residual R = A sigma - F;
- consistent element tangent K = A E_alg / L.

The global object is deliberately minimal. It must be implemented independently
and must not import, copy or adapt the production two-phase UEL.

An optional scheduling case may use a short bar assembled from identical
elements only after the one-element lifecycle gates pass.

## State ownership

The formal implementation must distinguish:

1. host primary state;
2. host-managed committed material history;
3. call-local trial material and element state;
4. returned candidate history;
5. accepted output state;
6. algorithmic controls such as requested time-step reduction;
7. diagnostic-only state;
8. seeded unsafe persistent state used only in negative controls.

No diagnostic or output field may enter the physical residual.

## Compared implementations

| Variant | Intended role |
|---|---|
| safe_local | Reconstruct every trial from declared primary and committed state. |
| safe_transactional | Return a candidate for host accept/discard without premature commit. |
| unsafe_trial_cache | Deliberately retain rejected trial history outside host rollback. |
| unsafe_output_feedback | Deliberately feed a diagnostic/output mirror into later physics. |
| seeded_version_mismatch | Deliberately label residual and tangent with different state versions; reject before interpretation. |

Unsafe variants are detection controls, not candidate production methods.

## Lifecycle histories

### Direct history

Advance from the accepted base to the target checkpoint without an inserted
retry. This is the same-track reference.

### Forced-retry history

After at least one candidate has been formed, request or induce rejection of
the current attempt without accepting its candidate. Retry from the same
accepted base at a smaller declared increment and continue to the common target
checkpoint.

### Extra-callback history

Insert one or more non-accepting residual/tangent evaluations at an identical
declared packet before the accepted path. The insertion must not change the
physical state of safe variants.

### Tangent-path history

Compare exact and explicitly lagged tangent schedules while keeping the
residual definition, boundary loading, material law and accepted target fixed.
This test evaluates accepted-field parity, not iteration-count identity.

### Output and checkpoint histories

Output may read only an accepted state. A serialized accepted checkpoint must
round-trip without changing its authoritative state hash. This checkpoint test
does not substitute for a host restart test.

## Required comparisons

- analytical accepted solution where available;
- direct versus forced-retry residual-state replay;
- direct versus extra-callback replay;
- exact versus lagged tangent accepted-field parity;
- safe versus seeded-unsafe discrimination;
- residual and tangent state-version compatibility;
