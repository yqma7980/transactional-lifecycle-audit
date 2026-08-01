# L2-D0 data contract

Status: **DRAFT / NO DATA GENERATED**

## Required artifact families

1. design and source manifest;
2. event-level host lifecycle ledger;
3. accepted-checkpoint table;
4. analytical-reference table;
5. case-level decision table;
6. duplicate-run comparison;
7. runtime metrics marked reporting-only;
8. final claim-boundary report.

## Event-level ledger

The formal ledger must contain at least:

| Group | Required fields |
|---|---|
| Identity | design_version, run_id, case_id, implementation_hash, configuration_hash |
| Host | host_name, host_version, execution_mode, thread_count, job_id |
| Location | step_id, increment_id, attempt_id, iteration_id, call_index |
| Event | event, accepted_flag, reject_reason, cutback_flag, retry_parent_id |
| Time/load | total_time, step_time, dtime, requested_dtime_factor, load_factor, applied_force |
| Primary state | primary_state_hash, displacement, reaction |
| Committed state | committed_version_before, committed_version_after, committed_state_hash_before, committed_state_hash_after |
| Candidate state | candidate_id, candidate_state_hash, candidate_reachable_after |
| Persistent state | persistent_state_hash_before, persistent_state_hash_after, persistent_state_class |
| Operator | declared_packet_hash, residual_state_version, tangent_state_version, residual_hash, tangent_hash |
| Material | strain, stress, plastic_strain, hardening_history, algorithmic_modulus |
| Norms | residual_norm, tangent_norm, correction_norm |
| Output | output_event, output_source_version, output_accepted_flag |
| Validation | finite, event_valid, analytical_error, parity_error, note |

Field definitions, units, missing-value rules and hexadecimal serialization
must be frozen before D1 implementation.

## Accepted-checkpoint table

Each common checkpoint must record:

- case and history identifiers;
- accepted host time/load;
- accepted primary-state hash;
- accepted committed-history hash;
- displacement, reaction, stress, plastic strain and hardening history;
- residual norm;
- source implementation and tangent schedule;
- whether the checkpoint followed direct, retry or callback-perturbed history;
- exact and normalized differences from the reference checkpoint.

Only accepted rows may appear in this table.

## Case-level decision table

Required fields:

- case_id;
- expected_classification;
- observed_classification;
- analytical gate;
- lifecycle gate;
- operator-version gate;
- accepted-field parity gate;
- output-provenance gate;
- finite gate;
- reproducibility gate;
- hard_gate_failed;
- passed;
- interpretation boundary.

## Hashing and provenance

- Source, input, environment and output hashes use SHA-256.
- State fingerprints must serialize fields in a documented fixed order.
- Exact equality and tolerance equality are separate columns.
- Terminal or rollback-only calls must be labelled and cannot be mixed with
