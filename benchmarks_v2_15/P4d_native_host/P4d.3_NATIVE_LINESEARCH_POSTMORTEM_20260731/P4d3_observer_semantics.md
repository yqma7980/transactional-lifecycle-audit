# P4d.3 observer semantics

## Conclusion

The PETSc C bridge is capable of distinguishing a full-step line-search candidate from the selected work vector. The missing rejected candidate in P4D-SAFE-LS-01 is attributed to the frozen history not triggering backtracking, not to an observer-API limitation.

## Read-only attachment

- SNESLineSearchMonitorSet records LINE_SEARCH_CANDIDATE before selection.
- SNESLineSearchSetPostCheck records LINE_SEARCH_SELECTED after selection.
- SNESLineSearchGetVecs, GetLambda, and GetReason read X/F/Y/W/G, lambda, and reason.
- changed_direction and changed_work are always set to PETSC_FALSE.
- The bridge does not change vectors, solver options, material state, lambda, or reason.

## P4D-SAFE-LS-01

- Candidate/selected pairs: 29.
- Candidate and selected lambda equal one: True.
- Exact X/F/Y/W/G equality for all pairs: True.
- Exact C-to-Python primary-vector correlations: 29/29.
- Structured unselected candidates: 0.

## P4d.1 zero-case comparison

- Candidate/selected pairs: 5.
- Structured unselected candidates: 1.
- This prior zero case includes a full-step candidate followed by a selected backtracked state, demonstrating the required public-interface observability.

## Boundary

This is a read-only postmortem. It does not convert the raw contract failure into a formal pass and does not establish complete P4d matrix support.
