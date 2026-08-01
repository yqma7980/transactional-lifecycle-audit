# P6R method-projection contract

Each future projection process reads one immutable P5 run and emits six method cells without invoking FE code. The paired raw run is processed in a separate single-process job.

| Method | Authorized projection | Forbidden shortcut |
|---|---|---|
| `M1_FINAL` | accepted output, finite/convergence flags, frozen metrics | event, mutation and owner fields |
| `M2_CKPT` | real checkpoint payload and post-restart accepted state | ordinary output as a checkpoint substitute |
| `M3_STATE` | predeclared per-component state hashes | P5 superset hash or `field_binding` fallback |
| `M4_OPERATOR` | residual/tangent versions and compatibility relation | numeric replay drift and callback history |
| `M5_META` | equal-input operator/candidate replay packets | owner, event, restoration and provenance |
| `M6_TLA` | owner/event/restoration/reachability/version/source ledger | ground-truth labels during detection |

`family_id`, `expected_lifecycle_verdict`, selection status and expected classification are post-run oracle fields only. A baseline success is retained. Not-applicable methods are excluded from every denominator.
