# R02 Authored Successor

R01 remains byte-for-byte preserved at the baseline root, with its exclusive run
SYNTHETIC_RICH_R01_20260907T095911Z_a7a46c57f1cc4f718b2dac5d1c452a9e.
Both R01 processes passed 35 authored tests and 388 recorded behavior checks per
process. Those tests did not cover user-defined metaclasses spoofing type equality.

Author self-inspection found that tuple-membership checks on type objects can
invoke a metaclass equality hook. An unsupported Python object could consequently
be treated as an allowed scalar when it appears in an ignored extra field. This
violates the finite typed JSON transport boundary; it is not a target defect.

R02 replaces only the two allowed-type membership expressions with explicit
identity checks. The fixed operands, literal values, eligibility, missing
precedence, equality, relations, and result normalization are unchanged. Three
new unittest methods exercise spoofing and exploding metaclasses, validate that
no user type-equality hook is called, and reject a spoofed integer case argument.

The R02 runner is adjusted only for its successor directory, lock path labels,
new version prefix, and this lineage record. The root implementation is retained
for audit history, not selected for delivery. The task-level
INDEPENDENT_BASELINE_HANDOFF.json selects this successor's rich_compare.py.

No forbidden core, wrapper, generated contract, prior LCMA outcome, target source,
target runtime, or native result was accessed to make this fix. This is still
author self-work, not independent nonauthor review.
