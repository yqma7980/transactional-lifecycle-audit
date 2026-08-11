"""Transaction adapter around the installed SciPy TRF least-squares host."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import numpy as np
import scipy
from scipy.optimize import least_squares

from benchmarks.L6_external_host.src.l6_state import (
    AcceptedOutput,
    CommittedState,
    OperatorVersionMismatch,
    PersistentState,
    ResidualPacket,
    TangentPacket,
    TrialCandidate,
    all_finite,
    canonical_hash,
    stale_state_version,
    state_version,
)


EXPECTED_SCIPY_VERSION = "1.17.1"


@dataclass(frozen=True)
class HostConfiguration:
    x0: float = 1.0
    method: str = "trf"
    tr_solver: str = "exact"
    ftol: float = 1.0e-12
    xtol: float = 1.0e-12
    gtol: float = 1.0e-12
    max_nfev: int = 100
    x_scale: float = 1.0
    loss: str = "linear"
    diff_step: float = 1.0e-6


@dataclass
class HostExecution:
    path_id: str
    variant: str
    jacobian_mode: str
    success: bool
    status: int
    message: str
    final_x: float
    final_residual: float
    final_cost: float
    nfev: int
    njev: int
    events: list[dict[str, Any]]
    outputs: list[AcceptedOutput]
    committed_before: CommittedState
    committed_after: CommittedState | None
    persistent_before_fingerprint: str
    persistent_after_fingerprint: str
    version_mismatch: dict[str, Any] | None = None

    @property
    def nonaccepted_residual_events(self) -> list[dict[str, Any]]:
        return [
            event
            for event in self.events
            if event["event"] == "FormResidual"
            and event["resolution"] == "HOST_NONACCEPTED"
        ]

    @property
    def accepted_residual_events(self) -> list[dict[str, Any]]:
        return [
            event
            for event in self.events
            if event["event"] == "FormResidual"
            and event["resolution"] == "HOST_ACCEPTED_ITERATE"
        ]

    @property
    def committed_transition_valid(self) -> bool:
        if not self.success or self.committed_after is None:
            return False
        return (
            self.committed_after.history.hex() == self.final_x.hex()
            and self.committed_after.accepted_version
            == self.committed_before.accepted_version + 1
        )

    @property
    def rejected_candidates_unreachable(self) -> bool:
        output_sources = {output.source_event_id for output in self.outputs}
        return all(
            event["event_id"] not in output_sources
            and not event["candidate_reachable"]
            and not event["output_reachable"]
            for event in self.nonaccepted_residual_events
        )

    @property
    def all_values_finite(self) -> bool:
        values = [self.final_x, self.final_residual, self.final_cost]
        for event in self.events:
            for key in ("x", "residual", "tangent", "cost"):
                value = event.get(key)
                if value is not None:
                    values.append(float(value))
        return all_finite(values)


class ScipyLifecycleAdapter:
    """Record genuine SciPy trial/accept events without changing host order."""

    def __init__(
        self,
        *,
        path_id: str,
        variant: str,
        config: HostConfiguration | None = None,
    ) -> None:
        if scipy.__version__ != EXPECTED_SCIPY_VERSION:
            raise RuntimeError(
                f"Frozen SciPy version {EXPECTED_SCIPY_VERSION}, found {scipy.__version__}"
            )
        if variant not in {
            "safe_transactional",
            "unsafe_persistent_cache",
            "version_mismatch",
        }:
            raise ValueError(f"Unsupported variant: {variant}")
        self.path_id = path_id
        self.variant = variant
        self.config = config or HostConfiguration()
        self.committed = CommittedState()
        self.committed_before = self.committed
        self.persistent = PersistentState()
        self.persistent_before_fingerprint = self.persistent.fingerprint
        self.events: list[dict[str, Any]] = []
        self.outputs: list[AcceptedOutput] = []
        self._residual_call_count = 0
        self._jacobian_call_count = 0
        self._callback_count = 0
        self._segment_residual_indices: list[int] = []
        self._last_residual_by_x: dict[str, ResidualPacket] = {}
        self._last_accepted_x_hex: str | None = None
        self._last_accepted_event_id: str | None = None

    def _event(self, event: str, **values: Any) -> int:
        row: dict[str, Any] = {
            "ordinal": len(self.events) + 1,
            "path_id": self.path_id,
            "variant": self.variant,
            "event": event,
            "event_id": f"{self.path_id}:E{len(self.events) + 1}",
            "resolution": values.pop("resolution", ""),
            "x": values.pop("x", None),
            "x_hex": values.pop("x_hex", ""),
            "residual": values.pop("residual", None),
            "tangent": values.pop("tangent", None),
            "cost": values.pop("cost", None),
            "residual_state_version": values.pop(
                "residual_state_version", ""
            ),
            "tangent_state_version": values.pop(
                "tangent_state_version", ""
            ),
            "candidate_fingerprint": values.pop(
                "candidate_fingerprint", ""
            ),
            "committed_fingerprint": values.pop(
                "committed_fingerprint", self.committed.fingerprint
            ),
            "persistent_before_fingerprint": values.pop(
                "persistent_before_fingerprint", self.persistent.fingerprint
            ),
            "persistent_after_fingerprint": values.pop(
                "persistent_after_fingerprint", self.persistent.fingerprint
            ),
            "candidate_reachable": values.pop("candidate_reachable", False),
            "output_reachable": values.pop("output_reachable", False),
            "host_nfev": values.pop("host_nfev", None),
            "host_njev": values.pop("host_njev", None),
            "host_nit": values.pop("host_nit", None),
        }
        if values:
            row.update(values)
        self.events.append(row)
        return len(self.events) - 1

    def fun(self, x_array: np.ndarray) -> np.ndarray:
        x = float(x_array[0])
        self._residual_call_count += 1
        persistent_before = self.persistent.fingerprint
        history_used = (
            self.persistent.history
            if self.variant == "unsafe_persistent_cache"
            else self.committed.history
        )
        beta = 0.05 if self.variant == "unsafe_persistent_cache" else 0.0
        residual = x**3 - 2.0 * x + 2.0 + beta * history_used
        version = state_version(self.committed, x)
        candidate = TrialCandidate(
            x=x,
            candidate_history=x,
            source_event_id=f"{self.path_id}:R{self._residual_call_count}",
            committed_fingerprint=self.committed.fingerprint,
        )
        packet = ResidualPacket(
            x=x,
            residual=residual,
            residual_state_version=version,
            candidate_fingerprint=candidate.fingerprint,
            committed_fingerprint=self.committed.fingerprint,
        )
        if self.variant == "unsafe_persistent_cache":
            self.persistent.history = x
            self.persistent.mutation_count += 1
        persistent_after = self.persistent.fingerprint
        resolution = (
            "HOST_INITIAL"
            if self._residual_call_count == 1
            else "UNRESOLVED"
        )
        index = self._event(
            "FormResidual",
            resolution=resolution,
            x=x,
            x_hex=x.hex(),
            residual=residual,
            residual_state_version=version,
            candidate_fingerprint=candidate.fingerprint,
            persistent_before_fingerprint=persistent_before,
            persistent_after_fingerprint=persistent_after,
            residual_packet_fingerprint=packet.fingerprint,
            candidate_source_event_id=candidate.source_event_id,
        )
        if resolution == "UNRESOLVED":
            self._segment_residual_indices.append(index)
        self._last_residual_by_x[x.hex()] = packet
        return np.array([residual], dtype=float)

    def jac(self, x_array: np.ndarray) -> np.ndarray:
        x = float(x_array[0])
        self._jacobian_call_count += 1
        residual_packet = self._last_residual_by_x.get(x.hex())
        if residual_packet is None:
            raise RuntimeError("Jacobian requested without same-x residual packet")
        tangent = 3.0 * x**2 - 2.0
        tangent_version = (
            stale_state_version(self.committed, x)
            if self.variant == "version_mismatch"
            else residual_packet.residual_state_version
        )
        tangent_packet = TangentPacket(
            x=x,
            tangent=tangent,
            tangent_state_version=tangent_version,
            committed_fingerprint=self.committed.fingerprint,
        )
        compatible = (
            residual_packet.residual_state_version
            == tangent_packet.tangent_state_version
        )
        self._event(
            "FormTangent" if compatible else "RejectVersionMismatch",
            resolution="HOST_JACOBIAN" if compatible else "REJECTED_PRE_HOST",
            x=x,
            x_hex=x.hex(),
            residual=residual_packet.residual,
            tangent=tangent,
            residual_state_version=residual_packet.residual_state_version,
            tangent_state_version=tangent_packet.tangent_state_version,
            candidate_fingerprint=residual_packet.candidate_fingerprint,
            residual_packet_fingerprint=residual_packet.fingerprint,
            tangent_packet_fingerprint=tangent_packet.fingerprint,
            version_compatible=compatible,
        )
        if not compatible:
            raise OperatorVersionMismatch(residual_packet, tangent_packet)
        return np.array([[tangent]], dtype=float)

    def callback(self, intermediate_result: Any) -> None:
        x = float(intermediate_result.x[0])
        match = None
        for index in reversed(self._segment_residual_indices):
            if self.events[index]["x_hex"] == x.hex():
                match = index
                break
        if match is None:
            if (
                self._last_accepted_x_hex != x.hex()
                or self._last_accepted_event_id is None
            ):
                raise RuntimeError(
                    "Accepted callback lacks a current or prior matching "
                    "residual event"
                )
            for index in self._segment_residual_indices:
                self.events[index]["resolution"] = "HOST_NONACCEPTED"
            callback_resolution = "HOST_ACCEPTED_STATE_UNCHANGED"
            accepted_state_changed = False
        else:
            for index in self._segment_residual_indices:
                self.events[index]["resolution"] = (
                    "HOST_ACCEPTED_ITERATE"
                    if index == match
                    else "HOST_NONACCEPTED"
                )
            self._last_accepted_x_hex = x.hex()
            self._last_accepted_event_id = self.events[match]["event_id"]
            callback_resolution = "HOST_ACCEPTED_ITERATE"
            accepted_state_changed = True
        self._callback_count += 1
        self._event(
            "HostAcceptedCallback",
            resolution=callback_resolution,
            x=x,
            x_hex=x.hex(),
            residual=float(intermediate_result.fun[0]),
            cost=float(intermediate_result.cost),
            host_nfev=int(intermediate_result.nfev),
            host_nit=int(intermediate_result.nit),
            accepted_residual_event_id=self._last_accepted_event_id,
            accepted_state_changed=accepted_state_changed,
        )
        self._segment_residual_indices.clear()

    def _finalize_unresolved(self) -> None:
        for index in self._segment_residual_indices:
            self.events[index]["resolution"] = "HOST_NONACCEPTED_ON_RETURN"
        self._segment_residual_indices.clear()

    def run(self, *, jacobian_mode: str = "analytic") -> HostExecution:
        if jacobian_mode not in {"analytic", "2-point"}:
            raise ValueError(f"Unsupported Jacobian mode: {jacobian_mode}")
        kwargs: dict[str, Any] = {
            "fun": self.fun,
            "x0": np.array([self.config.x0], dtype=float),
            "jac": self.jac if jacobian_mode == "analytic" else "2-point",
            "method": self.config.method,
            "tr_solver": self.config.tr_solver,
            "ftol": self.config.ftol,
            "xtol": self.config.xtol,
            "gtol": self.config.gtol,
            "max_nfev": self.config.max_nfev,
            "x_scale": self.config.x_scale,
            "loss": self.config.loss,
            "callback": self.callback,
            "verbose": 0,
        }
        if jacobian_mode == "2-point":
            kwargs["diff_step"] = self.config.diff_step
        result = least_squares(**kwargs)
        self._finalize_unresolved()
        final_x = float(result.x[0])
        final_residual = float(result.fun[0])
        final_cost = float(result.cost)
        self._event(
            "HostReturn",
            resolution="HOST_SUCCESS" if result.success else "HOST_FAILURE",
            x=final_x,
            x_hex=final_x.hex(),
            residual=final_residual,
            cost=final_cost,
            host_nfev=int(result.nfev),
            host_njev=int(result.njev),
            host_status=int(result.status),
        )
        committed_after: CommittedState | None = None
        if result.success:
            if self._last_accepted_x_hex != final_x.hex():
                raise RuntimeError(
                    "Host-returned state does not match latest accepted callback"
                )
            committed_after = CommittedState(
                history=final_x,
                accepted_version=self.committed.accepted_version + 1,
            )
            self._event(
                "Commit",
                resolution="PHYSICAL_ACCEPT",
                x=final_x,
                x_hex=final_x.hex(),
                residual=final_residual,
                cost=final_cost,
                committed_before_fingerprint=self.committed.fingerprint,
                committed_after_fingerprint=committed_after.fingerprint,
            )
            self.committed = committed_after
            output = AcceptedOutput(
                x=final_x,
                residual=final_residual,
                cost=final_cost,
                committed_fingerprint=committed_after.fingerprint,
                accepted_version=committed_after.accepted_version,
                source_event_id=str(self._last_accepted_event_id),
            )
            self.outputs.append(output)
            self._event(
                "OutputAcceptedState",
                resolution="ACCEPTED_OUTPUT",
                x=final_x,
                x_hex=final_x.hex(),
                residual=final_residual,
                cost=final_cost,
                committed_fingerprint=committed_after.fingerprint,
                output_reachable=True,
                source_event_id=output.source_event_id,
                output_fingerprint=output.fingerprint,
            )
        return HostExecution(
            path_id=self.path_id,
            variant=self.variant,
            jacobian_mode=jacobian_mode,
            success=bool(result.success),
            status=int(result.status),
            message=str(result.message),
            final_x=final_x,
            final_residual=final_residual,
            final_cost=final_cost,
            nfev=int(result.nfev),
            njev=int(result.njev),
            events=self.events,
            outputs=self.outputs,
            committed_before=self.committed_before,
            committed_after=committed_after,
            persistent_before_fingerprint=self.persistent_before_fingerprint,
            persistent_after_fingerprint=self.persistent.fingerprint,
        )

    def mismatch_execution(self) -> HostExecution:
        try:
            self.run(jacobian_mode="analytic")
        except OperatorVersionMismatch as exc:
            self._finalize_unresolved()
            values = [
                exc.residual_packet.x,
                exc.residual_packet.residual,
                exc.tangent_packet.x,
                exc.tangent_packet.tangent,
            ]
            return HostExecution(
                path_id=self.path_id,
                variant=self.variant,
                jacobian_mode="analytic",
                success=False,
                status=-99,
                message=str(exc),
                final_x=exc.residual_packet.x,
                final_residual=exc.residual_packet.residual,
                final_cost=0.5 * exc.residual_packet.residual**2,
                nfev=self._residual_call_count,
                njev=self._jacobian_call_count,
                events=self.events,
                outputs=self.outputs,
                committed_before=self.committed_before,
                committed_after=None,
                persistent_before_fingerprint=self.persistent_before_fingerprint,
                persistent_after_fingerprint=self.persistent.fingerprint,
                version_mismatch={
                    "residual_state_version": (
                        exc.residual_packet.residual_state_version
                    ),
                    "tangent_state_version": (
                        exc.tangent_packet.tangent_state_version
                    ),
                    "all_values_finite": all_finite(values),
                    "rejected_before_host_correction": True,
                },
            )
        raise RuntimeError("Mismatch case unexpectedly reached host return")


def output_rows(execution: HostExecution) -> list[dict[str, Any]]:
    return [asdict(output) | {"path_id": execution.path_id} for output in execution.outputs]


def event_rows(execution: HostExecution) -> list[dict[str, Any]]:
    return [dict(event) for event in execution.events]


__all__ = [
    "EXPECTED_SCIPY_VERSION",
    "HostConfiguration",
    "HostExecution",
    "ScipyLifecycleAdapter",
    "event_rows",
    "output_rows",
]
