# P5C localization access contract

Version: JSS-P5C-ACCESS-1.0

## Common output contract

For a subject, B3 and B6 must each return a complete ordered permutation of the
same eight candidate IDs in P5C_candidate_ontology.csv. Each row contains:

- candidate_id;
- integer rank from 1 through 8;
- numeric score;
- method_id;
- case_id; and
- a method-visible reason code.

No semantic tuple, free-text path, module name, or newly generated ID may
replace a candidate ID. Duplicate or missing IDs fail schema conformance.

## B3 generic-replay access plane

B3 may read:

- the subject ID;
- the two declared replay packets;
- residual, tangent, accepted-field, and output deltas;
- static ontology fields field_or_packet and semantic_role.

B3 may not read runtime owner, event, reachability, restoration, checkpoint, or
output-source provenance.

B3 scoring is frozen:

- +2 if semantic_role matches an observed changed artifact class;
- +1 if field_or_packet matches the changed packet family;
- 0 otherwise.

## B6 lifecycle-ledger access plane

B6 may read every B3 field plus observed lifecycle-ledger records: state owner,
event type, field or packet, restoration, candidate reachability, operator
versions, checkpoint stage, and semantic output source.

B6 scoring is frozen:

- +4 for an observed anomalous owner match;
- +2 for an observed anomalous event match;
- +2 for an observed anomalous source-plane match;
- +1 for an observed field or packet match;
- +1 for a relevant reachability, restoration, or version-relation anomaly.

Ground-truth candidate IDs are unavailable to both scoring implementations and
are read only by the evaluator after rankings are frozen.

## Tie and suspicious-set rules

- Higher score ranks first.
- Ties are broken by ascending candidate_id.
- The suspicious set is every positive-score candidate.
- If all scores are zero, the suspicious set is the complete eight-candidate
  universe.

## Hard failure

If either method fails to emit the exact common universe, the case is
NOT_EVALUABLE_SCHEMA_CONTRACT for RQ3. No post-hoc alias, tuple parsing, or ID
mapping is permitted.

