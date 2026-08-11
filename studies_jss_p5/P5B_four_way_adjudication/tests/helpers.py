from __future__ import annotations

from dataclasses import replace

from jss_p5b.adapters import MECHANISM_REQUIREMENTS, RawObservation
from jss_p5b.cases import CaseSpec
from jss_p5b.model import LifecycleSignals, ReplayPacket, Verdict


def base_packet() -> ReplayPacket:
    return ReplayPacket(
        primary_state_hash="PRIMARY-A",
        committed_state_hash="COMMITTED-A",
        persistent_projection_hash="PERSISTENT-A",
        load_hash="LOAD-A",
        residual_version="R-1",
        tangent_version="J-1",
        environment_hash="ENV-A",
    )


def synthetic_observation(case: CaseSpec) -> RawObservation:
    packet_a = base_packet()
    packet_b = packet_a
    signals = LifecycleSignals()
    if case.fault_or_control == "DECLARED_VERSIONED_TANGENT_LAG":
        packet_b = replace(packet_b, tangent_version="J-LAG-DECLARED")
    elif case.fault_or_control == "PRIMARY_STATE_MISMATCH":
        packet_b = replace(packet_b, primary_state_hash="PRIMARY-B")
    elif case.fault_or_control == "COMMITTED_PROJECTION_MISMATCH":
        packet_b = replace(
            packet_b,
            committed_state_hash="COMMITTED-B",
            persistent_projection_hash="PERSISTENT-B",
        )
    elif case.fault_or_control == "LOAD_MISMATCH":
        packet_b = replace(packet_b, load_hash="LOAD-B")
    elif case.fault_or_control == "PRECOMPARISON_VERSION_MISMATCH":
        packet_b = replace(packet_b, tangent_version="J-INCOMPATIBLE")
    elif case.fault_or_control == "BOUNDARY_CONTROL_MISMATCH":
        packet_b = replace(packet_b, environment_hash="ENV-BOUNDARY-B")
    if case.target_verdict is Verdict.DETECT_LIFECYCLE_DRIFT:
        if case.fault_or_control == "F03_PREMATURE_COMMIT":
            signals = LifecycleSignals(
                authoritative_state_mutation=True,
                commit_violation=True,
            )
        elif case.fault_or_control == "F05_OUTPUT_FEEDBACK":
            signals = LifecycleSignals(
                operator_replay_drift=True,
                output_provenance_violation=True,
            )
        elif case.fault_or_control == "F07_CALLBACK_ORDER_BIAS":
            signals = LifecycleSignals(
                operator_replay_drift=True,
                ownership_violation=True,
            )
        elif case.fault_or_control == "F08_WITHIN_HISTORY_VERSION_VIOLATION":
            signals = LifecycleSignals(within_history_version_violation=True)
        elif case.fault_or_control == "F05_REJECTED_CANDIDATE_OUTPUT":
            signals = LifecycleSignals(output_provenance_violation=True)
        else:
            raise AssertionError(f"no frozen synthetic signal for {case.fault_or_control}")
    return RawObservation(
        packet_a=packet_a,
        packet_b=packet_b,
        precomparison_relation=case.precomparison_relation,
        lifecycle_signals=signals,
        evidence_tokens=MECHANISM_REQUIREMENTS[case.fault_or_control],
    )

