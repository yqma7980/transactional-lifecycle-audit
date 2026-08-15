import argparse
import csv
import hashlib
import json
import math
import subprocess
from pathlib import Path


CASE_ORDER = [
    ("OS-B01", "PASS_INVARIANT", "BENIGN", "NONE"),
    ("OS-B02", "PASS_INVARIANT", "BENIGN", "NONE"),
    ("OS-F01", "DETECT_LIFECYCLE_DRIFT", "PREMATURE_COMMIT", "C01_PREMATURE_COMMIT"),
    ("OS-F02", "DETECT_LIFECYCLE_DRIFT", "PREMATURE_COMMIT", "C01_PREMATURE_COMMIT"),
    ("OS-F03", "DETECT_LIFECYCLE_DRIFT", "ROLLBACK_OMISSION", "C02_ROLLBACK_DISPATCH"),
    ("OS-F04", "DETECT_LIFECYCLE_DRIFT", "PERSISTENT_HISTORY_ESCAPE", "C03_EXTERNAL_STATE_OWNER"),
    ("OS-I01", "INVALID_COMPARISON", "INVALID_CONTROL", "NONE"),
    ("OS-U01", "UNSUPPORTED_OBSERVATION", "UNSUPPORTED_CONTROL", "NONE"),
]

CANDIDATES = [
    "C01_PREMATURE_COMMIT",
    "C02_ROLLBACK_DISPATCH",
    "C03_EXTERNAL_STATE_OWNER",
    "C04_OPERATOR_VERSION",
    "C05_OUTPUT_PROVENANCE",
    "C06_OBSERVABILITY_COVERAGE",
]

DRIFT_GATE = 1.0e-12
REPETITIONS = 3


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def normalized_difference(left: float, right: float) -> float:
    return abs(left - right) / max(1.0, abs(left))


def classify(record: dict) -> tuple[str, list[str], float]:
    if not record["observation_coverage"]:
        return "UNSUPPORTED_OBSERVATION", ["observation_coverage_missing"], 0.0
    if not record["comparison_eligible"]:
        return "INVALID_COMPARISON", ["declared_replay_target_mismatch"], 0.0

    drift = max(
        normalized_difference(record["reference_stress"], record["reported_stress"]),
        normalized_difference(record["reference_tangent"], record["reported_tangent"]),
    )
    signals = []
    for key in (
        "commit_violation",
        "rollback_omission",
        "ownership_violation",
        "output_provenance_violation",
        "operator_version_incompatibility",
    ):
        if record[key]:
            signals.append(key)
    if drift > DRIFT_GATE:
        signals.append("operator_replay_drift")
    verdict = "DETECT_LIFECYCLE_DRIFT" if signals else "PASS_INVARIANT"
    return verdict, signals, drift


def rank_candidates(record: dict, signals: list[str]) -> list[tuple[str, int]]:
    scores = {candidate: 0 for candidate in CANDIDATES}
    if record["commit_violation"]:
        scores["C01_PREMATURE_COMMIT"] += 5
    if record["rollback_omission"]:
        scores["C02_ROLLBACK_DISPATCH"] += 5
    if record["ownership_violation"]:
        scores["C03_EXTERNAL_STATE_OWNER"] += 5
    if record["operator_version_incompatibility"]:
        scores["C04_OPERATOR_VERSION"] += 5
    if record["output_provenance_violation"]:
        scores["C03_EXTERNAL_STATE_OWNER"] += 2
        scores["C05_OUTPUT_PROVENANCE"] += 5
    if not record["observation_coverage"]:
        scores["C06_OBSERVABILITY_COVERAGE"] += 5
    if "operator_replay_drift" in signals:
        for candidate in CANDIDATES[:5]:
            scores[candidate] += 1
    order = {candidate: index for index, candidate in enumerate(CANDIDATES)}
    return sorted(scores.items(), key=lambda item: (-item[1], order[item[0]]))


def semantic_hash(record: dict) -> str:
    projected = {key: value for key, value in record.items() if key != "run_id"}
    blob = json.dumps(projected, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(blob).hexdigest().upper()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--preregistration", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    preregistration_sha = sha256(args.preregistration)
    raw_records = []

    for case_id, expected, fault_family, injected_candidate in CASE_ORDER:
        for repetition in range(1, REPETITIONS + 1):
            run_id = f"run_{repetition:02d}"
            completed = subprocess.run(
                [str(args.exe), case_id, run_id],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"{case_id}/{run_id} exited {completed.returncode}: {completed.stderr}"
                )
            lines = [line for line in completed.stdout.splitlines() if line.strip()]
            if len(lines) != 1:
                raise RuntimeError(f"{case_id}/{run_id} produced {len(lines)} nonempty lines")
            record = json.loads(lines[0])
            if record["case_id"] != case_id or record["run_id"] != run_id:
                raise RuntimeError(f"identity mismatch for {case_id}/{run_id}")
            if record["expected_verdict"] != expected:
                raise RuntimeError(f"expected-verdict mismatch for {case_id}")
            if record["fault_family"] != fault_family:
                raise RuntimeError(f"fault-family mismatch for {case_id}")
            if record["injected_candidate"] != injected_candidate:
                raise RuntimeError(f"candidate mismatch for {case_id}")
            verdict, signals, drift = classify(record)
            ranking = rank_candidates(record, signals)
            record.update(
                observed_verdict=verdict,
                active_signals=signals,
                normalized_operator_drift=drift,
                verdict_match=(verdict == expected),
                semantic_sha256=semantic_hash(record),
                localization_ranking=[candidate for candidate, _ in ranking],
                localization_scores={candidate: score for candidate, score in ranking},
                preregistration_sha256=preregistration_sha,
            )
            raw_records.append(record)

    jsonl_path = args.output_dir / "OPEN_SEES_NATIVE_HOST_RUNS.jsonl"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as stream:
        for record in raw_records:
            stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")

    case_rows = []
    localization_rows = []
    adverse = []
    for case_id, expected, fault_family, injected_candidate in CASE_ORDER:
        runs = [record for record in raw_records if record["case_id"] == case_id]
        verdicts = {record["observed_verdict"] for record in runs}
        semantic_hashes = {record["semantic_sha256"] for record in runs}
        observed = next(iter(verdicts)) if len(verdicts) == 1 else "NONREPRODUCIBLE"
        signals = sorted({signal for record in runs for signal in record["active_signals"]})
        first = runs[0]
        case_rows.append(
            {
                "case_id": case_id,
                "fault_family": fault_family,
                "expected_verdict": expected,
                "observed_verdict": observed,
                "verdict_match": observed == expected,
                "fresh_process_repetitions": len(runs),
                "semantic_reproducibility": len(semantic_hashes) == 1,
                "active_signals": ";".join(signals),
                "normalized_operator_drift": max(r["normalized_operator_drift"] for r in runs),
                "reference_stress": first["reference_stress"],
                "reported_stress": first["reported_stress"],
                "reference_tangent": first["reference_tangent"],
                "reported_tangent": first["reported_tangent"],
                "injected_candidate": injected_candidate,
                "top_ranked_candidate": first["localization_ranking"][0],
                "preregistration_sha256": preregistration_sha,
            }
        )
        if observed != expected or len(semantic_hashes) != 1:
            adverse.append(case_id)
        if injected_candidate != "NONE":
            ranking = first["localization_ranking"]
            rank = ranking.index(injected_candidate) + 1
            localization_rows.append(
                {
                    "case_id": case_id,
                    "fault_family": fault_family,
                    "injected_candidate": injected_candidate,
                    "rank": rank,
                    "top1": rank == 1,
                    "reciprocal_rank": 1.0 / rank,
                    "candidate_count": len(CANDIDATES),
                    "ranking": ";".join(ranking),
                }
            )

    results_path = args.output_dir / "OPEN_SEES_NATIVE_HOST_RESULTS.csv"
    with results_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(case_rows[0]))
        writer.writeheader()
        writer.writerows(case_rows)

    localization_path = args.output_dir / "OPEN_SEES_NATIVE_HOST_LOCALIZATION.csv"
    with localization_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(localization_rows[0]))
        writer.writeheader()
        writer.writerows(localization_rows)

    validation = {
        "classification": "PASS" if not adverse else "PASS_WITH_ADVERSE_RESULTS_RETAINED",
        "native_host": "OpenSees 3.8.0",
        "lifecycle_tier": "TIER_A_NATIVE_MATERIAL_API",
        "case_count": len(case_rows),
        "fresh_process_run_count": len(raw_records),
        "expected_verdict_matches": sum(row["verdict_match"] for row in case_rows),
        "semantic_reproducibility_matches": sum(row["semantic_reproducibility"] for row in case_rows),
        "benign_controls_quiet": all(
            row["observed_verdict"] == "PASS_INVARIANT"
            for row in case_rows
            if row["fault_family"] == "BENIGN"
        ),
        "fault_case_top1": sum(row["top1"] for row in localization_rows),
        "fault_case_count": len(localization_rows),
        "adverse_or_missed_case_ids": adverse,
        "old_17_case_matrix_recomputed": False,
        "old_mcnemar_p_recomputed": False,
        "population_inference_authorized": False,
        "preregistration_sha256": preregistration_sha,
        "executable_sha256": sha256(args.exe),
        "results_sha256": sha256(results_path),
        "runs_sha256": sha256(jsonl_path),
        "localization_sha256": sha256(localization_path),
    }
    validation_path = args.output_dir / "OPEN_SEES_NATIVE_HOST_VALIDATION.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(validation, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
