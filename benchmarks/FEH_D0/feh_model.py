from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.sparse.linalg import spsolve
from skfem import Basis, BilinearForm, ElementQuad1, LinearForm, MeshQuad, asm
from skfem.element import DiscreteField
from skfem.helpers import dot, grad


SERIALIZER_VERSION = "FEH-CANON-1.0"
RESIDUAL_VERSION = "FEH-R-1.0"
TANGENT_VERSION = "FEH-K-1.0"
FINITE_LIMIT = 1.0e100


def _array_packet(value: np.ndarray) -> dict[str, Any]:
    array = np.ascontiguousarray(value, dtype="<f8")
    return {
        "dtype": "<f8",
        "shape": list(array.shape),
        "sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest(),
    }


def canonical_json(value: Any) -> str:
    def convert(item: Any) -> Any:
        if isinstance(item, np.ndarray):
            return {"__ndarray__": _array_packet(item)}
        if isinstance(item, (np.floating, float)):
            return {"__float_hex__": float(item).hex()}
        if isinstance(item, (np.integer, int)):
            return int(item)
        if isinstance(item, (np.bool_, bool)):
            return bool(item)
        if isinstance(item, dict):
            return {str(key): convert(item[key]) for key in sorted(item)}
        if isinstance(item, (list, tuple)):
            return [convert(entry) for entry in item]
        if item is None or isinstance(item, str):
            return item
        raise TypeError(f"Unsupported canonical type: {type(item)!r}")

    return json.dumps(convert(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def norm_relative(delta: np.ndarray | float, reference: np.ndarray | float) -> float:
    d = np.asarray(delta, dtype=float)
    r = np.asarray(reference, dtype=float)
    return float(np.linalg.norm(d.ravel()) / max(1.0, np.linalg.norm(r.ravel())))


def all_finite(*values: Any) -> bool:
    for value in values:
        array = np.asarray(value, dtype=float)
        if not np.isfinite(array).all() or np.max(np.abs(array), initial=0.0) >= FINITE_LIMIT:
            return False
    return True


@dataclass(frozen=True)
class MaterialParameters:
    shear_modulus: float = 10.0
    hardening_modulus: float = 1.0
    yield_stress: float = 0.55
    band_factor: float = 0.72

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self.__dict__)


@dataclass
class CommittedState:
    displacement: np.ndarray
    plastic_strain: np.ndarray
    kappa: np.ndarray
    load: float
    accepted_version: int

    def clone(self) -> "CommittedState":
        return CommittedState(
            self.displacement.copy(),
            self.plastic_strain.copy(),
            self.kappa.copy(),
            float(self.load),
            int(self.accepted_version),
        )

    @property
    def fingerprint(self) -> str:
        return canonical_hash(
            {
                "serializer": SERIALIZER_VERSION,
                "displacement": self.displacement,
                "plastic_strain": self.plastic_strain,
                "kappa": self.kappa,
                "load": self.load,
                "accepted_version": self.accepted_version,
            }
        )


@dataclass
class PersistentState:
    hidden_plastic_strain: np.ndarray
    hidden_kappa: np.ndarray
    output_mirror_kappa: np.ndarray
    version: int = 0

    def clone(self) -> "PersistentState":
        return PersistentState(
            self.hidden_plastic_strain.copy(),
            self.hidden_kappa.copy(),
            self.output_mirror_kappa.copy(),
            int(self.version),
        )

    @property
    def fingerprint(self) -> str:
        return canonical_hash(
            {
                "serializer": SERIALIZER_VERSION,
                "hidden_plastic_strain": self.hidden_plastic_strain,
                "hidden_kappa": self.hidden_kappa,
                "output_mirror_kappa": self.output_mirror_kappa,
                "version": self.version,
            }
        )


@dataclass
class CandidateState:
    plastic_strain: np.ndarray
    kappa: np.ndarray
    stress: np.ndarray
    tangent: np.ndarray

    @property
    def fingerprint(self) -> str:
        return canonical_hash(
            {
                "plastic_strain": self.plastic_strain,
                "kappa": self.kappa,
                "stress": self.stress,
                "tangent": self.tangent,
            }
        )


@dataclass
class OperatorPacket:
    displacement: np.ndarray
    load: float
    residual: np.ndarray
    tangent: Any
    candidate: CandidateState
    declared_fingerprint: str
    persistent_fingerprint: str
    residual_version: str = RESIDUAL_VERSION
    tangent_version: str = TANGENT_VERSION


@dataclass
class EventLedger:
    history_id: str
    rows: list[dict[str, Any]] = field(default_factory=list)

    def add(self, event: str, **kwargs: Any) -> None:
        row = {
            "history_id": self.history_id,
            "ordinal": len(self.rows) + 1,
            "event": event,
        }
        row.update(kwargs)
        self.rows.append(row)


@dataclass
class HistoryResult:
    history_id: str
    classification: str
    pass_flag: bool
    committed: CommittedState
    persistent: PersistentState
    accepted_rows: list[dict[str, Any]]
    ledger: EventLedger
    replay_packet: OperatorPacket | None
    all_values_finite: bool
    version_rejected_before_correction: bool = False


@LinearForm
def residual_form(v, w):
    return dot(w.stress, grad(v))


@BilinearForm
def tangent_form(u, v, w):
    c_grad_u = np.einsum("ij...,j...->i...", w.material_tangent, grad(u))
    return dot(c_grad_u, grad(v))


class FEHost:
    def __init__(
        self,
        nx: int,
        ny: int,
        heterogeneous: bool,
        variant: str,
        mutation_strength: float,
        history_id: str,
        material: MaterialParameters | None = None,
    ) -> None:
        self.nx = int(nx)
        self.ny = int(ny)
        self.heterogeneous = bool(heterogeneous)
        self.variant = variant
        self.mutation_strength = float(mutation_strength)
        self.material = material or MaterialParameters()
        self.mesh = MeshQuad.init_tensor(
            np.linspace(0.0, 1.0, self.nx + 1),
            np.linspace(0.0, 1.0, self.ny + 1),
        )
        self.basis = Basis(self.mesh, ElementQuad1(), intorder=3)
        self.bottom = np.asarray(
            self.basis.get_dofs(lambda x: np.isclose(x[1], 0.0)).all(), dtype=int
        )
        self.top = np.asarray(
            self.basis.get_dofs(lambda x: np.isclose(x[1], 1.0)).all(), dtype=int
        )
        self.fixed = np.unique(np.concatenate([self.bottom, self.top]))
        self.free = np.setdiff1d(np.arange(self.basis.N), self.fixed)
        qshape = (self.mesh.nelements, self.basis.X.shape[1])
        zeros_p = np.zeros((2,) + qshape)
        zeros_k = np.zeros(qshape)
        self.committed = CommittedState(
            np.zeros(self.basis.N), zeros_p.copy(), zeros_k.copy(), 0.0, 0
        )
        self.persistent = PersistentState(
            zeros_p.copy(), zeros_k.copy(), zeros_k.copy(), 0
        )
        self.ledger = EventLedger(history_id)
        self.accepted_rows: list[dict[str, Any]] = []
        self._initial_committed_hash = self.committed.fingerprint
        coordinates = self.basis.global_coordinates()
        band = np.abs(coordinates[1] - (0.25 + 0.5 * coordinates[0])) <= 0.13
        self.yield_field = np.full(qshape, self.material.yield_stress)
        if self.heterogeneous:
            self.yield_field[band] *= self.material.band_factor

    @property
    def mesh_fingerprint(self) -> str:
        return canonical_hash(
            {
                "host": "scikit-fem-12.0.2",
                "nx": self.nx,
                "ny": self.ny,
                "points": self.mesh.p,
                "connectivity": self.mesh.t.astype(float),
                "quadrature": self.basis.X,
            }
        )

    def _authoritative_persistent_packet(self) -> dict[str, Any]:
        return {
            "hidden_plastic_strain": self.committed.plastic_strain,
            "hidden_kappa": self.committed.kappa,
            "output_mirror_kappa": self.committed.kappa,
            "version": self.committed.accepted_version,
        }

    def _declared_packet(self, displacement: np.ndarray, load: float) -> dict[str, Any]:
        authoritative_persistent = self._authoritative_persistent_packet()
        return {
            "serializer_version": SERIALIZER_VERSION,
            "mesh_fingerprint": self.mesh_fingerprint,
            "material_fingerprint": self.material.fingerprint,
            "displacement": displacement,
            "load": load,
            "committed_state_sha256": self.committed.fingerprint,
            "persistent_compatibility": "EXACT_AUTHORITATIVE_VERSION_AND_HASH",
            "persistent_version": self.committed.accepted_version,
            "persistent_sha256": canonical_hash(authoritative_persistent),
            "residual_version": RESIDUAL_VERSION,
            "tangent_version": TANGENT_VERSION,
        }

    def _material_update(self, displacement: np.ndarray) -> CandidateState:
        grad_w = np.asarray(self.basis.interpolate(displacement).grad)
        p_base = self.committed.plastic_strain
        k_base = self.committed.kappa
        if self.variant == "unsafe_trial_cache":
            mu = self.mutation_strength
            p_base = p_base + mu * (self.persistent.hidden_plastic_strain - p_base)
            k_base = k_base + mu * (self.persistent.hidden_kappa - k_base)

        output_feedback = np.zeros_like(k_base)
        if self.variant == "unsafe_output_feedback":
            output_feedback = self.mutation_strength * self.material.hardening_modulus * self.persistent.output_mirror_kappa

        trial_stress = self.material.shear_modulus * (grad_w - p_base)
        radius = np.linalg.norm(trial_stress, axis=0)
        yield_radius = self.yield_field + self.material.hardening_modulus * k_base + output_feedback
        yield_function = radius - yield_radius
        plastic = yield_function > 0.0
        safe_radius = np.where(radius > 1.0e-30, radius, 1.0)
        direction = trial_stress / safe_radius[None, ...]
        delta_lambda = np.where(
            plastic,
            yield_function / (self.material.shear_modulus + self.material.hardening_modulus),
            0.0,
        )
        plastic_strain = p_base + direction * delta_lambda[None, ...]
        kappa = k_base + delta_lambda
        stress = trial_stress - self.material.shear_modulus * direction * delta_lambda[None, ...]

        eye = np.eye(2)[:, :, None, None]
        outer = np.einsum("i...,j...->ij...", direction, direction)
        q = np.linalg.norm(stress, axis=0)
        tangential_ratio = np.where(radius > 1.0e-30, q / safe_radius, 1.0)
        radial_ratio = self.material.hardening_modulus / (
            self.material.shear_modulus + self.material.hardening_modulus
        )
        material_tangent = self.material.shear_modulus * (
            tangential_ratio[None, None, ...] * (eye - outer)
            + radial_ratio * outer
        )
        material_tangent[:, :, ~plastic] = self.material.shear_modulus * eye[:, :, 0, 0][:, :, None]

        candidate = CandidateState(plastic_strain, kappa, stress, material_tangent)
        if self.variant == "unsafe_trial_cache":
            self.persistent.hidden_plastic_strain = candidate.plastic_strain.copy()
            self.persistent.hidden_kappa = candidate.kappa.copy()
            self.persistent.version += 1
        elif self.variant == "unsafe_output_feedback":
            self.persistent.output_mirror_kappa = candidate.kappa.copy()
            self.persistent.version += 1
        return candidate

    def evaluate(self, displacement: np.ndarray, load: float, role: str) -> OperatorPacket:
        displacement = np.asarray(displacement, dtype=float).copy()
        candidate = self._material_update(displacement)
        residual = asm(
            residual_form,
            self.basis,
            stress=DiscreteField(candidate.stress),
        )
        tangent = asm(
            tangent_form,
            self.basis,
            material_tangent=DiscreteField(candidate.tangent),
        )
        declared = self._declared_packet(displacement, load)
        packet = OperatorPacket(
            displacement=displacement,
            load=float(load),
            residual=np.asarray(residual),
            tangent=tangent,
            candidate=candidate,
            declared_fingerprint=canonical_hash(declared),
            persistent_fingerprint=self.persistent.fingerprint,
        )
        self.ledger.add(
            "TrialEvaluate",
            role=role,
            load=float(load),
            committed_sha256=self.committed.fingerprint,
            persistent_sha256=packet.persistent_fingerprint,
            declared_sha256=packet.declared_fingerprint,
            candidate_sha256=candidate.fingerprint,
            residual_norm=float(np.linalg.norm(packet.residual[self.free])),
            tangent_norm=float(np.linalg.norm(packet.tangent.data)),
        )
        return packet

    def _initial_guess(self, target_load: float, w_max: float) -> np.ndarray:
        displacement = self.committed.displacement.copy()
        y = self.mesh.p[1]
        increment = (target_load - self.committed.load) * w_max
        displacement += increment * y
        displacement[self.bottom] = 0.0
        displacement[self.top] = target_load * w_max
        return displacement

    def _record_accept(self, packet: OperatorPacket, iterations: int) -> None:
        before = self.committed.fingerprint
        self.committed = CommittedState(
            packet.displacement.copy(),
            packet.candidate.plastic_strain.copy(),
            packet.candidate.kappa.copy(),
            packet.load,
            self.committed.accepted_version + 1,
        )
        if self.variant == "safe_transactional":
            self.persistent.hidden_plastic_strain = self.committed.plastic_strain.copy()
            self.persistent.hidden_kappa = self.committed.kappa.copy()
            self.persistent.output_mirror_kappa = self.committed.kappa.copy()
            self.persistent.version = self.committed.accepted_version
        reaction_top = float(np.sum(packet.residual[self.top]))
        reaction_bottom = float(np.sum(packet.residual[self.bottom]))
        balance = abs(reaction_top + reaction_bottom) / max(
            1.0, abs(reaction_top), abs(reaction_bottom)
        )
        row = {
            "accepted_version": self.committed.accepted_version,
            "load": self.committed.load,
            "iterations": iterations,
            "residual_norm": float(np.linalg.norm(packet.residual[self.free])),
            "reaction_top": reaction_top,
            "reaction_bottom": reaction_bottom,
            "reaction_balance": balance,
            "max_kappa": float(np.max(self.committed.kappa)),
            "committed_before_sha256": before,
            "committed_after_sha256": self.committed.fingerprint,
            "candidate_sha256": packet.candidate.fingerprint,
        }
        self.accepted_rows.append(row)
        self.ledger.add("AcceptIncrement", **row)
        self.ledger.add(
            "OutputAcceptedState",
            accepted_version=self.committed.accepted_version,
            committed_sha256=self.committed.fingerprint,
            source="authoritative_committed_state",
        )

    def solve_increment(
        self,
        target_load: float,
        w_max: float,
        inject_rejected_probe: bool = False,
        force_attempt_cap: int | None = None,
        version_mismatch: bool = False,
    ) -> tuple[bool, str, OperatorPacket | None]:
        snapshot = self.committed.clone()
        persistent_snapshot = self.persistent.clone()
        self.ledger.add(
            "BeginAttempt",
            target_load=float(target_load),
            committed_sha256=snapshot.fingerprint,
            persistent_sha256=persistent_snapshot.fingerprint,
        )
        displacement = self._initial_guess(target_load, w_max)
        first_norm: float | None = None
        probe_done = False
        last_packet: OperatorPacket | None = None

        for iteration in range(1, 21):
            packet = self.evaluate(displacement, target_load, "newton_state")
            last_packet = packet
            residual_norm = float(np.linalg.norm(packet.residual[self.free]))
            if first_norm is None:
                first_norm = residual_norm
            tolerance = max(1.0e-11, 1.0e-10 * first_norm)
            self.ledger.add(
                "FormResidual",
                target_load=float(target_load),
                iteration=iteration,
                residual_norm=residual_norm,
                residual_version=RESIDUAL_VERSION,
            )
            self.ledger.add(
                "FormTangent",
                target_load=float(target_load),
                iteration=iteration,
                tangent_version=("FEH-K-STALE" if version_mismatch else TANGENT_VERSION),
            )
            if version_mismatch:
                self.ledger.add(
                    "RejectOperatorVersionMismatch",
                    target_load=float(target_load),
                    before_correction=True,
                    before_commit=True,
                    before_output=True,
                )
                self.committed = snapshot
                if self.variant == "safe_transactional":
                    self.persistent = persistent_snapshot
                return False, "VERSION_MISMATCH", packet
            if residual_norm <= tolerance:
                self._record_accept(packet, iteration)
                return True, "ACCEPTED", packet
            if force_attempt_cap is not None and iteration >= force_attempt_cap:
                self.ledger.add(
                    "RejectAttempt",
                    reason="predeclared_iteration_cap",
                    target_load=float(target_load),
                    iteration=iteration,
                )
                self.committed = snapshot
                if self.variant == "safe_transactional":
                    self.persistent = persistent_snapshot
                self.ledger.add(
                    "Rollback",
                    committed_sha256=self.committed.fingerprint,
                    persistent_sha256=self.persistent.fingerprint,
                )
                return False, "ATTEMPT_CAP", packet

            correction = spsolve(packet.tangent[self.free][:, self.free], -packet.residual[self.free])
            if not all_finite(correction):
                return False, "NONFINITE_CORRECTION", packet

            if inject_rejected_probe and not probe_done:
                probe = displacement.copy()
                probe[self.free] += 8.0 * correction
                probe_packet = self.evaluate(probe, target_load, "predeclared_rejected_alpha_8")
                probe_norm = float(np.linalg.norm(probe_packet.residual[self.free]))
                armijo_limit = (1.0 - 1.0e-4 * 8.0) * residual_norm
                if probe_norm <= armijo_limit:
                    return False, "PROBE_UNEXPECTEDLY_ACCEPTABLE", probe_packet
                self.ledger.add(
                    "RejectLineSearch",
                    target_load=float(target_load),
                    alpha=8.0,
                    residual_norm=probe_norm,
                    armijo_limit=armijo_limit,
                )
                probe_done = True

            accepted_alpha = None
            for alpha in (1.0, 0.5, 0.25, 0.125):
                trial = displacement.copy()
                trial[self.free] += alpha * correction
                trial_packet = self.evaluate(trial, target_load, "armijo_candidate")
                trial_norm = float(np.linalg.norm(trial_packet.residual[self.free]))
                if trial_norm <= (1.0 - 1.0e-4 * alpha) * residual_norm or trial_norm < tolerance:
                    displacement = trial
                    accepted_alpha = alpha
                    self.ledger.add(
                        "AcceptLineSearch",
                        target_load=float(target_load),
                        alpha=alpha,
                        residual_norm=trial_norm,
                    )
                    break
                self.ledger.add(
                    "RejectLineSearch",
                    target_load=float(target_load),
                    alpha=alpha,
                    residual_norm=trial_norm,
                )
            if accepted_alpha is None:
                self.committed = snapshot
                if self.variant == "safe_transactional":
                    self.persistent = persistent_snapshot
                self.ledger.add("Rollback", reason="line_search_exhausted")
                return False, "LINE_SEARCH_EXHAUSTED", last_packet

        self.committed = snapshot
        if self.variant == "safe_transactional":
            self.persistent = persistent_snapshot
        self.ledger.add("Rollback", reason="newton_iteration_limit")
        return False, "ITERATION_LIMIT", last_packet

    def checkpoint_payload(self) -> dict[str, Any]:
        state = self.committed
        return {
            "serializer_version": SERIALIZER_VERSION,
            "nx": self.nx,
            "ny": self.ny,
            "heterogeneous": self.heterogeneous,
            "variant": self.variant,
            "mutation_strength": self.mutation_strength,
            "material": self.material.__dict__,
            "displacement_hex": [float(v).hex() for v in state.displacement],
            "plastic_strain_hex": [float(v).hex() for v in state.plastic_strain.ravel(order="C")],
            "plastic_strain_shape": list(state.plastic_strain.shape),
            "kappa_hex": [float(v).hex() for v in state.kappa.ravel(order="C")],
            "kappa_shape": list(state.kappa.shape),
            "load_hex": float(state.load).hex(),
            "accepted_version": state.accepted_version,
            "committed_sha256": state.fingerprint,
        }

    @classmethod
    def from_checkpoint(cls, payload: dict[str, Any], history_id: str) -> "FEHost":
        host = cls(
            payload["nx"],
            payload["ny"],
            payload["heterogeneous"],
            payload["variant"],
            payload["mutation_strength"],
            history_id,
            MaterialParameters(**payload["material"]),
        )
        displacement = np.array([float.fromhex(v) for v in payload["displacement_hex"]])
        plastic = np.array([float.fromhex(v) for v in payload["plastic_strain_hex"]]).reshape(
            payload["plastic_strain_shape"]
        )
        kappa = np.array([float.fromhex(v) for v in payload["kappa_hex"]]).reshape(
            payload["kappa_shape"]
        )
        state = CommittedState(
            displacement,
            plastic,
            kappa,
            float.fromhex(payload["load_hex"]),
            int(payload["accepted_version"]),
        )
        if state.fingerprint != payload["committed_sha256"]:
            raise ValueError("Checkpoint fingerprint mismatch")
        host.committed = state
        host.persistent = PersistentState(plastic.copy(), kappa.copy(), kappa.copy(), 0)
        host.ledger.add("RestartRead", committed_sha256=state.fingerprint)
        return host


def _combine_ledgers(*ledgers: EventLedger) -> EventLedger:
    combined = EventLedger("combined")
    for ledger in ledgers:
        for row in ledger.rows:
            copied = dict(row)
            copied["source_history_id"] = ledger.history_id
            copied["ordinal"] = len(combined.rows) + 1
            combined.rows.append(copied)
    return combined


def run_history(
    history_id: str,
    variant: str = "safe_transactional",
    mutation_strength: float = 0.0,
    nx: int = 8,
    ny: int = 6,
    heterogeneous: bool = True,
    load_sequence: Iterable[float] = (0.2, 0.4, 0.6, 0.8, 1.0),
    w_max: float = 0.12,
) -> HistoryResult:
    host = FEHost(nx, ny, heterogeneous, variant, mutation_strength, history_id)
    load_sequence = tuple(float(v) for v in load_sequence)
    all_hosts = [host]
    version_rejected = False

    for target in load_sequence:
        inject = history_id == "rejected_line_search" and math.isclose(target, 0.8)
        if history_id == "cutback" and math.isclose(target, 0.8):
            ok, reason, _ = host.solve_increment(1.0, w_max, force_attempt_cap=1)
            if ok or reason != "ATTEMPT_CAP":
                return HistoryResult(history_id, "FAIL_CUTBACK_PROBE", False, host.committed, host.persistent, host.accepted_rows, host.ledger, None, False)
            host.ledger.add("CutbackAndRetry", from_load=1.0, to_load=0.8)
        if history_id == "version_mismatch" and math.isclose(target, 0.8):
            before = host.committed.fingerprint
            ok, reason, packet = host.solve_increment(target, w_max, version_mismatch=True)
            version_rejected = (
                not ok
                and reason == "VERSION_MISMATCH"
                and host.committed.fingerprint == before
            )
            return HistoryResult(
                history_id,
                "REJECT_VERSION_MISMATCH_PRE_CORRECTION" if version_rejected else "FAIL_VERSION_GATE",
                version_rejected,
                host.committed,
                host.persistent,
                host.accepted_rows,
                host.ledger,
                packet,
                packet is not None and all_finite(packet.residual, packet.tangent.data),
                version_rejected,
            )
        ok, reason, packet = host.solve_increment(
            target,
            w_max,
            inject_rejected_probe=inject,
        )
        if not ok:
            return HistoryResult(
                history_id,
                f"FAIL_{reason}",
                False,
                host.committed,
                host.persistent,
                host.accepted_rows,
                host.ledger,
                packet,
                packet is not None and all_finite(packet.residual, packet.tangent.data),
            )
        if history_id == "restart" and math.isclose(target, 0.6):
            payload = host.checkpoint_payload()
            host.ledger.add("CheckpointWrite", committed_sha256=host.committed.fingerprint)
            restarted = FEHost.from_checkpoint(payload, history_id + "_continued")
            all_hosts.append(restarted)
            host = restarted

    replay = host.evaluate(host.committed.displacement, host.committed.load, "final_replay")
    combined = _combine_ledgers(*(item.ledger for item in all_hosts)) if len(all_hosts) > 1 else host.ledger
    accepted_rows: list[dict[str, Any]] = []
    for item in all_hosts:
        accepted_rows.extend(item.accepted_rows)
    finite = all_finite(
        host.committed.displacement,
        host.committed.plastic_strain,
        host.committed.kappa,
        replay.residual,
        replay.tangent.data,
    )
    converged = len(accepted_rows) == len(load_sequence)
    balanced = all(row["reaction_balance"] <= 1.0e-9 for row in accepted_rows)
    classification = "PASS_HISTORY" if finite and converged and balanced else "FAIL_HISTORY_GATES"
    return HistoryResult(
        history_id,
        classification,
        finite and converged and balanced,
        host.committed,
        host.persistent,
        accepted_rows,
        combined,
        replay,
        finite,
        version_rejected,
    )


def compare_histories(left: HistoryResult, right: HistoryResult) -> dict[str, Any]:
    if left.replay_packet is None or right.replay_packet is None:
        raise ValueError("Both histories require replay packets")
    lp = left.replay_packet
    rp = right.replay_packet
    tangent_delta = lp.tangent - rp.tangent
    displacement_error = norm_relative(
        left.committed.displacement - right.committed.displacement,
        left.committed.displacement,
    )
    stress_error = norm_relative(
        lp.candidate.stress - rp.candidate.stress,
        lp.candidate.stress,
    )
    kappa_error = norm_relative(
        left.committed.kappa - right.committed.kappa,
        left.committed.kappa,
    )
    reaction_left = left.accepted_rows[-1]["reaction_top"]
    reaction_right = right.accepted_rows[-1]["reaction_top"]
    return {
        "left_history": left.history_id,
        "right_history": right.history_id,
        "left_pass": left.pass_flag,
        "right_pass": right.pass_flag,
        "declared_fingerprint_equal": lp.declared_fingerprint == rp.declared_fingerprint,
        "committed_fingerprint_equal": left.committed.fingerprint == right.committed.fingerprint,
        "persistent_fingerprint_equal": left.persistent.fingerprint == right.persistent.fingerprint,
        "residual_relative_drift": norm_relative(lp.residual - rp.residual, lp.residual),
        "tangent_relative_drift": float(
            np.linalg.norm(tangent_delta.data) / max(1.0, np.linalg.norm(lp.tangent.data))
        ),
        "displacement_relative_error": displacement_error,
        "reaction_relative_error": abs(reaction_left - reaction_right) / max(1.0, abs(reaction_left)),
        "stress_relative_error": stress_error,
        "kappa_relative_error": kappa_error,
        "left_balance": left.accepted_rows[-1]["reaction_balance"],
        "right_balance": right.accepted_rows[-1]["reaction_balance"],
        "all_values_finite": left.all_values_finite and right.all_values_finite,
    }


def audit_replay_pair(
    variant: str,
    mutation_strength: float,
    nx: int = 8,
    ny: int = 6,
    heterogeneous: bool = True,
    w_max: float = 0.12,
    preload_sequence: Iterable[float] = (0.2, 0.4, 0.6),
    replay_load: float = 0.8,
) -> tuple[dict[str, Any], EventLedger]:
    direct = FEHost(nx, ny, heterogeneous, variant, mutation_strength, "audit_direct")
    extra = FEHost(nx, ny, heterogeneous, variant, mutation_strength, "audit_extra")
    for target in preload_sequence:
        for host in (direct, extra):
            ok, reason, _ = host.solve_increment(float(target), w_max)
            if not ok:
                raise RuntimeError(f"Audit preload failed at {target}: {reason}")
    if direct.committed.fingerprint != extra.committed.fingerprint:
        raise RuntimeError("Audit histories do not share a common committed start")

    replay_u_direct = direct._initial_guess(replay_load, w_max)
    replay_u_extra = extra._initial_guess(replay_load, w_max)
    if not np.array_equal(replay_u_direct, replay_u_extra):
        raise RuntimeError("Audit replay primary states differ")
    direct_packet = direct.evaluate(replay_u_direct, replay_load, "equal_declared_replay")

    base_packet = extra.evaluate(replay_u_extra, replay_load, "pre_rejected_probe_base")
    correction = spsolve(
        base_packet.tangent[extra.free][:, extra.free],
        -base_packet.residual[extra.free],
    )
    probe = replay_u_extra.copy()
    probe[extra.free] += 8.0 * correction
    probe_packet = extra.evaluate(probe, replay_load, "predeclared_rejected_alpha_8")
    base_norm = float(np.linalg.norm(base_packet.residual[extra.free]))
    probe_norm = float(np.linalg.norm(probe_packet.residual[extra.free]))
    armijo_limit = (1.0 - 8.0e-4) * base_norm
    if probe_norm <= armijo_limit:
        raise RuntimeError("Frozen alpha=8 audit probe unexpectedly satisfies Armijo")
    extra.ledger.add(
        "RejectLineSearch",
        target_load=replay_load,
        alpha=8.0,
        residual_norm=probe_norm,
        armijo_limit=armijo_limit,
    )
    extra_packet = extra.evaluate(replay_u_extra, replay_load, "equal_declared_replay")

    tangent_delta = direct_packet.tangent - extra_packet.tangent
    comparison = {
        "declared_fingerprint_equal": direct_packet.declared_fingerprint == extra_packet.declared_fingerprint,
        "committed_fingerprint_equal": direct.committed.fingerprint == extra.committed.fingerprint,
        "observed_persistent_fingerprint_equal": direct_packet.persistent_fingerprint == extra_packet.persistent_fingerprint,
        "residual_relative_drift": norm_relative(
            direct_packet.residual - extra_packet.residual,
            direct_packet.residual,
        ),
        "tangent_relative_drift": float(
            np.linalg.norm(tangent_delta.data) / max(1.0, np.linalg.norm(direct_packet.tangent.data))
        ),
        "candidate_fingerprint_equal": direct_packet.candidate.fingerprint == extra_packet.candidate.fingerprint,
        "all_values_finite": all_finite(
            direct_packet.residual,
            direct_packet.tangent.data,
            extra_packet.residual,
            extra_packet.tangent.data,
        ),
    }
    return comparison, _combine_ledgers(direct.ledger, extra.ledger)


def run_holdout_history(
    variant: str,
    mutation_strength: float,
    extra_probe: bool,
) -> HistoryResult:
    history_id = "holdout_extra" if extra_probe else "holdout_direct"
    host = FEHost(10, 7, True, variant, mutation_strength, history_id)
    load_sequence = (0.15, 0.35, 0.55, 0.75, 0.9, 1.0)
    w_max = 0.11
    for target in load_sequence:
        if extra_probe and math.isclose(target, 0.75):
            probe = host._initial_guess(0.84, w_max)
            host.evaluate(probe, 0.84, "holdout_rejected_load_probe")
            host.ledger.add(
                "RejectLineSearch",
                target_load=0.75,
                probe_load=0.84,
                reason="frozen_holdout_nonaccepting_probe",
            )
        ok, reason, packet = host.solve_increment(target, w_max)
        if not ok:
            return HistoryResult(
                history_id,
                f"FAIL_{reason}",
                False,
                host.committed,
                host.persistent,
                host.accepted_rows,
                host.ledger,
                packet,
                packet is not None and all_finite(packet.residual, packet.tangent.data),
            )
    replay = host.evaluate(host.committed.displacement, host.committed.load, "holdout_final_replay")
    finite = all_finite(
        host.committed.displacement,
        host.committed.plastic_strain,
        host.committed.kappa,
        replay.residual,
        replay.tangent.data,
    )
    balanced = all(row["reaction_balance"] <= 1.0e-9 for row in host.accepted_rows)
    return HistoryResult(
        history_id,
        "PASS_HOLDOUT_HISTORY" if finite and balanced else "FAIL_HOLDOUT_GATES",
        finite and balanced,
        host.committed,
        host.persistent,
        host.accepted_rows,
        host.ledger,
        replay,
        finite,
    )


def audit_holdout_pair(
    variant: str,
    mutation_strength: float,
) -> tuple[dict[str, Any], EventLedger]:
    direct = FEHost(10, 7, True, variant, mutation_strength, "holdout_audit_direct")
    extra = FEHost(10, 7, True, variant, mutation_strength, "holdout_audit_extra")
    w_max = 0.11
    for target in (0.15, 0.35, 0.55):
        for host in (direct, extra):
            ok, reason, _ = host.solve_increment(target, w_max)
            if not ok:
                raise RuntimeError(f"Hold-out audit preload failed at {target}: {reason}")
    replay_u = direct._initial_guess(0.75, w_max)
    direct_packet = direct.evaluate(replay_u, 0.75, "equal_declared_holdout_replay")
    probe_u = extra._initial_guess(0.84, w_max)
    extra.evaluate(probe_u, 0.84, "holdout_rejected_load_probe")
    extra.ledger.add(
        "RejectLineSearch",
        target_load=0.75,
        probe_load=0.84,
        reason="frozen_holdout_nonaccepting_probe",
    )
    extra_packet = extra.evaluate(replay_u, 0.75, "equal_declared_holdout_replay")
    tangent_delta = direct_packet.tangent - extra_packet.tangent
    comparison = {
        "declared_fingerprint_equal": direct_packet.declared_fingerprint == extra_packet.declared_fingerprint,
        "committed_fingerprint_equal": direct.committed.fingerprint == extra.committed.fingerprint,
        "observed_persistent_fingerprint_equal": direct_packet.persistent_fingerprint == extra_packet.persistent_fingerprint,
        "residual_relative_drift": norm_relative(
            direct_packet.residual - extra_packet.residual,
            direct_packet.residual,
        ),
        "tangent_relative_drift": float(
            np.linalg.norm(tangent_delta.data) / max(1.0, np.linalg.norm(direct_packet.tangent.data))
        ),
        "all_values_finite": all_finite(
            direct_packet.residual,
            direct_packet.tangent.data,
            extra_packet.residual,
            extra_packet.tangent.data,
        ),
    }
    return comparison, _combine_ledgers(direct.ledger, extra.ledger)


def patch_oracle(w_max: float = 0.12, material: MaterialParameters | None = None) -> dict[str, float]:
    params = material or MaterialParameters()
    gamma = w_max
    trial = params.shear_modulus * gamma
    if trial <= params.yield_stress:
        stress = trial
        kappa = 0.0
    else:
        delta_lambda = (trial - params.yield_stress) / (
            params.shear_modulus + params.hardening_modulus
        )
        stress = trial - params.shear_modulus * delta_lambda
        kappa = delta_lambda
    return {"stress": stress, "reaction": stress, "kappa": kappa}


def case_payload(result: HistoryResult) -> dict[str, Any]:
    replay = result.replay_packet
    return {
        "history_id": result.history_id,
        "classification": result.classification,
        "pass_flag": result.pass_flag,
        "committed_state_sha256": result.committed.fingerprint,
        "persistent_state_sha256": result.persistent.fingerprint,
        "accepted_increment_count": len(result.accepted_rows),
        "all_values_finite": result.all_values_finite,
        "version_rejected_before_correction": result.version_rejected_before_correction,
        "replay_declared_sha256": None if replay is None else replay.declared_fingerprint,
        "replay_residual_norm": None if replay is None else float(np.linalg.norm(replay.residual)),
        "replay_tangent_norm": None if replay is None else float(np.linalg.norm(replay.tangent.data)),
        "max_kappa": float(np.max(result.committed.kappa)),
    }
