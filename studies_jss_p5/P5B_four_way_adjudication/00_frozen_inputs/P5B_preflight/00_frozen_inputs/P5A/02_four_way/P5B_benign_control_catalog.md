# P5B benign-control catalog

The five controls are legal lifecycle variations, not merely fault-free direct
runs.

| Case | Legal variation | Why it should remain quiet |
|---|---|---|
| P5B-PASS-01 | Declared and version-compatible tangent lag | Different iteration path is allowed when the operator-version relation is explicit and accepted fields meet the frozen relation. |
| P5B-PASS-02 | Diagnostic-only persistent counter | The counter is owned by diagnostics and excluded from the semantic persistent-state projection and every physical operator. |
| P5B-PASS-03 | Extra nonaccepting callback evaluations | Extra calls are legal when each trial is reconstructed from committed state and no callback-owned state has a reverse path into physics. |
| P5B-PASS-04 | Legitimate checkpoint/restart | The restart is written from an accepted state and restores the same authoritative committed packet before continuation. |
| P5B-PASS-05 | Output generated after commit | Output is legal when its source candidate is accepted and the commit-reachability record is complete. |

## Pass gate

A benign control passes only when it is observable, eligible, finite, and
invariant under its declared relation. A quiet numerical result cannot override
an ownership, version, or provenance violation.

Five quiet controls permit only finite-sample counts and exact intervals. They
do not establish a population false-positive rate.

