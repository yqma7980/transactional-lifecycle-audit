# Pre-formal common information and comparison semantics

Known historical projects r79/r94 are not heldout. The unchanged generic core is
frozen in governance/CORE_AND_SCOPE_FREEZE.json. No target G4 execution yet.

## Transport and precedence (both independent arms)

`trace` has exactly context and samples. Only finite, typed JSON values are legal;
booleans are distinct from integers; lists are ordered and object key order is not
significant. Unsupported Python objects and invalid envelopes return ERROR in a
transport wrapper, not a product detection. Context/samples may be arbitrary JSON
in synthetic checks: a missing path is UNSUPPORTED, not silent defaulting.

Resolve all eligibility operands first and all relation operands in the listed
order. Missing paths take precedence over eligibility mismatch. UNSUPPORTED has
ordered `missing` path list and empty failed. Complete eligibility mismatch returns
INVALID, ordered `invalid` IDs and empty failed. Otherwise failed relations return
DETECTED with ordered {id,obligation}; none returns INVARIANT with failed=[].
ERROR normalization is {verdict:ERROR,failed:[]} without arm-specific exception names.

An explicitly present null/object with missing internal keys is compared as a
value at the specified operand path, not silently converted or treated as absent.
Extra context/samples keys not in the fixed rule set are ignored by both arms.

## r79 association restoration

Context (declared from the already audited producer, not inferred hidden state):
protocol_id=G4-ASSOCIATION-RESTORE-1
observation_point=post_restore_property_window
observation_order=[file_equal,name,url,storage,instance,field]

Eligibility IDs protocol_matches,point_matches,order_matches compare these context
fields with the exact literals, in that order.

Six relation operands in that same attribute order:
samples.checks.<attribute> equals {status:VALUE,equal:true}.
Relation ID `restored_<attribute>` and obligation O3 for each.

Projection copies only status/equal from each original PROPERTY_CHECK:<attribute>
event, after external typed native-grammar/provenance validation. It does not read
native_outcome, pass flags, source side, trigger label, traceback, version, PID,
filesystem location or the native evaluator's derived observation dictionary.
`equal` is an existing primitive native equality measurement; this study does not
claim to invent that oracle. ATTRIBUTE_ERROR with equal=null is a present measured
relation violation if the independent source-origin gate accepts it, not a missing
measurement. Unknown/unresolved native origins stop method scoring for that row.

## r94 pending callback completion

Context:
protocol_id=G4-PENDING-CALLBACK-1
observation_point=immediate_native_exit_before_cleanup
observation_order=[pending_after,pending_ids_after,callback_receipts,callback_counts,callback_enter_return_balance]

Same three eligibility IDs in the same order. Relations are O5:

| ID | sample path (below samples) | literal |
| --- | --- | --- |
| pending_count_empty | pending_after | 0 (integer) |
| pending_ids_empty | pending_ids_after | [] |
| receipt_order | callback_receipts | [op_b,op_a] |
| callback_once | callback_counts | {op_a:1,op_b:1} |
| callback_balanced | callback_enter_return_balance | {op_a:[1,1],op_b:[1,1]} |

Projection copies these five raw TERMINAL_SNAPSHOT fields after external native
grammar/provenance checks. No precomputed verdict, signature, native-exit label,
source/history, file path, PID, timing or per-side label enters either method.
An extra legal empty perform scan is not a callback duplicate.

## Formal design and interpretation

Each root: two sources x two histories x three fresh target processes, not pilot
reuse. Fixed order per repetition:
1 before-trigger,after-control,after-trigger,before-control;
2 after-trigger,before-control,before-trigger,after-control;
3 before-control,after-trigger,after-control,before-trigger.
Process IDs are ordinal G4_Rxxx_001..012. Same raw input list for both methods.
Two fresh processes per method, order LCMA,rich,rich,LCMA for each root.
Microbenchmark:20 warmup rounds;7 batches;100 evaluations per trace per batch.
Report median amortized per-evaluation times; no human or production inference.

Native references qualify the common property independently of both comparators.
Compare detected/missed native violations, false alarms on native-satisfied rows,
unsupported/error counts, failed relation IDs, and elapsed/CPU/memory costs.
Repeated rows are not independent bugs. No population sensitivity/specificity
confidence claims from these two known roots. Diagnostic relation IDs do not prove
root-cause localization. Identical detection and additional overhead are valid.

The rich arm must be independently coded without importing the core, LCMA wrapper,
generated declarative contracts, LCMA outcomes or old expected native labels. It
can use common JSON loading/finite transport specifications and this prose only.
No baseline output may be read by the LCMA evaluator. Frozen shared input hashes
and independent tests/review precede formal execution.
