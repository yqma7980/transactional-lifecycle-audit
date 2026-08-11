from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

from src.p5c_localization import execute_case


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute-authorized", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if not args.execute_authorized or os.environ.get("P5C_EXECUTION_AUTHORIZED") != "YES":
        raise SystemExit("P5C execution requires both the CLI and environment authorization locks")
    packet = execute_case(root, args.case_id, args.run_id)
    if packet["case"]["partition"] == "HELD_OUT":
        activation = root / "qa" / "P5C_heldout_activation.json"
        if os.environ.get("P5C_HELDOUT_AUTHORIZED") != "YES" or not activation.exists():
            raise SystemExit("Held-out execution remains locked")
        state = json.loads(activation.read_text(encoding="utf-8"))
        if state.get("status") != "HELDOUT_ACTIVATED_AFTER_DEVELOPMENT_FREEZE":
            raise SystemExit("Held-out activation record is invalid")
    out = root / "results" / packet["case"]["partition"].lower() / args.case_id / args.run_id
    if out.exists():
        raise SystemExit(f"Refusing to overwrite existing result directory: {out}")
    out.mkdir(parents=True)
    result_path = out / "case_result.json"
    ranking_path = out / "localization_ranking.csv"
    ledger_path = out / "event_ledger.csv"
    _write_json(result_path, packet["result"])
    with ranking_path.open("w", encoding="utf-8", newline="") as handle:
        fields = ["method_id", "case_id", "candidate_id", "rank", "score", "reason_code"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for method in ("b3_ranking", "b6_ranking"):
            writer.writerows(packet["result"][method])
    with ledger_path.open("w", encoding="utf-8", newline="") as handle:
        fields = ["case_id", "run_id", "ordinal", "event", "owner", "field_or_packet", "source_plane", "anomaly"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in packet["ledger"]:
            writer.writerow({"case_id": args.case_id, "run_id": args.run_id, **row})
    manifest = {
        "case_id": args.case_id,
        "run_id": args.run_id,
        "outputs": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (result_path, ranking_path, ledger_path)
        },
        "manifest_self_hash_embedded": False,
    }
    _write_json(out / "case_manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

