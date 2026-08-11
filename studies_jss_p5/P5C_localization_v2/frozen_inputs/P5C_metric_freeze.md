# P5C localization metric freeze

## Analysis population

Only eligible, active, detected P5C fault cases with duplicate agreement and
schema-conformant B3 and B6 rankings enter localization metrics. Every excluded
case remains listed with its predeclared reason.

## Primary endpoint

suspicious_set_reduction = 1 - size(S_B6) / size(S_B3)

Report every paired value and the median with a 95 percent bootstrap confidence
interval using 10000 resamples and seed 20260811.

## Secondary endpoints

- Top-1 and Top-3 exact ground-truth hit;
- reciprocal rank and mean reciprocal rank;
- EXAM = rank of first true candidate divided by 8;
- suspicious-set size;
- owner, event, and source-plane agreement as descriptive decompositions.

If a fault has more than one legitimate ground-truth candidate, all valid IDs
must be frozen before execution and the first ranked valid ID defines reciprocal
rank and EXAM.

## Paired analysis

Compare B3 and B6 only on identical cases. Use an exact paired permutation test
for suspicious-set reduction and report the paired rank-biserial effect size.
Holm correction applies if more than one inferential localization family is
reported.

Null or adverse results are retained. No superiority wording is allowed unless
the frozen endpoint supports it.

