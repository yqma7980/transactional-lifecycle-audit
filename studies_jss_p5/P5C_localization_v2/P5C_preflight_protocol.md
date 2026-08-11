# P5C implementation preflight

The preflight verifies the frozen matrix and ontology hashes, the exact
eight-candidate universe, ground-truth isolation from both scorers, deterministic
tie breaking, authorization locks, held-out isolation, finite rankings, and
import behavior.

Passing this preflight authorizes only the nine development cases. The three
held-out cases remain locked until development duplicate and schema gates are
frozen in P5C_development_summary.json.
