"""Five frozen L2-D1 cases. Importing this module performs no execution."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path
from typing import Any

from oracle.l2_fraction_oracle import equilibrium

from .l2_host import HostControls, NewtonHost
from .l2_state import DESIGN_VERSION, HOST_VERSION, MaterialData, canonical_hash
from .l2_variants import VARIANTS


CLAIM_BOUNDARY = (
    "Standalone L2-D1 only; no Abaqus, restart, coupled physics, conservation, "
    "thread-safety, performance or production claim."
)


@dataclass(frozen=True)
class CaseExecution:
    result: dict[str, Any]
    events: tuple[dict[str, Any], ...]
    checkpoints: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class HistoryExecution:
    probe: Any
    events: tuple[dict[str, Any], ...]
    checkpoints: tuple[Any, ...]
    reject_committed_unchanged: bool
    reject_candidate_unreachable: bool


def authorized_case_ids() -> tuple[str, ...]:
    return (
        "L2-REF-01",
        "L2-REF-02",
        "L2-RT-01",
        "L2-RT-02",
        "L2-RT-03",
    )


def _fraction(value: str) -> float:
    return float(Fraction(value))


def _configuration_hash(root: Path) -> str:
    return canonical_hash(
        {
            "freeze": (root / "L2_D1_execution_freeze.json").read_text(
                encoding="utf-8"
            ),
            "matrix": (root / "L2_D1_minimal_case_matrix.csv").read_text(
                encoding="utf-8"
            ),
            "design_version": DESIGN_VERSION,
            "host_version": HOST_VERSION,
        }
    )


def _checkpoint_rows(
    *,
    run_id: str,
    case_id: str,
    history_id: str,
    variant: str,
    checkpoints: tuple[Any, ...],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for index, checkpoint in enumerate(checkpoints, start=1):
        rows.append(
            {
                "design_version": DESIGN_VERSION,
                "host_version": HOST_VERSION,
                "run_id": run_id,
                "case_id": case_id,
                "history_id": history_id,
                "variant": variant,
                "checkpoint_index": index,
                "force": checkpoint.force,
                "displacement": checkpoint.displacement,
                "reaction": checkpoint.reaction,
                "stress": checkpoint.stress,
                "epsilon_p": checkpoint.epsilon_p,
                "kappa": checkpoint.kappa,
                "accepted_version": checkpoint.accepted_version,
                "committed_state_hash": checkpoint.committed_state_hash,
                "physical_checkpoint_hash": checkpoint.physical_hash,
            }
        )
    return tuple(rows)


def _reference_case(
    *,
    root: Path,
    run_id: str,
    case_id: str,
    force_fraction: str,
) -> CaseExecution:
    variant_name = "safe_transactional"
    variant = VARIANTS[variant_name](MaterialData())
    host = NewtonHost(
        run_id=run_id,
        case_id=case_id,
        history_id="REFERENCE",
        variant=variant,
        configuration_hash=_configuration_hash(root),
    )
    force = _fraction(force_fraction)
    checkpoint = host.solve_increment(
        target_force=force,
        attempt_id=f"{case_id}:reference",
    )
    oracle = equilibrium(Fraction(force_fraction))
    error_u = checkpoint.displacement - float(oracle.displacement)
    error_stress = checkpoint.stress - float(oracle.stress)
    state_error = max(
        abs(checkpoint.epsilon_p - float(oracle.epsilon_p)),
        abs(checkpoint.kappa - float(oracle.kappa)),
    )
    tolerance = 1.0e-12
    passed = (
        abs(error_u) <= tolerance
        and abs(error_stress) <= tolerance
        and state_error <= tolerance
    )
    result = {
        "design_version": DESIGN_VERSION,
        "host_version": HOST_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "variant": variant_name,
        "expected_classification": "PASS_ANALYTICAL_REFERENCE",
        "observed_classification": (
            "PASS_ANALYTICAL_REFERENCE"
            if passed
            else "FAIL_ANALYTICAL_REFERENCE"
        ),
        "analytical_error_displacement": error_u,
        "analytical_error_stress": error_stress,
        "replay_delta_residual": "NA",
        "replay_delta_tangent": "NA",
        "accepted_checkpoint_equal": "NA",
        "committed_unchanged_on_reject": "NA",
        "candidate_unreachable_after_reject": "NA",
        "finite": all(
            math.isfinite(value)
            for value in (
                checkpoint.displacement,
                checkpoint.stress,
                checkpoint.epsilon_p,
                checkpoint.kappa,
            )
        ),
        "hard_gate_failed": "NA" if passed else "analytical_reference",
        "passed": passed,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    checkpoints = _checkpoint_rows(
        run_id=run_id,
        case_id=case_id,
        history_id="REFERENCE",
        variant=variant_name,
        checkpoints=(checkpoint,),
    )
    return CaseExecution(result, tuple(host.events), checkpoints)


def _run_history(
    *,
    root: Path,
    run_id: str,
    case_id: str,
    variant_name: str,
    history_id: str,
    forced_retry: bool,
    solve_accepted_path: bool,
) -> HistoryExecution:
    variant = VARIANTS[variant_name](MaterialData())
    host = NewtonHost(
        run_id=run_id,
        case_id=case_id,
        history_id=history_id,
        variant=variant,
        configuration_hash=_configuration_hash(root),
        controls=HostControls(),
    )
    committed_unchanged = True
    candidate_unreachable = True
    retry_parent = "NA"
    if forced_retry:
        retry_parent = f"{case_id}:{history_id}:forced_parent"
        seed = host.inject_forced_retry(
            attempt_id=retry_parent,
            displacement=_fraction("3/100"),
            force=_fraction("11/10"),
        )
        committed_unchanged = seed.committed_unchanged
        candidate_unreachable = seed.candidate_unreachable

    probe = host.replay_probe(
        attempt_id=f"{case_id}:{history_id}:probe",
        displacement=_fraction("1/200"),
        force=_fraction("1/2"),
    )
    committed_unchanged = committed_unchanged and probe.committed_unchanged
    candidate_unreachable = candidate_unreachable and probe.candidate_unreachable

    if solve_accepted_path:
        host.solve_increment(
            target_force=_fraction("11/20"),
            attempt_id=f"{case_id}:{history_id}:inc1",
            retry_parent_id=retry_parent,
        )
        host.solve_increment(
            target_force=_fraction("11/10"),
            attempt_id=f"{case_id}:{history_id}:inc2",
        )

    return HistoryExecution(
        probe=probe.result,
        events=tuple(host.events),
        checkpoints=tuple(host.checkpoints),
        reject_committed_unchanged=committed_unchanged,
        reject_candidate_unreachable=candidate_unreachable,
    )


def _retry_case(
    *,
    root: Path,
    run_id: str,
    case_id: str,
    variant_name: str,
) -> CaseExecution:
    safe = variant_name != "unsafe_trial_cache"
    direct = _run_history(
        root=root,
        run_id=run_id,
        case_id=case_id,
        variant_name=variant_name,
        history_id="DIRECT",
        forced_retry=False,
        solve_accepted_path=safe,
    )
    retry = _run_history(
        root=root,
        run_id=run_id,
        case_id=case_id,
        variant_name=variant_name,
        history_id="FORCED_RETRY",
        forced_retry=True,
        solve_accepted_path=safe,
    )
    delta_residual = retry.probe.residual - direct.probe.residual
    delta_tangent = retry.probe.tangent - direct.probe.tangent
    finite = all(
        math.isfinite(value)
        for value in (
            direct.probe.residual,
            direct.probe.tangent,
            retry.probe.residual,
            retry.probe.tangent,
        )
    )
    committed_ok = (
        direct.reject_committed_unchanged
        and retry.reject_committed_unchanged
    )
    unreachable_ok = (
        direct.reject_candidate_unreachable
        and retry.reject_candidate_unreachable
    )

    if safe:
        direct_hashes = tuple(value.physical_hash for value in direct.checkpoints)
        retry_hashes = tuple(value.physical_hash for value in retry.checkpoints)
        checkpoint_equal = direct_hashes == retry_hashes
        passed = (
            finite
            and committed_ok
            and unreachable_ok
            and delta_residual == 0.0
            and delta_tangent == 0.0
            and checkpoint_equal
        )
        expected = "PASS_EXACT_ACCEPTED_CHECKPOINT"
        observed = expected if passed else "FAIL_RETRY_ROLLBACK_PARITY"
        hard_gate = "NA" if passed else "retry_rollback"
    else:
        checkpoint_equal = "NA"
        passed = (
            finite
            and committed_ok
            and unreachable_ok
            and abs(delta_residual) >= 1.0e-8
        )
        expected = "DETECT_FINITE_REJECTED_TRIAL_ESCAPE"
        observed = expected if passed else "UNSAFE_RETRY_SEED_NOT_DETECTED"
        hard_gate = "NA" if passed else "negative_control_detection"

    result = {
        "design_version": DESIGN_VERSION,
        "host_version": HOST_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "variant": variant_name,
        "expected_classification": expected,
        "observed_classification": observed,
        "analytical_error_displacement": "NA",
        "analytical_error_stress": "NA",
        "replay_delta_residual": delta_residual,
        "replay_delta_tangent": delta_tangent,
        "accepted_checkpoint_equal": checkpoint_equal,
        "committed_unchanged_on_reject": committed_ok,
        "candidate_unreachable_after_reject": unreachable_ok,
        "finite": finite,
        "hard_gate_failed": hard_gate,
        "passed": passed,
        "claim_boundary": CLAIM_BOUNDARY,
    }
    checkpoints = (
        _checkpoint_rows(
            run_id=run_id,
            case_id=case_id,
            history_id="DIRECT",
            variant=variant_name,
            checkpoints=direct.checkpoints,
        )
        + _checkpoint_rows(
            run_id=run_id,
            case_id=case_id,
            history_id="FORCED_RETRY",
            variant=variant_name,
            checkpoints=retry.checkpoints,
        )
    )
    return CaseExecution(
        result=result,
        events=direct.events + retry.events,
        checkpoints=checkpoints,
    )


def execute_case(root: Path, case_id: str, run_id: str) -> CaseExecution:
    if case_id not in authorized_case_ids():
        raise ValueError(f"Case is outside the frozen D1 subset: {case_id}")
    freeze = json.loads(
        (root / "L2_D1_execution_freeze.json").read_text(encoding="utf-8")
    )
    if tuple(freeze["authorized_case_subset"]) != authorized_case_ids():
        raise RuntimeError("Freeze and implementation case subsets differ")

    if case_id == "L2-REF-01":
        return _reference_case(
            root=root,
            run_id=run_id,
            case_id=case_id,
            force_fraction="1/2",
        )
    if case_id == "L2-REF-02":
        return _reference_case(
            root=root,
            run_id=run_id,
            case_id=case_id,
            force_fraction="11/10",
        )
    if case_id == "L2-RT-01":
        variant_name = "safe_local"
    elif case_id == "L2-RT-02":
        variant_name = "safe_transactional"
    else:
        variant_name = "unsafe_trial_cache"
    return _retry_case(
        root=root,
        run_id=run_id,
        case_id=case_id,
        variant_name=variant_name,
    )
