"""Narrow real-method composition recipe; no service or constructor lifecycle claim."""
import sys
from types import SimpleNamespace
from unittest.mock import patch


def run(history, emit):
    from celery import bootsteps
    from celery.worker.consumer.consumer import Consumer
    from celery.worker.loops import synloop

    if history not in ("control", "trigger"):
        raise ValueError("Invalid history")
    c = object.__new__(Consumer)
    c.hub = None
    c._pending_operations = []
    c.pool = SimpleNamespace(is_green=False)
    receipts = []
    callback_entries = []
    callback_returns = []
    callback_errors = []
    shutdown_outcomes = []
    calls = {"native_perform": 0, "maybe_shutdown": 0, "drain": 0, "consume": 0, "ready": 0}
    timeouts = []

    def receipt(token):
        callback_entries.append(token)
        try:
            emit("CALLBACK_ENTER:" + token, {})
            receipts.append(token)
            callback_returns.append(token)
            emit("CALLBACK_RETURN:" + token, {})
        except Exception as exc:
            callback_errors.append({"token": token, "type_fqn": type(exc).__module__ + "." + type(exc).__qualname__,
                                    "message": str(exc)})
            raise

    def drain_events(timeout):
        calls["drain"] += 1
        timeouts.append(timeout)
        emit("DRAIN_EVENTS", {"timeout_seconds": timeout})
        c.connection = None

    def consume():
        calls["consume"] += 1
        emit("TASK_CONSUMER_CONSUME", {})

    def ready():
        calls["ready"] += 1
        emit("ON_READY", {})

    def create_handler():
        emit("TASK_HANDLER_CREATED", {})
        return lambda *args, **kwargs: None

    def maybe_shutdown():
        calls["maybe_shutdown"] += 1
        if history == "trigger":
            shutdown_outcomes.append("RAISE_SYSTEM_EXIT")
            emit("MAYBE_SHUTDOWN_RAISE", {"type_fqn": "builtins.SystemExit", "code": 0})
            raise SystemExit(0)
        shutdown_outcomes.append("RETURN_NONE")
        emit("MAYBE_SHUTDOWN_RETURN", {})

    c.connection = connection = SimpleNamespace(drain_events=drain_events)
    c.create_task_handler = create_handler
    c.on_ready = ready
    task_consumer = SimpleNamespace(consume=consume, on_message=None)
    blueprint = SimpleNamespace(state=bootsteps.RUN)
    qos = SimpleNamespace(prev=1, value=1)
    assert type(c) is Consumer
    assert c.perform_pending_operations.__self__ is c
    assert c.perform_pending_operations.__func__ is Consumer.perform_pending_operations
    assert c.call_soon.__func__ is Consumer.call_soon
    assert "perform_pending_operations" not in c.__dict__ and "call_soon" not in c.__dict__
    promises = []
    for token in ("op_a", "op_b"):
        promises.append((c.call_soon(receipt, token), token))
        emit("CALL_SOON:" + token, {})

    def pending_ids():
        return [next(token for promise, token in promises if item is promise)
                for item in c._pending_operations]

    initial_ids = pending_ids()
    assert initial_ids == ["op_a", "op_b"]
    emit("PENDING_SNAPSHOT:2", {"pending_ids": initial_ids})
    native_code = Consumer.perform_pending_operations.__code__

    def observe(frame, event, arg):
        if frame.f_code is native_code and frame.f_locals.get("self") is c:
            if event == "call":
                calls["native_perform"] += 1
                emit("NATIVE_PERFORM_ENTER", {})
            elif event == "return":
                emit("NATIVE_PERFORM_RETURN", {})

    prior_profiler = sys.getprofile()
    # A preexisting profiler must be resolved before this cell, not silently displaced.
    assert prior_profiler is None
    try:
        sys.setprofile(observe)
        with patch("celery.worker.loops.state.maybe_shutdown", maybe_shutdown):
            emit("SYNLOOP_ENTER", {})
            try:
                synloop(c, connection, task_consumer, blueprint, None, qos, 0, None, hbrate=2.0)
            except SystemExit as exc:
                native_exit, exit_code = "SYSTEM_EXIT", exc.code
                emit("SYNLOOP_SYSTEM_EXIT", {"code": exit_code})
            else:
                native_exit, exit_code = "RETURN_NONE", None
                emit("SYNLOOP_RETURN", {})
        final_ids = pending_ids()
        result = {"pending_before": len(initial_ids), "pending_after": len(final_ids),
                  "pending_ids_before": initial_ids, "pending_ids_after": final_ids,
                  "callback_receipts": receipts[:],
                  "callback_counts": {token: receipts.count(token) for token in ("op_a", "op_b")},
                  "callback_enter_return_balance": {
                      token: [callback_entries.count(token), callback_returns.count(token)]
                      for token in ("op_a", "op_b")},
                  "unexpected_callback_exceptions": callback_errors[:],
                  "native_perform_calls": calls["native_perform"],
                  "maybe_shutdown_calls": calls["maybe_shutdown"],
                  "maybe_shutdown_outcome": shutdown_outcomes[-1] if shutdown_outcomes else None,
                  "drain_events_calls": calls["drain"], "drain_timeout_seconds": timeouts[:],
                  "consume_calls": calls["consume"], "on_ready_calls": calls["ready"],
                  "native_exit": native_exit, "system_exit_code": exit_code}
        emit("TERMINAL_SNAPSHOT", result)
        return result
    finally:
        sys.setprofile(prior_profiler)
    # Intentionally no manual consumption, shutdown, list.clear(), or teardown flush.
