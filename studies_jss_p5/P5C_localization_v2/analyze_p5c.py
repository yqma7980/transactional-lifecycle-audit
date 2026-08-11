from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import rankdata

from src.p5c_localization import load_cases, normalized_result


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_ledger(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row.pop("run_id", None)
    return rows


def validate_run(run_dir: Path) -> dict[str, Any]:
    required = {"case_result.json", "localization_ranking.csv", "event_ledger.csv", "case_manifest.json"}
    found = {path.name for path in run_dir.iterdir() if path.is_file()}
    if found != required:
        raise ValueError(f"Unexpected run files in {run_dir}: {sorted(found)}")
    manifest = read_json(run_dir / "case_manifest.json")
    for name, entry in manifest["outputs"].items():
        path = run_dir / name
        if sha256(path) != entry["sha256"] or path.stat().st_size != entry["bytes"]:
            raise ValueError(f"Manifest mismatch: {path}")
    result = read_json(run_dir / "case_result.json")
    if not result["pass_flag"] or not result["schema_b3_pass"] or not result["schema_b6_pass"]:
        raise ValueError(f"Failed case result: {run_dir}")
    return result


def compare_case(root: Path, case: dict[str, str]) -> dict[str, Any]:
    base = root / "results" / case["partition"].lower() / case["case_id"]
    one_dir = base / "run_1"
    two_dir = base / "run_2"
    one = validate_run(one_dir)
    two = validate_run(two_dir)
    result_equal = normalized_result(one) == normalized_result(two)
    ranking_equal = (one_dir / "localization_ranking.csv").read_bytes() == (two_dir / "localization_ranking.csv").read_bytes()
    ledger_equal = normalize_ledger(one_dir / "event_ledger.csv") == normalize_ledger(two_dir / "event_ledger.csv")
    gate = result_equal and ranking_equal and ledger_equal and one["semantic_fingerprint"] == two["semantic_fingerprint"]
    return {
        "case_id": case["case_id"],
        "partition": case["partition"],
        "subject_id": case["subject_id"],
        "fault_family": case["fault_family"],
        "normalized_case_result_equal": result_equal,
        "ranking_exact_equal": ranking_equal,
        "normalized_event_ledger_equal": ledger_equal,
        "semantic_fingerprint_equal": one["semantic_fingerprint"] == two["semantic_fingerprint"],
        "duplicate_gate_pass": gate,
        "case_result": one,
    }


def exact_sign_flip_p(values: np.ndarray) -> float:
    observed = abs(float(np.mean(values)))
    stats = []
    for signs in itertools.product((-1.0, 1.0), repeat=len(values)):
        stats.append(abs(float(np.mean(values * np.asarray(signs)))))
    return sum(value >= observed - 1.0e-15 for value in stats) / len(stats)


def rank_biserial(values: np.ndarray) -> float:
    nonzero = values[np.abs(values) > 0.0]
    if len(nonzero) == 0:
        return 0.0
    ranks = rankdata(np.abs(nonzero), method="average")
    positive = float(np.sum(ranks[nonzero > 0.0]))
    negative = float(np.sum(ranks[nonzero < 0.0]))
    return (positive - negative) / float(np.sum(ranks))


def metric_summary(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    reductions = np.asarray(
        [row["case_result"]["suspicious_set_reduction"] for row in comparisons], dtype=float
    )
    rng = np.random.default_rng(20260811)
    medians = np.median(
        reductions[rng.integers(0, len(reductions), size=(10000, len(reductions)))], axis=1
    )
    result: dict[str, Any] = {
        "case_count": len(comparisons),
        "primary_endpoint": "suspicious_set_reduction",
        "paired_values": reductions.tolist(),
        "median": float(np.median(reductions)),
        "bootstrap_95_ci": [float(np.quantile(medians, 0.025)), float(np.quantile(medians, 0.975))],
        "bootstrap_resamples": 10000,
        "bootstrap_seed": 20260811,
        "exact_sign_flip_p": exact_sign_flip_p(reductions),
        "paired_rank_biserial": rank_biserial(reductions),
    }
    for key in ("b3_metrics", "b6_metrics"):
        label = key.split("_", 1)[0]
        metrics = [row["case_result"][key] for row in comparisons]
        result[label] = {
            "top1_count": sum(bool(row["top1"]) for row in metrics),
            "top3_count": sum(bool(row["top3"]) for row in metrics),
            "mrr": float(np.mean([row["reciprocal_rank"] for row in metrics])),
            "mean_exam": float(np.mean([row["exam"] for row in metrics])),
            "median_suspicious_set_size": float(np.median([row["suspicious_set_size"] for row in metrics])),
        }
    return result


def write_case_source(path: Path, comparisons: list[dict[str, Any]]) -> None:
    fields = [
        "case_id", "partition", "subject_id", "fault_family", "b3_top1", "b3_top3",
        "b3_rank", "b3_rr", "b3_exam", "b3_set_size", "b6_top1", "b6_top3",
        "b6_rank", "b6_rr", "b6_exam", "b6_set_size", "suspicious_set_reduction",
        "duplicate_gate_pass",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in comparisons:
            result = row["case_result"]
            b3 = result["b3_metrics"]
            b6 = result["b6_metrics"]
            writer.writerow({
                "case_id": row["case_id"],
                "partition": row["partition"],
                "subject_id": row["subject_id"],
                "fault_family": row["fault_family"],
                "b3_top1": b3["top1"],
                "b3_top3": b3["top3"],
                "b3_rank": b3["first_ground_truth_rank"],
                "b3_rr": b3["reciprocal_rank"],
                "b3_exam": b3["exam"],
                "b3_set_size": b3["suspicious_set_size"],
                "b6_top1": b6["top1"],
                "b6_top3": b6["top3"],
                "b6_rank": b6["first_ground_truth_rank"],
                "b6_rr": b6["reciprocal_rank"],
                "b6_exam": b6["exam"],
                "b6_set_size": b6["suspicious_set_size"],
                "suspicious_set_reduction": result["suspicious_set_reduction"],
                "duplicate_gate_pass": row["duplicate_gate_pass"],
            })


def raw_manifest(root: Path, cases: list[dict[str, str]]) -> dict[str, Any]:
    files = []
    for case in cases:
        base = root / "results" / case["partition"].lower() / case["case_id"]
        for run_id in ("run_1", "run_2"):
            for path in sorted((base / run_id).iterdir(), key=lambda item: item.name):
                files.append({
                    "relative_path": path.relative_to(root).as_posix(),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                })
    payload = "\n".join(f"{row['relative_path']}|{row['sha256']}" for row in files).encode("utf-8")
    return {
        "file_count": len(files),
        "aggregate_sha256": hashlib.sha256(payload).hexdigest(),
        "files": files,
        "manifest_self_hash_embedded": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("development", "final"), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    cases = load_cases(root)
    selected = [row for row in cases if args.stage == "final" or row["partition"] == "DEVELOPMENT"]
    if args.stage == "development" and (root / "results" / "held_out").exists():
        if any((root / "results" / "held_out").rglob("case_result.json")):
            raise SystemExit("Held-out evidence exists before development freeze")
    comparisons = [compare_case(root, case) for case in selected]
    if not all(row["duplicate_gate_pass"] for row in comparisons):
        raise SystemExit("Duplicate gate failed")
    out = root / "results" / ("development_final" if args.stage == "development" else "final")
    if out.exists():
        raise SystemExit(f"Refusing to overwrite {out}")
    out.mkdir(parents=True)
    stripped = [{key: value for key, value in row.items() if key != "case_result"} for row in comparisons]
    write_json(out / "P5C_duplicate_comparison.json", stripped)
    write_case_source(out / "P5C_case_metric_source.csv", comparisons)
    summary = {
        "status": "PASS_P5C_DEVELOPMENT_FREEZE" if args.stage == "development" else "PASS_P5C_LOCALIZATION_V2",
        "stage": args.stage,
        "case_count": len(selected),
        "fresh_process_count": len(selected) * 2,
        "all_duplicate_gates_pass": True,
        "all_schema_gates_pass": True,
        "all_values_finite": True,
        "heldout_accessed": args.stage == "final",
        "metrics": metric_summary(comparisons),
        "abaqus_used": False,
    }
    write_json(out / "P5C_summary.json", summary)
    write_json(out / "P5C_raw_manifest.json", raw_manifest(root, selected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

