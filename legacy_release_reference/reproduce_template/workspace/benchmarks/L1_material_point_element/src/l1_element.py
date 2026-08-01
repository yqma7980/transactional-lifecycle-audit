"""One-point two-node bar operator for standalone L1-E1."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .l1_state import (
    CandidateState,
    CommittedState,
    MaterialData,
    MaterialResult,
    OutputSnapshot,
    canonical_hash,
)


@dataclass(frozen=True)
class ElementData:
    area: float = 1.0
    length: float = 1.0
    u1: float = 0.0
    operator_version: str = "L1-E1-1.0"

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)


@dataclass(frozen=True)
class ElementResult:
    u: float
    force: float
    epsilon: float
    residual: float
    tangent: float
    material_result: MaterialResult
    declared_packet_hash: str
    operator_version: str
    residual_state_version: str
    tangent_state_version: str
    seeded_version_mismatch: bool = False

    @property
    def candidate(self) -> CandidateState:
        return self.material_result.candidate

    @property
    def sigma(self) -> float:
        return self.material_result.sigma

    @property
    def E_alg(self) -> float:
        return self.material_result.E_alg

    @property
    def finite(self) -> bool:
        return all(
            math.isfinite(value)
            for value in (
                self.u,
                self.force,
                self.epsilon,
                self.residual,
                self.tangent,
                self.sigma,
                self.E_alg,
            )
        )

    @property
    def version_compatible(self) -> bool:
        return self.residual_state_version == self.tangent_state_version

    @property
    def residual_fingerprint(self) -> str:
        return canonical_hash(
            {
                "declared_packet_hash": self.declared_packet_hash,
                "residual": self.residual,
                "state_version": self.residual_state_version,
            }
        )

    @property
    def tangent_fingerprint(self) -> str:
        return canonical_hash(
            {
                "declared_packet_hash": self.declared_packet_hash,
                "tangent": self.tangent,
                "state_version": self.tangent_state_version,
            }
        )

    @property
    def operator_fingerprint(self) -> str:
        return canonical_hash(
            {
                "declared_packet_hash": self.declared_packet_hash,
                "operator_version": self.operator_version,
                "residual": self.residual,
                "tangent": self.tangent,
                "residual_state_version": self.residual_state_version,
                "tangent_state_version": self.tangent_state_version,
            }
        )


@dataclass(frozen=True)
class ElementOutputSnapshot:
    accepted_version: int
    epsilon_p: float
    kappa: float
    source_version: str
    source_candidate_id: str
    operator_version: str
    configuration_hash: str

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self)

    @property
    def accepted_source_valid(self) -> bool:
        return (
            self.source_version == f"accepted:{self.accepted_version}"
            and self.source_candidate_id == "NA"
        )


def declared_element_packet_hash(
    *,
    case_id: str,
    variant_name: str,
    committed: CommittedState,
    material: MaterialData,
    element: ElementData,
    configuration_hash: str,
    u: float,
    force: float,
) -> str:
    return canonical_hash(
        {
            "design_version": "L1-D1.0",
            "case_id": case_id,
            "sublevel": "L1-E1",
            "variant": variant_name,
            "accepted_version": committed.accepted_version,
            "committed_state_hash": committed.fingerprint,
            "material_parameters_hash": material.fingerprint,
            "element_configuration_hash": element.fingerprint,
            "configuration_hash": configuration_hash,
            "operator_version": element.operator_version,
            "u": u,
            "force": force,
            "requested_outputs": ["sigma", "R", "K", "candidate", "state_versions"],
        }
    )


def evaluate_element(
    variant: Any,
    element: ElementData,
    *,
    case_id: str,
    configuration_hash: str,
    u: float,
    force: float,
    candidate_id: str,
    attempt_id: str,
    source_call_index: int,
    seeded_version_mismatch: bool = False,
) -> ElementResult:
    if element.length <= 0.0 or element.area <= 0.0:
        raise ValueError("Element area and length must be positive")

    committed = variant.committed
    packet_hash = declared_element_packet_hash(
        case_id=case_id,
        variant_name=variant.name,
        committed=committed,
        material=variant.material,
        element=element,
        configuration_hash=configuration_hash,
        u=u,
        force=force,
    )
    epsilon = (u - element.u1) / element.length
    material_result = variant.evaluate(
        epsilon,
        candidate_id=candidate_id,
        attempt_id=attempt_id,
        source_call_index=source_call_index,
    )
    residual = element.area * material_result.sigma - force
    tangent = element.area * material_result.E_alg / element.length
    residual_version = material_result.residual_state_version
    tangent_version = (
        f"seeded-mismatch:{material_result.tangent_state_version}"
        if seeded_version_mismatch
        else material_result.tangent_state_version
    )
    result = ElementResult(
        u=u,
        force=force,
        epsilon=epsilon,
        residual=residual,
        tangent=tangent,
        material_result=material_result,
        declared_packet_hash=packet_hash,
        operator_version=element.operator_version,
        residual_state_version=residual_version,
        tangent_state_version=tangent_version,
        seeded_version_mismatch=seeded_version_mismatch,
    )
    if not result.finite:
        raise FloatingPointError("Non-finite element output")
    return result


def read_element_output(
    variant: Any,
    element: ElementData,
    *,
    trigger_u: float,
    configuration_hash: str,
) -> ElementOutputSnapshot:
    material_snapshot: OutputSnapshot = variant.terminal_read(
        (trigger_u - element.u1) / element.length
    )
    return ElementOutputSnapshot(
        accepted_version=material_snapshot.accepted_version,
        epsilon_p=material_snapshot.epsilon_p,
        kappa=material_snapshot.kappa,
        source_version=material_snapshot.source_version,
        source_candidate_id=material_snapshot.source_candidate_id,
        operator_version=element.operator_version,
        configuration_hash=configuration_hash,
    )

