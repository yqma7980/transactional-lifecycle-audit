# JSS P5B implementation preflight

This additive package implements the P5A four-way verdict contract without
running the frozen 20-case matrix. The protected P5A inputs are snapshotted in
`00_frozen_inputs/P5A`; implementation code is under `src/jss_p5b`; and all
allowed QA is confined to `tests` and `qa`.

Formal execution remains unauthorized. No result produced by this package may
be labeled `OBSERVED-P5B` until a separately authorized formal protocol runs
the development and held-out partitions in the frozen order.
