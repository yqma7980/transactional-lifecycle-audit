# P4d.4 acceptance gates

## Exploratory diagnostic gates

- Frozen image, mesh, material, cyclic reload state, PETSc types, tolerances, and observer are unchanged.
- Positive SNES reason.
- At least one structured unselected candidate.
- Complete exact C-to-Python candidate correlation.
- Post-check change flags remain false.
- All values finite.
- Free-DOF equilibrium, reaction balance, alpha bounds, and yield-consistency gates pass.
- Each diagnostic is labeled EXPLORATORY_NOT_FORMAL_EVIDENCE.

## Held-out formal gates

- Target is selected only by the predeclared mapping.
- Exact-current direct and declared-lag histories share the same declared source state and target load.
- Each history has two fresh-process repetitions with semantic duplicate equality.
- Native unselected candidate evidence is structured and correlated.
- Accepted output is post-commit and rejected candidates are unreachable.
- Mechanics, finite, operator-version, and lifecycle gates pass.

## Prohibitions

No diagnostic threshold tuning, line-search option change, material or mesh change, extra target, retrospective selection, or reuse of exploratory runs as formal evidence is allowed.
