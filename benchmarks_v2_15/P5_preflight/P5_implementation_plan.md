# P5 implementation-preflight plan

Status target: `PASS_P5_IMPLEMENTATION_PREFLIGHT_READY_FOR_FULL_IMPLEMENTATION`

This package implements the frozen numerical contracts without installing or running a finite-element execution backend. The implementation consists of:

1. immutable freeze/hash and authorization checks;
2. metric-scaled fresh-process null-envelope calculations;
3. deterministic A/B/C/D arithmetic reduction paths;
4. exact F01/F02/F05/F07 development and held-out field bindings on synthetic state packets;
5. the complete-grid adjacent-level selector and fresh-process duplicate gate;
6. an independent `fractions.Fraction` oracle; and
7. a future runner that refuses to create results unless both authorization locks are present and still stops while the FE backend is absent.

Synthetic mutation tests establish implementation-contract wiring only. They are not DOLFINx results, formal P5 cases, detector evidence or manuscript evidence.
