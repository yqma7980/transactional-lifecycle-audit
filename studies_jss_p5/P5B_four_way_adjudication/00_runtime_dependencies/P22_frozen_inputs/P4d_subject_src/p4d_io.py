from __future__ import annotations

import csv
import json
import pathlib
from dataclasses import asdict
from typing import Any

import numpy as np

from p4d_canonical import canonical_hash, file_sha256
from p4d_config import (
    DESIGN_VERSION,
    HOST_VERSION,
    IMPLEMENTATION_VERSION,
    OUTPUT_SCHEMA_VERSION,
    RESIDUAL_VERSION,
    SERIALIZER_VERSION,
    TANGENT_VERSION,
)
from p4d_state import CommittedState


def write_json_new(path: pathlib.Path, value: Any) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _little_endian(values: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(values, dtype="<f8")


def checkpoint_identity(state: CommittedState, mesh_hashes: dict[str, str], environment_hash: str) -> dict[str, Any]:
    primary = _little_endian(state.primary)
    gamma_p = _little_endian(state.gamma_p)
    alpha = _little_endian(state.alpha)
    identity = {
        "schema_version": OUTPUT_SCHEMA_VERSION,
        "design_version": DESIGN_VERSION,
        "implementation_version": IMPLEMENTATION_VERSION,
        "host_version": HOST_VERSION,
        "environment_hash": environment_hash,
        "mesh_recipe": "unit square 4x4 right-diagonal triangles",
        "mesh_hash": canonical_hash(mesh_hashes),
        "coordinates_hash": mesh_hashes["coordinates"],
        "connectivity_hash": mesh_hashes["connectivity"],
        "boundary_dof_order_hash": mesh_hashes["boundary_dof_order"],
        "quadrature_rule_hash": mesh_hashes["quadrature_rule"],
        "material_packet_hash": mesh_hashes["material"],
        "serializer_version": SERIALIZER_VERSION,
        "residual_version": RESIDUAL_VERSION,
        "tangent_relation": "EXACT_CURRENT",
        "accepted_index": state.accepted_index,
        "accepted_load_factor": state.accepted_load,
        "accepted_version": state.accepted_version,
        "primary_array_sha256": canonical_hash(primary),
        "gamma_p_array_sha256": canonical_hash(gamma_p),
        "alpha_array_sha256": canonical_hash(alpha),
    }
    identity["payload_sha256"] = canonical_hash(identity)
    return identity


def write_checkpoint(directory: pathlib.Path, state: CommittedState, mesh_hashes: dict[str, str], environment_hash: str) -> dict[str, Any]:
    if directory.exists():
        raise FileExistsError(f"refusing to overwrite checkpoint directory {directory}")
    directory.mkdir(parents=True)
    arrays_path = directory / "accepted_state_arrays.npz"
    manifest_path = directory / "checkpoint_manifest.json"
    np.savez(
        arrays_path,
        primary_w=_little_endian(state.primary),
        gamma_p=_little_endian(state.gamma_p),
        alpha=_little_endian(state.alpha),
    )
    manifest = checkpoint_identity(state, mesh_hashes, environment_hash)
    manifest["arrays_file_sha256"] = file_sha256(arrays_path)
    write_json_new(manifest_path, manifest)
    return {"manifest": manifest, "manifest_path": str(manifest_path), "arrays_path": str(arrays_path)}


def read_checkpoint(directory: pathlib.Path, expected_mesh_hashes: dict[str, str], expected_environment_hash: str) -> tuple[CommittedState, dict[str, Any]]:
    manifest = json.loads((directory / "checkpoint_manifest.json").read_text(encoding="utf-8"))
    arrays_path = directory / "accepted_state_arrays.npz"
    if file_sha256(arrays_path) != manifest["arrays_file_sha256"]:
        raise RuntimeError("checkpoint array archive hash mismatch")
    if manifest["environment_hash"] != expected_environment_hash:
        raise RuntimeError("checkpoint environment mismatch")
    if manifest["mesh_hash"] != canonical_hash(expected_mesh_hashes):
        raise RuntimeError("checkpoint mesh identity mismatch")
    with np.load(arrays_path, allow_pickle=False) as payload:
        primary = np.asarray(payload["primary_w"], dtype=np.float64)
        gamma_p = np.asarray(payload["gamma_p"], dtype=np.float64)
        alpha = np.asarray(payload["alpha"], dtype=np.float64)
    if primary.shape != (25,) or gamma_p.shape != (32, 3, 2) or alpha.shape != (32, 3):
        raise RuntimeError("checkpoint array shape mismatch")
    if canonical_hash(primary) != manifest["primary_array_sha256"]:
        raise RuntimeError("checkpoint primary hash mismatch")
    if canonical_hash(gamma_p) != manifest["gamma_p_array_sha256"]:
        raise RuntimeError("checkpoint gamma_p hash mismatch")
    if canonical_hash(alpha) != manifest["alpha_array_sha256"]:
        raise RuntimeError("checkpoint alpha hash mismatch")
    state = CommittedState(
        primary=primary,
        gamma_p=gamma_p,
        alpha=alpha,
        accepted_index=int(manifest["accepted_index"]),
        accepted_load=float(manifest["accepted_load_factor"]),
        accepted_version=int(manifest["accepted_version"]),
    )
    if canonical_hash({k: v for k, v in manifest.items() if k not in {"arrays_file_sha256", "payload_sha256"}}) != manifest["payload_sha256"]:
        raise RuntimeError("checkpoint payload identity mismatch")
    return state, manifest


class AcceptedOutputStore:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.invalid_injection_count = 0

    def append_after_commit(self, *, state: CommittedState, candidate_id: str, metrics, mesh_hashes: dict[str, str], relation: str) -> dict[str, Any]:
        row = {
            "accepted_index": state.accepted_index,
            "accepted_load_factor": state.accepted_load,
            "accepted_version": state.accepted_version,
            "selected_candidate_id": candidate_id,
            "primary_vector_hash": canonical_hash(state.primary),
            "committed_gamma_p_hash": canonical_hash(state.gamma_p),
            "committed_alpha_hash": canonical_hash(state.alpha),
            "residual_norm": metrics.residual_norm,
            "top_reaction": metrics.top_reaction,
            "bottom_reaction": metrics.bottom_reaction,
            "max_alpha": metrics.maximum_alpha,
            "plastic_point_count": metrics.plastic_point_count,
            "mesh_hash": canonical_hash(mesh_hashes),
            "material_hash": mesh_hashes["material"],
            "residual_version": RESIDUAL_VERSION,
            "tangent_relation": relation,
            "source_event": "AcceptCommit",
        }
        self.rows.append(row)
        return row

    def inject_rejected_candidate(self, *, candidate_id: str, source_load: float, target_load: float) -> dict[str, Any]:
        row = {
            "accepted_index": None,
            "accepted_load_factor": target_load,
            "accepted_version": None,
            "selected_candidate_id": candidate_id,
            "primary_vector_hash": None,
            "committed_gamma_p_hash": None,
            "committed_alpha_hash": None,
            "residual_norm": None,
            "top_reaction": None,
            "bottom_reaction": None,
            "max_alpha": None,
            "plastic_point_count": None,
            "mesh_hash": None,
            "material_hash": None,
            "residual_version": RESIDUAL_VERSION,
            "tangent_relation": "EXACT_CURRENT",
            "source_event": "FailedAttemptTrial",
            "source_load_factor": source_load,
        }
        self.rows.append(row)
        self.invalid_injection_count += 1
        return row

    def rejected_candidate_reachable(self) -> bool:
        return any(row.get("source_event") != "AcceptCommit" for row in self.rows)

    def write(self, directory: pathlib.Path) -> dict[str, str]:
        if directory.exists():
            raise FileExistsError(f"refusing to overwrite accepted output directory {directory}")
        directory.mkdir(parents=True)
        csv_path = directory / "accepted_output.csv"
        json_path = directory / "accepted_output_provenance.json"
        fields = list(self.rows[0]) if self.rows else []
        with csv_path.open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
            writer.writeheader()
            writer.writerows(self.rows)
        write_json_new(json_path, {
            "schema_version": OUTPUT_SCHEMA_VERSION,
            "row_count": len(self.rows),
            "invalid_injection_count": self.invalid_injection_count,
            "rejected_candidate_reachable": self.rejected_candidate_reachable(),
            "rows_sha256": canonical_hash(self.rows),
        })
        return {"csv_sha256": file_sha256(csv_path), "json_sha256": file_sha256(json_path)}


def metrics_to_dict(metrics) -> dict[str, Any]:
    return asdict(metrics)
