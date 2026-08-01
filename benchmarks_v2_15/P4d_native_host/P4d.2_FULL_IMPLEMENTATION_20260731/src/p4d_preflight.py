from __future__ import annotations

from dataclasses import asdict

from p4d_host import TransactionalFEHost
from p4d_state import initial_committed_state


def run_bounded_host_integration() -> dict[str, object]:
    host = TransactionalFEHost(initial_committed_state(), run_id="P4D2-INTEGRATION-01")
    accepted: list[dict[str, object]] = []
    for index, target in enumerate((0.04, 0.08, 0.10, 0.12), start=1):
        host.begin_attempt(target, f"P4D2-INTEGRATION-A{index:02d}", "EXACT_CURRENT", 25)
        attempt = host.solve_attempt()
        if not attempt.converged or not attempt.metrics.pass_flag:
            raise RuntimeError(f"bounded integration failed at {target}: {attempt}")
        host.commit(attempt)
        accepted.append({
            "target_load": target,
            "snes_reason": attempt.snes_reason,
            "iterations": attempt.nonlinear_iterations,
            "candidate_id": attempt.selected_packet.candidate_id,
            "committed_hash": host.committed.full_hash,
            "mechanics": asdict(attempt.metrics),
            "branches": sorted(set(attempt.selected_packet.branch.ravel().tolist())),
        })
    event_kinds = [event["event_kind"] for event in host.events.records]
    result = {
        "schema_version": "CMAME-P4D2-PREFLIGHT-1.0",
        "preflight_id": "P4D2-INTEGRATION-01",
        "accepted": accepted,
        "accepted_increment_count": len(accepted),
        "final_load": host.committed.accepted_load,
        "final_version": host.committed.accepted_version,
        "final_maximum_alpha": float(host.committed.alpha.max()),
        "plasticity_exercised": bool(host.committed.alpha.max() > 0.0),
        "trial_event_count": event_kinds.count("TrialEvaluate"),
        "residual_event_count": event_kinds.count("FormResidual"),
        "tangent_event_count": event_kinds.count("FormTangent"),
        "commit_event_count": event_kinds.count("AcceptCommit"),
        "formal_case_run": False,
        "continued_past_0p12": False,
        "pass_flag": bool(
            len(accepted) == 4
            and host.committed.accepted_load == 0.12
            and host.committed.accepted_version == 4
            and host.committed.alpha.max() > 0.0
            and event_kinds.count("AcceptCommit") == 4
        ),
    }
    host.close()
    return result
