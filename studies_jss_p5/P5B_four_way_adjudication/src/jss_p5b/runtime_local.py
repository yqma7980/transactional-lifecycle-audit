from __future__ import annotations

from dataclasses import asdict
import inspect
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
for _path in (ROOT, ROOT / "00_runtime_dependencies"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from benchmarks.L4_two_phase_displacement.src.l4_fv import make_candidate
from benchmarks.L4_two_phase_displacement.src.l4_state import TwoPhaseModel, initial_state
from benchmarks.L6_external_host.src.l6_scipy_adapter import ScipyLifecycleAdapter
from benchmarks.L6_external_host.src.l6_state import CommittedState as ScipyCommittedState
from jss_p22.common import CaseSpec as LegacyCaseSpec
from jss_p22.s02_adapter import execute as execute_s02

from .cases import CaseSpec
from .model import PrecomparisonRelation
from .runtime import (
    RuntimeRecord,
    assert_finite,
    max_abs_delta,
    raw_observation,
    replay_packet,
    runtime_environment,
    semantic_hash,
)


ETA_LOW = 1.0e-10
L4_REPLAY_DT = 0.005
S03_CALLBACKS = (0.03, -0.03)


def _legacy_spec(case: CaseSpec, fault_id: str, strength_id: str = "CONTROL") -> LegacyCaseSpec:
    return LegacyCaseSpec(
        case_id=case.case_id,
        canonical_identity=f"P5B1|{case.case_id}|{fault_id}",
        effective_partition="DEVELOPMENT",
        subject_id=case.subject_id,
        fault_id=fault_id,
        site_id="P5B1-FROZEN",
        strength_id=strength_id,
        history_id=f"P5B1-{case.history_a}-{case.history_b}",
        control_id="P5B1",
        category="P5B1_RUNTIME",
        applicable=True,
        eligible=True,
        expected_verdict=case.target_verdict.value,
        ground_truth_owner="FROZEN_SUBJECT",
        ground_truth_module="P5B1_RUNTIME",
        ground_truth_event=case.fault_or_control,
        ground_truth_field=case.required_observable,
        ground_truth_source_plane="FROZEN_RUNTIME",
    )


def _l4_packet(
    *,
    primary: Any,
    committed: Any,
    tangent_version: str = "L4-FV-K1",
) -> Any:
    return replay_packet(
        primary=primary,
        committed=committed,
        persistent={"feedback": 0.0, "callback_bias": 0.0},
        load={"dt": L4_REPLAY_DT, "boundary": "L4-FROZEN"},
        residual_version="L4-FV-R1",
        tangent_version=tangent_version,
        environment={"subject": "JSS-S02", "backend": "L4-FV"},
    )


def _s02_record(case: CaseSpec, run_id: str, runtime_mode: str) -> RuntimeRecord:
    model = TwoPhaseModel()
    committed = initial_state(32)
    candidate = make_candidate(model, committed, L4_REPLAY_DT, attempt_id="P5B1-PACKET")
    base_primary = {
        "saturation_n": candidate.saturation_n,
        "time": candidate.time,
    }
    base_committed = {
        "fingerprint": committed.fingerprint,
        "model": model.fingerprint,
    }
    environment = runtime_environment(
        "JSS-S02", backend={"name": "L4 finite-volume subject", "cells": 32}
    )

    if case.case_id == "P5B-PASS-01":
        outcome = execute_s02(_legacy_spec(case, "BENIGN-01"), run_id)
        packet_a = _l4_packet(primary=base_primary, committed=base_committed)
        packet_b = _l4_packet(
            primary=base_primary,
            committed=base_committed,
            tangent_version="L4-FV-K1-DECLARED-LAG",
        )
        accepted_delta = max_abs_delta(outcome.direct_accepted, outcome.perturbed_accepted)
        if accepted_delta != 0.0 or not outcome.finite or not outcome.converged:
            raise RuntimeError("declared-lag control lost accepted-field parity")
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.COMPATIBLE,
            evidence_tokens=("OPERATOR_PACKET_VERSIONS",),
        )
        measurements = {
            "accepted_field_delta": accepted_delta,
            "operator_delta": max_abs_delta(outcome.direct_operator, outcome.perturbed_operator),
            "finite": outcome.finite,
            "converged": outcome.converged,
            "declared_relation": "DECLARED_VERSIONED_TANGENT_LAG",
        }
        events = tuple(outcome.events)
    elif case.case_id == "P5B-DETECT-02":
        outcome = execute_s02(_legacy_spec(case, "F05", "ETA-LOW"), run_id)
        packet_a = _l4_packet(primary=base_primary, committed=base_committed)
        packet_b = packet_a
        drift = max_abs_delta(outcome.direct_operator, outcome.perturbed_operator)
        if drift <= 0.0 or not outcome.accepted_output_provenance_violation:
            raise RuntimeError("F05 output-feedback route did not activate")
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.COMPATIBLE,
            evidence_tokens=("LATER_OPERATOR", "OUTPUT_SOURCE"),
            signal_names=("operator_replay_drift", "output_provenance_violation"),
        )
        measurements = {
            "operator_replay_drift": drift,
            "accepted_field_delta": max_abs_delta(outcome.direct_accepted, outcome.perturbed_accepted),
            "output_provenance_violation": True,
            "finite": outcome.finite,
            "converged": outcome.converged,
            "seed_strength": ETA_LOW,
            "diagnostics": outcome.diagnostics,
        }
        events = tuple(outcome.events)
    elif case.case_id == "P5B-DETECT-04":
        outcome = execute_s02(_legacy_spec(case, "F08", "CONTROL"), run_id)
        packet_a = _l4_packet(primary=base_primary, committed=base_committed)
        packet_b = packet_a
        if not outcome.operator_version_incompatibility or outcome.operator_versions_compatible:
            raise RuntimeError("F08 within-history version guard did not activate")
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.COMPATIBLE,
            evidence_tokens=("WITHIN_HISTORY_OPERATOR_VERSIONS",),
            signal_names=("within_history_version_violation",),
        )
        measurements = {
            "operator_packet_values_finite": outcome.finite,
            "within_history_versions_compatible": False,
            "rejected_before_commit_and_output": True,
            "operator_delta": max_abs_delta(outcome.direct_operator, outcome.perturbed_operator),
        }
        events = tuple(outcome.events)
    elif case.case_id == "P5B-INVALID-01":
        alternate = dict(base_primary)
        saturation = list(candidate.saturation_n)
        saturation[0] = float(saturation[0]) + 1.0e-6
        alternate["saturation_n"] = tuple(saturation)
        packet_a = _l4_packet(primary=base_primary, committed=base_committed)
        packet_b = _l4_packet(primary=alternate, committed=base_committed)
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.INCOMPATIBLE,
            evidence_tokens=("PRIMARY_STATE_FINGERPRINTS",),
        )
        measurements = {
            "primary_state_equal": False,
            "lifecycle_not_evaluated": True,
            "alternate_delta": 1.0e-6,
        }
        events = (
            {"event_type": "PrecomparisonPacketAudit", "field_name": "primary_state_hash"},
        )
    elif case.case_id == "P5B-INVALID-04":
        packet_a = _l4_packet(primary=base_primary, committed=base_committed)
        packet_b = _l4_packet(
            primary=base_primary,
            committed=base_committed,
            tangent_version="L4-FV-K1-PRE-REPLAY-STALE",
        )
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.INCOMPATIBLE,
            evidence_tokens=("PRE_REPLAY_OPERATOR_VERSIONS",),
        )
        measurements = {
            "pre_replay_version_compatible": False,
            "lifecycle_not_evaluated": True,
        }
        events = (
            {"event_type": "PrecomparisonVersionAudit", "field_name": "tangent_version"},
        )
    elif case.case_id == "P5B-NS-03":
        packet_a = _l4_packet(primary=base_primary, committed=base_committed)
        packet_b = packet_a
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.NOT_EVALUATED,
            evidence_tokens=(),
        )
        measurements = {
            "native_nonlinear_host_present": False,
            "native_rejected_linesearch_event_exposed": False,
            "audited_subject_type": type(model).__name__,
        }
        events = (
            {
                "event_type": "StaticCapabilityAudit",
                "missing_event": "NATIVE_REJECTED_LINESEARCH_EVENT",
            },
        )
    else:
        raise ValueError(f"unsupported S02 development case: {case.case_id}")

    return RuntimeRecord(
        case_id=case.case_id,
        run_id=run_id,
        subject_id=case.subject_id,
        runtime_mode=runtime_mode,
        raw=raw,
        events=events,
        measurements=measurements,
        environment=environment,
    )


def _scipy_run(path_id: str, variant: str, *, extra_callbacks: bool = False):
    import numpy as np

    adapter = ScipyLifecycleAdapter(path_id=path_id, variant=variant)
    injected: list[dict[str, Any]] = []
    if extra_callbacks:
        for ordinal, value in enumerate(S03_CALLBACKS, start=1):
            before = adapter.persistent.fingerprint
            residual = float(adapter.fun(np.array([value], dtype=float))[0])
            injected.append(
                {
                    "event_type": "ExtraNonacceptingResidual",
                    "ordinal": ordinal,
                    "x": value,
                    "residual": residual,
                    "persistent_before_fingerprint": before,
                    "persistent_after_fingerprint": adapter.persistent.fingerprint,
                    "accepted": False,
                }
            )
    execution = adapter.run(jacobian_mode="analytic")
    return execution, tuple(injected)


def _x_one_residual(execution: Any) -> float:
    rows = [
        row
        for row in execution.events
        if row.get("event") == "FormResidual"
        and row.get("x_hex") == "0x1.0000000000000p+0"
    ]
    if not rows:
        raise RuntimeError("SciPy execution lacks the frozen x=1 replay packet")
    return float(rows[0]["residual"])


def _s03_packet(*, load: Any = None) -> Any:
    committed = ScipyCommittedState()
    return replay_packet(
        primary={"x": 1.0},
        committed={"fingerprint": committed.fingerprint},
        persistent={"physics_projection": "committed_only"},
        load={"objective": "x^3-2x+2"} if load is None else load,
        residual_version="L6-RJ-D1.0",
        tangent_version="L6-RJ-D1.0",
        environment={"subject": "JSS-S03", "host": "SciPy-TRF-1.17.1"},
    )


def _s03_record(case: CaseSpec, run_id: str, runtime_mode: str) -> RuntimeRecord:
    import numpy as np
    import scipy

    environment = runtime_environment(
        "JSS-S03",
        backend={"name": "SciPy least_squares TRF", "scipy": scipy.__version__},
    )
    packet_a = _s03_packet()

    if case.case_id == "P5B-PASS-02":
        left, left_extra = _scipy_run("P5B-PASS-02-A", "safe_transactional")
        right, right_extra = _scipy_run("P5B-PASS-02-B", "safe_transactional")
        packet_b = packet_a
        accepted_delta = max(
            abs(left.final_x - right.final_x),
            abs(left.final_residual - right.final_residual),
            abs(left.final_cost - right.final_cost),
        )
        if accepted_delta != 0.0:
            raise RuntimeError("diagnostic-only control changed accepted fields")
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.COMPATIBLE,
            evidence_tokens=(
                "DIAGNOSTIC_FIELD_OWNERSHIP",
                "SEMANTIC_PERSISTENT_PROJECTION",
            ),
        )
        measurements = {
            "diagnostic_counter_a": 0,
            "diagnostic_counter_b": 1,
            "diagnostic_counter_in_physics_projection": False,
            "accepted_field_delta": accepted_delta,
            "finite": left.all_values_finite and right.all_values_finite,
            "converged": left.success and right.success,
        }
        events = tuple(left.events + right.events) + left_extra + right_extra
    elif case.case_id == "P5B-PASS-03":
        left, left_extra = _scipy_run("P5B-PASS-03-DIRECT", "safe_transactional")
        right, right_extra = _scipy_run(
            "P5B-PASS-03-EXTRA", "safe_transactional", extra_callbacks=True
        )
        packet_b = packet_a
        replay_drift = abs(_x_one_residual(left) - _x_one_residual(right))
        accepted_delta = max(
            abs(left.final_x - right.final_x),
            abs(left.final_residual - right.final_residual),
            abs(left.final_cost - right.final_cost),
        )
        if replay_drift != 0.0 or accepted_delta != 0.0:
            raise RuntimeError("safe callback-order control lost replay invariance")
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.COMPATIBLE,
            evidence_tokens=("CALLBACK_LEDGER", "REPLAY_PACKET"),
        )
        measurements = {
            "extra_callback_values": list(S03_CALLBACKS),
            "extra_callback_count": len(right_extra),
            "operator_replay_drift": replay_drift,
            "accepted_field_delta": accepted_delta,
            "finite": left.all_values_finite and right.all_values_finite,
            "converged": left.success and right.success,
        }
        events = tuple(left.events + right.events) + left_extra + right_extra
    elif case.case_id == "P5B-DETECT-03":
        left, left_extra = _scipy_run(
            "P5B-DETECT-03-DIRECT", "unsafe_persistent_cache"
        )
        right, right_extra = _scipy_run(
            "P5B-DETECT-03-EXTRA", "unsafe_persistent_cache", extra_callbacks=True
        )
        packet_b = packet_a
        replay_drift = abs(_x_one_residual(left) - _x_one_residual(right))
        if replay_drift <= 0.0:
            raise RuntimeError("unsafe callback cache did not produce replay drift")
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.COMPATIBLE,
            evidence_tokens=("CALLBACK_LEDGER", "PERSISTENT_FINGERPRINT"),
            signal_names=("operator_replay_drift", "ownership_violation"),
        )
        measurements = {
            "extra_callback_values": list(S03_CALLBACKS),
            "extra_callback_count": len(right_extra),
            "operator_replay_drift": replay_drift,
            "persistent_fingerprint_equal_before_replay": False,
            "finite": left.all_values_finite and right.all_values_finite,
            "converged": left.success and right.success,
            "direct_persistent_after": left.persistent_after_fingerprint,
            "extra_persistent_after": right.persistent_after_fingerprint,
        }
        events = tuple(left.events + right.events) + left_extra + right_extra
    elif case.case_id == "P5B-INVALID-03":
        packet_b = _s03_packet(load={"objective": "x^3-2x+2", "offset": 1.0e-6})
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.INCOMPATIBLE,
            evidence_tokens=("LOAD_PACKET_HASHES",),
        )
        measurements = {
            "load_packet_equal": False,
            "lifecycle_not_evaluated": True,
            "load_offset": 1.0e-6,
        }
        events = ({"event_type": "PrecomparisonLoadAudit", "field_name": "load_hash"},)
    elif case.case_id in {"P5B-NS-01", "P5B-NS-02"}:
        packet_b = packet_a
        missing = (
            "NATIVE_CHECKPOINT_EVENT"
            if case.case_id == "P5B-NS-01"
            else "NATIVE_OPERATOR_VERSION_FIELDS"
        )
        signature = str(inspect.signature(ScipyLifecycleAdapter.run))
        raw = raw_observation(
            packet_a,
            packet_b,
            PrecomparisonRelation.NOT_EVALUATED,
            evidence_tokens=(),
        )
        measurements = {
            "native_checkpoint_api_exposed": False,
            "native_operator_version_metadata_exposed": False,
            "adapter_run_signature": signature,
            "missing_evidence": missing,
        }
        events = ({"event_type": "StaticCapabilityAudit", "missing_evidence": missing},)
    else:
        raise ValueError(f"unsupported S03 development case: {case.case_id}")

    return RuntimeRecord(
        case_id=case.case_id,
        run_id=run_id,
        subject_id=case.subject_id,
        runtime_mode=runtime_mode,
        raw=raw,
        events=events,
        measurements=measurements,
        environment=environment,
    )


def execute_local_runtime(case: CaseSpec, run_id: str, runtime_mode: str) -> RuntimeRecord:
    if case.subject_id == "JSS-S02":
        return _s02_record(case, run_id, runtime_mode)
    if case.subject_id == "JSS-S03":
        return _s03_record(case, run_id, runtime_mode)
    raise ValueError(f"local runtime cannot execute subject {case.subject_id}")
