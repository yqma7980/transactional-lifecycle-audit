from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AdapterOutcome:
    subject_id: str
    case_id: str
    run_id: str
    direct_operator: tuple[float, ...]
    perturbed_operator: tuple[float, ...]
    direct_accepted: tuple[float, ...]
    perturbed_accepted: tuple[float, ...]
    direct_hash: str
    perturbed_hash: str
    committed_before_hash: str
    committed_after_trial_hash: str
    persistent_before_hash: str
    persistent_after_hash: str
    finite: bool
    converged: bool
    accuracy_error: float
    balance_error: float
    checkpoint_applicable: bool
    checkpoint_parity: bool
    checkpoint_stage: str
    checkpoint_field: str
    operator_versions_compatible: bool
    committed_state_mutated_before_accept: bool
    accepted_output_provenance_violation: bool
    operator_version_incompatibility: bool
    rejected_candidate_unreachable: bool
    all_outputs_after_commit: bool
    owner_field_observed: bool
    activation_event_observed: bool
    restoration_failure_observed: bool
    output_reachability_observed: bool
    first_drift_after_mutation: bool
    events: tuple[dict[str, Any], ...]
    diagnostics: dict[str, Any]

