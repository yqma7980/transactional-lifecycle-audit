from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any

from .adjudicator import adjudicate
from .canonical import canonical_sha256, file_sha256, semantic_result


REQUIRED_OBSERVATIONS = (
    "database_projection",
    "persistent_projection",
    "event_ledger",
    "commit_identity",
    "output_provenance",
    "version_tuple",
)


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, isolation_level=None)
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    return connection


def _initialize(path: Path, *, quantity: int = 10) -> None:
    connection = _connect(path)
    try:
        connection.executescript(
            """
            CREATE TABLE inventory(
                sku TEXT PRIMARY KEY,
                quantity INTEGER NOT NULL CHECK(quantity >= 0)
            );
            CREATE TABLE orders(
                order_id TEXT PRIMARY KEY,
                sku TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT NOT NULL,
                candidate_id TEXT NOT NULL
            );
            CREATE TABLE outbox(
                event_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE metadata(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        connection.execute("INSERT INTO inventory VALUES('widget', ?)", (quantity,))
        connection.executemany(
            "INSERT INTO metadata VALUES(?, ?)",
            (("state_version", "state-v1"), ("policy_version", "policy-v1")),
        )
    finally:
        connection.close()


def _database_projection(connection: sqlite3.Connection) -> dict[str, Any]:
    tables = ("inventory", "orders", "outbox", "metadata")
    return {
        table: [list(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1")]
        for table in tables
    }


def _projection(
    connection: sqlite3.Connection,
    persistent: dict[str, Any],
    emitted: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "database": _database_projection(connection),
        "persistent": dict(persistent),
        "emitted": [dict(item) for item in emitted],
    }


def _record(
    ledger: list[dict[str, Any]],
    event: str,
    candidate: str,
    accepted: bool,
    detail: str,
) -> None:
    ledger.append(
        {
            "sequence": len(ledger) + 1,
            "event": event,
            "candidate": candidate,
            "accepted": accepted,
            "detail": detail,
        }
    )


def _apply_order(connection: sqlite3.Connection, order_id: str, candidate_id: str, quantity: int) -> None:
    connection.execute(
        "INSERT INTO orders VALUES(?, 'widget', ?, 'trial', ?)",
        (order_id, quantity, candidate_id),
    )
    connection.execute(
        "UPDATE inventory SET quantity=quantity-? WHERE sku='widget'",
        (quantity,),
    )


def _accept_order(connection: sqlite3.Connection) -> None:
    _apply_order(connection, "accepted-order", "candidate-accepted", 2)
    connection.execute(
        "UPDATE orders SET status='accepted' WHERE order_id='accepted-order'"
    )
    connection.execute(
        "INSERT INTO outbox VALUES('accepted-event', 'accepted-order', "
        "'candidate-accepted', 'accepted-order-created')"
    )


def _run_reference(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    _initialize(path)
    connection = _connect(path)
    persistent = {"cache_reserved": 0, "authoritative_owner": "sqlite"}
    emitted: list[dict[str, str]] = []
    try:
        initial = _projection(connection, persistent, emitted)
        connection.execute("BEGIN IMMEDIATE")
        _accept_order(connection)
        connection.execute("COMMIT")
        emitted.append(
            {
                "event_id": "accepted-event",
                "candidate": "candidate-accepted",
                "commit": "accepted-commit",
            }
        )
        final = _projection(connection, persistent, emitted)
    finally:
        connection.close()
    return initial, final


def _rollback_rejected(
    connection: sqlite3.Connection,
    ledger: list[dict[str, Any]],
    persistent: dict[str, Any],
    *,
    restore_cache: bool,
) -> None:
    connection.execute("ROLLBACK TO rejected_trial")
    _record(ledger, "rollback_to", "candidate-rejected", False, "native_savepoint_rollback")
    connection.execute("RELEASE rejected_trial")
    _record(ledger, "release", "candidate-rejected", False, "savepoint_closed")
    if restore_cache:
        persistent["cache_reserved"] = 0
        _record(ledger, "restore", "candidate-rejected", False, "persistent_projection_restored")


def _run_followup(
    spec: dict[str, Any],
    path: Path,
    *,
    enforce: bool,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, bool], list[str]]:
    quantity = 11 if spec["fault"] == "INVALID_ENTRY" else 10
    _initialize(path, quantity=quantity)
    connection = _connect(path)
    persistent = {"cache_reserved": 0, "authoritative_owner": "sqlite"}
    emitted: list[dict[str, str]] = []
    ledger: list[dict[str, Any]] = []
    blocked: list[str] = []
    signals = {name: False for name in ("O1", "O2", "O3", "O4", "O5")}
    fault = spec["fault"]
    variant = spec["history_variant"]

    try:
        initial = _projection(connection, persistent, emitted)
        connection.execute("BEGIN IMMEDIATE")
        _record(ledger, "begin", "candidate-rejected", False, "outer_transaction")
        connection.execute("SAVEPOINT rejected_trial")
        _record(ledger, "evaluate", "candidate-rejected", False, "savepoint_trial")
        _apply_order(connection, "rejected-order", "candidate-rejected", 1)
        persistent["cache_reserved"] = 1

        if fault == "O2_PREMATURE_COMMIT":
            signals["O2"] = True
            if enforce:
                blocked.append("premature_commit")
                _record(ledger, "block", "candidate-rejected", False, "premature_commit")
                _rollback_rejected(connection, ledger, persistent, restore_cache=True)
            else:
                connection.execute("RELEASE rejected_trial")
                connection.execute("COMMIT")
                _record(ledger, "commit", "candidate-rejected", False, "premature_commit")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute("DELETE FROM orders WHERE order_id='rejected-order'")
                connection.execute("UPDATE inventory SET quantity=quantity+1 WHERE sku='widget'")
                connection.execute("COMMIT")
                persistent["cache_reserved"] = 0
                _record(ledger, "compensate", "candidate-rejected", False, "endpoint_restored_only")
                connection.execute("BEGIN IMMEDIATE")
        elif fault == "O3_ROLLBACK_OMITTED":
            signals["O3"] = True
            if enforce:
                blocked.append("rollback_omission")
                _record(ledger, "block", "candidate-rejected", False, "rollback_required")
                _rollback_rejected(connection, ledger, persistent, restore_cache=True)
            else:
                connection.execute("RELEASE rejected_trial")
                _record(ledger, "release", "candidate-rejected", False, "rollback_omitted")
        elif variant == "inner_release_outer_rollback":
            connection.execute("RELEASE rejected_trial")
            _record(ledger, "release", "candidate-rejected", False, "inner_release_not_durable")
            connection.execute("ROLLBACK")
            _record(ledger, "rollback", "candidate-rejected", False, "outer_transaction_rollback")
            persistent["cache_reserved"] = 0
            _record(ledger, "restore", "candidate-rejected", False, "persistent_projection_restored")
            connection.execute("BEGIN IMMEDIATE")
        else:
            if variant == "exception_rollback":
                _record(ledger, "exception", "candidate-rejected", False, "controlled_application_error")
            restore_cache = fault != "O3_INCOMPLETE_RESTORE" or enforce
            _rollback_rejected(connection, ledger, persistent, restore_cache=restore_cache)
            if fault == "O3_INCOMPLETE_RESTORE":
                signals["O3"] = True
                if enforce:
                    blocked.append("incomplete_restore")
                    _record(ledger, "block", "candidate-rejected", False, "restore_completed_by_guard")

        if fault == "O1_COMPETING_OWNER":
            signals["O1"] = True
            if enforce:
                blocked.append("competing_owner")
                _record(ledger, "block", "candidate-rejected", False, "owner_change_rejected")
            else:
                persistent["authoritative_owner"] = "application-shadow"
                _record(ledger, "owner_change", "candidate-rejected", False, "competing_owner")

        if fault == "O4_VERSION_MISMATCH":
            signals["O4"] = True
            if enforce:
                blocked.append("version_mismatch")
                _record(ledger, "block", "candidate-rejected", False, "policy_state_version_mismatch")
            else:
                connection.execute(
                    "UPDATE metadata SET value='policy-v2' WHERE key='policy_version'"
                )
                _record(ledger, "version_bind", "candidate-rejected", False, "policy-v2_with_state-v1")

        if fault == "O5_OUTPUT_ESCAPE":
            signals["O5"] = True
            if enforce:
                blocked.append("output_escape")
                _record(ledger, "block", "candidate-rejected", False, "uncommitted_output_dropped")
            else:
                emitted.append(
                    {
                        "event_id": "rejected-event",
                        "candidate": "candidate-rejected",
                        "commit": "none",
                    }
                )
                _record(ledger, "emit", "candidate-rejected", False, "uncommitted_output_escape")

        if not connection.in_transaction:
            connection.execute("BEGIN IMMEDIATE")
        _record(ledger, "evaluate", "candidate-accepted", True, "accepted_trial")
        _accept_order(connection)
        connection.execute("COMMIT")
        _record(ledger, "commit", "candidate-accepted", True, "accepted_commit")
        emitted.append(
            {
                "event_id": "accepted-event",
                "candidate": "candidate-accepted",
                "commit": "accepted-commit",
            }
        )
        _record(ledger, "emit", "candidate-accepted", True, "post_commit_output")
        final = _projection(connection, persistent, emitted)
    finally:
        connection.close()

    return initial, final, ledger, signals, blocked


def _observability(spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    available = list(REQUIRED_OBSERVATIONS)
    missing: list[str] = []
    if spec["fault"] == "MISSING_ROLLBACK_OBSERVATION":
        available.remove("event_ledger")
        missing.append("event_ledger")
    if spec["fault"] == "MISSING_OUTPUT_PROVENANCE":
        available.remove("output_provenance")
        missing.append("output_provenance")
    return available, missing


def execute_case(
    spec: dict[str, Any],
    *,
    run_id: str,
    mode: str,
    output_dir: Path,
) -> dict[str, Any]:
    if mode not in {"diagnostic", "enforce"}:
        raise ValueError(f"unsupported mode: {mode}")
    output_dir.mkdir(parents=True, exist_ok=False)
    reference_path = output_dir / "reference.db"
    followup_path = output_dir / "followup.db"
    initial_a, final_a = _run_reference(reference_path)
    initial_b, final_b, ledger, signals, blocked = _run_followup(
        spec, followup_path, enforce=mode == "enforce"
    )
    available, missing = _observability(spec)
    eligible = canonical_sha256(initial_a) == canonical_sha256(initial_b)
    verdict, reasons = adjudicate(
        capability_complete=not missing,
        eligible=eligible,
        signals=signals,
    )
    endpoint_equal = canonical_sha256(final_a) == canonical_sha256(final_b)
    output_equal = canonical_sha256(final_a["emitted"]) == canonical_sha256(final_b["emitted"])
    persistent_equal = canonical_sha256(final_a["persistent"]) == canonical_sha256(final_b["persistent"])
    database_equal = canonical_sha256(final_a["database"]) == canonical_sha256(final_b["database"])
    expected = spec["expected_verdict"]

    result: dict[str, Any] = {
        "schema_version": "M2026-003-R3-SQLITE-RESULT-1.0",
        "case_id": spec["case_id"],
        "label": spec["label"],
        "fault": spec["fault"],
        "mode": mode,
        "run_id": run_id,
        "sqlite_version": sqlite3.sqlite_version,
        "expected_verdict": expected,
        "observed_verdict": verdict.value,
        "verdict_match": verdict.value == expected,
        "eligible": eligible,
        "required_observations": list(REQUIRED_OBSERVATIONS),
        "available_observations": available,
        "missing_observations": missing,
        "signals": signals,
        "reasons": list(reasons),
        "database_equal": database_equal,
        "persistent_equal": persistent_equal,
        "output_equal": output_equal,
        "endpoint_equal": endpoint_equal,
        "blocked_actions": blocked,
        "blocked_count": len(blocked),
        "false_block": spec["fault"] == "NONE" and bool(blocked),
        "initial_reference_sha256": canonical_sha256(initial_a),
        "initial_followup_sha256": canonical_sha256(initial_b),
        "final_reference_sha256": canonical_sha256(final_a),
        "final_followup_sha256": canonical_sha256(final_b),
        "ledger_sha256": canonical_sha256(ledger),
        "database_file_sha256": file_sha256(followup_path),
    }
    result["containment_pass"] = (
        mode == "diagnostic"
        or (
            database_equal
            and persistent_equal
            and output_equal
            and (
                (spec["fault"] == "NONE" and not blocked)
                or (spec["fault"].startswith("O") and bool(blocked))
            )
        )
    )
    result["semantic_sha256"] = canonical_sha256(semantic_result(result))

    with (output_dir / "case_result.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with (output_dir / "event_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("sequence", "event", "candidate", "accepted", "detail")
        )
        writer.writeheader()
        writer.writerows(ledger)
    with (output_dir / "final_projection.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump({"reference": final_a, "followup": final_b}, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return result

