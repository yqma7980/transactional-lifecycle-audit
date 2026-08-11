# P5B partition and held-out rule

## Fixed allocation

Development contains 16 cases. The held-out partition is:

- P5B-PASS-05
- P5B-DETECT-05
- P5B-INVALID-05
- P5B-NS-05

The allocation is stratified by expected verdict and fixed before adapter
implementation.

## Access rule

Held-out case parameters and expected observations may be read by the
authorization script only after:

1. all development duplicate pairs are frozen;
2. the adjudication implementation hash is frozen;
3. no development case is pending; and
4. a held-out activation manifest records those hashes.

There is no replacement rule. If a held-out case is not executable, disagrees
between repetitions, or produces an adverse verdict, that result is retained.

## Counting rule

The four-way verdict study reports all 20 cases. Detection metrics use only
eligible fault-bearing cases. Coverage and eligibility controls remain in the
verdict table but outside detection denominators.

