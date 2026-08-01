# P5 F01 threshold-crossing postmortem

Status: `OBSERVED_NOT_SUPPORTED_DISTINCTIVE_REGION_EMPTY`

The frozen binary sweep first became nonquiet at index 5 and first reached `Z_family >= 10` at the same index 5. Index 4 remained conventionally quiet with `M_GP=5.68158e-11`, `M_R=6.06348e-13` and `Z_R=2.66675`. Index 5 produced `M_GP=4.54527e-10`, `M_R=4.85068e-12` and `Z_R=21.3335`, but its conventional gate had already failed.

A through-origin fit over indices 0--4 is retained only as a postmortem diagnostic. It places the `M_GP=1e-10` crossing at eta approximately 2.55758e-11 and the `M_R=10*T_R` crossing at eta approximately 5.45676e-11. This ordering is consistent with the observed empty distinctive region. The inferred values are not case selections and cannot authorize interpolation, an added strength or a changed gate.

Supported conclusion: under the frozen grid and history, F01 supplies an exact restoration violation but no region in which the secondary operator signal is separated while conventional outputs remain quiet.
