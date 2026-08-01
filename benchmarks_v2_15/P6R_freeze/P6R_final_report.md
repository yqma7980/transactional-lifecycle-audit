# P6R F05/F07 bounded same-fault comparison freeze

Final status: `PASS_P6R_F05_F07_BOUNDED_SAME_FAULT_COMPARISON_FREEZE`

The independent static study `P6R-F05-F07.0` binds the only two P5 families with valid fresh-process strength pairs, F05 and F07, plus one null-control pair. It reuses five cases and ten immutable raw runs; no FE rerun is allowed.

Four projections can be reconstructed fairly: final-state regression, operator-version consistency, equal-input metamorphic replay and full lifecycle-ledger audit. Checkpoint comparison and component-level state fingerprinting remain explicit evidence gaps rather than being dropped or retrofitted.

A later PASS may compare information yield and causal localization only for F05/F07. It cannot establish full P3/P5/P6, general detector performance or production validity. The next permissible task is a separately authorized `P6R_IMPLEMENTATION_PREFLIGHT`; it must not execute the ten projection jobs automatically.
