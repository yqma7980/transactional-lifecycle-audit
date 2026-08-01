from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from p6r_contracts import IMPLEMENTATION_VERSION, METHOD_IDS, canonical_hash, canonical_json, require_descendant
from p6r_detectors import detect_projection
from p6r_loader import load_raw_bundle
from p6r_projection import build_method_projection


def execute_one_projection_process(
    *,
    ncs_root: Path,
    study_root: Path,
    implementation_root: Path,
    results_root: Path,
    execution_tag: str,
    case_id: str,
    repetition: int,
) -> Path:
    authorized_parent = implementation_root / "results"
    require_descendant(results_root, authorized_parent)
    if not execution_tag.startswith("P6R_FORMAL_"):
        raise ValueError("execution tag must start with P6R_FORMAL_")
    output_dir = results_root / execution_tag / case_id / f"rep_{repetition}"
    require_descendant(output_dir, authorized_parent)
    if output_dir.exists():
        raise FileExistsError(f"formal projection output already exists: {output_dir}")

    # All immutable inputs and detector packets are built before any output path exists.
    bundle = load_raw_bundle(ncs_root, study_root, case_id, repetition)
    projections = [build_method_projection(method_id, bundle) for method_id in METHOD_IDS]
    detections = [detect_projection(packet) for packet in projections]

    output_dir.mkdir(parents=True, exist_ok=False)
    packet_records = [
        {
            "method_id": packet.method_id,
            "schema_version": packet.schema_version,
            "applicable": packet.applicable,
            "payload_sha256": packet.payload_sha256,
            "payload": packet.payload,
        }
        for packet in projections
    ]
    (output_dir / "projection_packets.json").write_text(
        json.dumps(json.loads(canonical_json(packet_records)), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    fieldnames = (
        "method_id",
        "applicable",
        "anomaly_detected",
        "classification",
        "localization_plane",
    )
    with (output_dir / "method_results.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        for result in detections:
            writer.writerow({key: getattr(result, key) for key in fieldnames})
    manifest = {
        "implementation_version": IMPLEMENTATION_VERSION,
        "execution_tag": execution_tag,
        "case_id": case_id,
        "repetition": repetition,
        "p5_run_id": bundle.p5_run_id,
        "raw_file_hashes": dict(bundle.file_hashes),
        "method_packet_hashes": {packet.method_id: packet.payload_sha256 for packet in projections},
        "detection_hash": canonical_hash([asdict(result) for result in detections]),
        "new_fe_solve_executed": False,
        "abaqus_used": False,
    }
    (output_dir / "projection_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output_dir

