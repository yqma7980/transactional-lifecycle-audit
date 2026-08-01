from __future__ import annotations

"""Gate-aware P5 history execution for formal strength sweeps.

This module preserves the frozen history and mutation schedule.  Its only
behavioral correction is to record a failed mechanics gate as a structured,
non-committed observation instead of calling the host commit routine, which is
contractually required to reject that candidate.
"""

import p5_fe_history as frozen


def run_p5_history_gateaware(
    family_id: str | None,
    faulty: bool,
    eta: float,
    run_id: str,
) -> frozen.P5HistoryRun:
    if faulty and family_id not in {"F01", "F02", "F05", "F07"}:
        raise ValueError("faulty P5 history requires a frozen family")
    if not faulty and eta != 0.0:
        raise ValueError("safe P5 history must use eta=0")

    committed = frozen.initial_committed_state()
    persistent = frozen.P5PersistentState()
    role = "faulty" if faulty else "safe"
    history_id = f"H_{family_id}_{role.upper()}" if family_id else "H_DIRECT_SAFE"
    host = frozen.P5TransactionalFEHost(
        committed,
        persistent,
        run_id=f"{run_id}-{role}",
    )
    output_rows: list[dict[str, object]] = []
    attempts: list[dict[str, object]] = []
    replay_packet = None
    mutation_record = None
    prerequisite_status = "PASS"

    for accepted_index in range(1, len(frozen.LOAD_PATH)):
        target_load = float(frozen.LOAD_PATH[accepted_index])
        source_load = float(host.committed.accepted_load)
        at_replay_boundary = (
            source_load == frozen.RETRY_SOURCE_LOAD
            and target_load == frozen.RETRY_REPLAY_TARGET
        )

        if family_id in {"F01", "F02", "F05"} and at_replay_boundary:
            attempt_id = f"{run_id}-{role}-FAILED-020"
            host.begin_attempt(
                frozen.RETRY_FAILED_TARGET,
                attempt_id,
                "EXACT_CURRENT",
                maximum_iterations=1,
            )
            failed = host.solve_attempt()
            attempts.append(frozen._attempt_summary(failed, forced=True))
            if failed.converged:
                prerequisite_status = "NOT_SUPPORTED_FORCED_RETRY_TRIGGER"
                break
            if faulty:
                mutation_record = frozen.inject_fault(
                    persistent,
                    family_id,
                    eta,
                    failed.selected_packet.candidate_id,
                )
                frozen._record_mutation(
                    host,
                    attempt_id,
                    mutation_record,
                    family_id == "F05",
                )
            host.restore_after_failed_attempt(failed)

        if family_id == "F07" and faulty and at_replay_boundary:
            attempt_id = f"{run_id}-{role}-EXTRA-CALLBACK"
            probe = frozen.evaluate_p5_material_field(
                host.context,
                host.committed.primary,
                host.committed,
                persistent,
                target_load,
                "EXACT_CURRENT",
            )
            host.events.append(
                "ExtraNonacceptingResidual",
                solve_id=host.run_id,
                attempt_id=attempt_id,
                candidate_id=probe.candidate_id,
                primary_vector_hash=probe.primary_hash,
                committed_state_hash=host.committed.full_hash,
                persistent_projection_hash=persistent.projection_hash,
                reachable_from_accepted_output=False,
            )
            mutation_record = frozen.inject_fault(
                persistent,
                family_id,
                eta,
                probe.candidate_id,
            )
            frozen._record_mutation(
                host,
                attempt_id,
                mutation_record,
                False,
            )

        attempt_id = f"{run_id}-{role}-A{accepted_index:02d}"
        host.begin_attempt(
            target_load,
            attempt_id,
            "EXACT_CURRENT",
            maximum_iterations=25,
        )
        attempt = host.solve_attempt()
        attempts.append(frozen._attempt_summary(attempt, forced=False))
        if at_replay_boundary:
            packets = tuple(host._packet_cache.values())
            if not packets:
                raise RuntimeError("P5 replay boundary has no material packet")
            replay_packet = packets[0]

        if not attempt.converged:
            prerequisite_status = "FAILED_NORMAL_ATTEMPT"
            break
        if not attempt.metrics.pass_flag:
            prerequisite_status = "FAILED_NORMAL_MECHANICS_GATE"
            break

        host.commit(attempt)
        host.events.append(
            "OutputAcceptedState",
            solve_id=host.run_id,
            attempt_id=attempt.attempt_id,
            candidate_id=attempt.selected_packet.candidate_id,
            committed_state_hash=host.committed.full_hash,
            accepted_version=host.committed.accepted_version,
            reachable_from_accepted_output=True,
        )
        output_rows.append(frozen._accepted_output_row(host, attempt))

    if replay_packet is None:
        raise RuntimeError(
            "P5 history ended before the frozen replay packet was available"
        )

    result = frozen.P5HistoryRun(
        history_id=history_id,
        role=role,
        family_id=family_id,
        eta=float(eta),
        final_state=host.committed,
        persistent=persistent,
        output_rows=output_rows,
        events=host.events.records,
        attempts=attempts,
        replay_packet=replay_packet,
        context=host.context,
        prerequisite_status=prerequisite_status,
        mutation_record=mutation_record,
    )
    host.close()
    return result
