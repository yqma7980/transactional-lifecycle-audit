# P4d.5b accepted-output CSV schema contract

Status: `FROZEN_ERRATUM_NOT_IMPLEMENTED`

## Defect

P4d.2 inferred CSV columns from the first accepted row. The seeded rejected-output row additionally contains `source_load_factor`, so `csv.DictWriter(..., extrasaction="raise")` stopped before a formal result could be written.

## Sole correction

The CSV field order is fixed to the following 18 columns:

```text
accepted_index, accepted_load_factor, accepted_version, selected_candidate_id, primary_vector_hash, committed_gamma_p_hash, committed_alpha_hash, residual_norm, top_reaction, bottom_reaction, max_alpha, plastic_point_count, mesh_hash, material_hash, residual_version, tangent_relation, source_event, source_load_factor
```

Accepted rows write an empty `source_load_factor`; the rejected-trial row preserves its numeric source load. Unknown fields still raise. The in-memory row dictionaries and their canonical `rows_sha256` are unchanged.

## Scientific boundary

This erratum changes no FE equation, material update, history, state ownership, solver option, threshold, oracle, event order, verdict, or prior evidence. A successful rerun can close only `P4D-NC-OUTPUT-01`; it cannot establish native rejected line-search coverage or a complete P4d matrix pass.

Freeze SHA-256: `2b90c6d23404b2dd935d11ca0512810059cc2920ef0ed462c03d95142a3a15de`
