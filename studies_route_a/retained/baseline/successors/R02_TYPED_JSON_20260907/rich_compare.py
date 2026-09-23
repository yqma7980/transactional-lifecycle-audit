"""Independent, fixed rich assertions derived only from COMPARISON_SEMANTICS.md.

The direct evaluators reject malformed transport with TraceInputError. The
normalized wrapper maps exceptions to exactly {"verdict": "ERROR", "failed": []}.
No target, generic rule interpreter, wrapper, generated contract, or result is
imported or consulted. All traversal and equality operations are non-mutating.
"""

import math


class TraceInputError(ValueError):
    """The input is outside the finite, typed JSON transport domain."""


_MISSING = object()


def _validate_json(value):
    """Validate iteratively; aliases are legal, but ancestor cycles are not."""
    active = set()
    stack = [(value, False)]
    while stack:
        item, leaving = stack.pop()
        if leaving:
            active.remove(id(item))
            continue
        kind = type(item)
        if item is None or kind is bool or kind is int or kind is str:
            continue
        if kind is float:
            if not math.isfinite(item):
                raise TraceInputError("Nonfinite number")
            continue
        if kind is not list and kind is not dict:
            raise TraceInputError("Unsupported JSON value type")
        if id(item) in active:
            raise TraceInputError("Cyclic JSON container")
        active.add(id(item))
        stack.append((item, True))
        if kind is dict:
            for key in item:
                if type(key) is not str:
                    raise TraceInputError("JSON object keys must be plain strings")
            stack.extend((child, False) for child in item.values())
        else:
            stack.extend((child, False) for child in item)


def _typed_equal(left, right):
    """Compare already-validated values without Python's bool/int coercion."""
    stack = [(left, right)]
    while stack:
        a, b = stack.pop()
        kind = type(a)
        if kind is not type(b):
            return False
        if kind is dict:
            if a.keys() != b.keys():
                return False
            stack.extend((a[key], b[key]) for key in a)
        elif kind is list:
            if len(a) != len(b):
                return False
            stack.extend(zip(a, b))
        elif a != b:
            return False
    return True


def typed_json_equal(left, right):
    """Typed deep equality; malformed operands raise TraceInputError.

    Integer, float and boolean are separate types. Lists are ordered, object
    key order is irrelevant, and present null is different from an absent key.
    """
    _validate_json(left)
    _validate_json(right)
    return _typed_equal(left, right)


def _validate_trace(trace):
    _validate_json(trace)
    if type(trace) is not dict or trace.keys() != {"context", "samples"}:
        raise TraceInputError("Trace must have exactly context and samples")


def _resolve(trace, path, missing):
    node = trace
    for key in path:
        if type(node) is not dict or key not in node:
            missing.append(".".join(path))
            return _MISSING
        node = node[key]
    return node


def evaluate79(trace):
    """Evaluate the six fixed r79 restoration properties on finite typed JSON."""
    _validate_trace(trace)
    missing = []
    protocol = _resolve(trace, ("context", "protocol_id"), missing)
    point = _resolve(trace, ("context", "observation_point"), missing)
    order = _resolve(trace, ("context", "observation_order"), missing)
    file_equal = _resolve(trace, ("samples", "checks", "file_equal"), missing)
    name = _resolve(trace, ("samples", "checks", "name"), missing)
    url = _resolve(trace, ("samples", "checks", "url"), missing)
    storage = _resolve(trace, ("samples", "checks", "storage"), missing)
    instance = _resolve(trace, ("samples", "checks", "instance"), missing)
    field = _resolve(trace, ("samples", "checks", "field"), missing)

    # All paths are resolved before either eligibility or property scoring.
    if missing:
        return {"verdict": "UNSUPPORTED", "missing": missing, "failed": []}
    invalid = []
    if not _typed_equal(protocol, "G4-ASSOCIATION-RESTORE-1"):
        invalid.append("protocol_matches")
    if not _typed_equal(point, "post_restore_property_window"):
        invalid.append("point_matches")
    if not _typed_equal(order, ["file_equal", "name", "url", "storage", "instance", "field"]):
        invalid.append("order_matches")
    if invalid:
        return {"verdict": "INVALID", "invalid": invalid, "failed": []}

    failed = []
    if not _typed_equal(file_equal, {"status": "VALUE", "equal": True}):
        failed.append({"id": "restored_file_equal", "obligation": "O3"})
    if not _typed_equal(name, {"status": "VALUE", "equal": True}):
        failed.append({"id": "restored_name", "obligation": "O3"})
    if not _typed_equal(url, {"status": "VALUE", "equal": True}):
        failed.append({"id": "restored_url", "obligation": "O3"})
    if not _typed_equal(storage, {"status": "VALUE", "equal": True}):
        failed.append({"id": "restored_storage", "obligation": "O3"})
    if not _typed_equal(instance, {"status": "VALUE", "equal": True}):
        failed.append({"id": "restored_instance", "obligation": "O3"})
    if not _typed_equal(field, {"status": "VALUE", "equal": True}):
        failed.append({"id": "restored_field", "obligation": "O3"})
    return {"verdict": "DETECTED" if failed else "INVARIANT", "failed": failed}


def evaluate94(trace):
    """Evaluate the five fixed r94 pending-callback completion properties."""
    _validate_trace(trace)
    missing = []
    protocol = _resolve(trace, ("context", "protocol_id"), missing)
    point = _resolve(trace, ("context", "observation_point"), missing)
    order = _resolve(trace, ("context", "observation_order"), missing)
    pending = _resolve(trace, ("samples", "pending_after"), missing)
    pending_ids = _resolve(trace, ("samples", "pending_ids_after"), missing)
    receipts = _resolve(trace, ("samples", "callback_receipts"), missing)
    counts = _resolve(trace, ("samples", "callback_counts"), missing)
    balance = _resolve(trace, ("samples", "callback_enter_return_balance"), missing)
    if missing:
        return {"verdict": "UNSUPPORTED", "missing": missing, "failed": []}
    invalid = []
    if not _typed_equal(protocol, "G4-PENDING-CALLBACK-1"):
        invalid.append("protocol_matches")
    if not _typed_equal(point, "immediate_native_exit_before_cleanup"):
        invalid.append("point_matches")
    if not _typed_equal(order, ["pending_after", "pending_ids_after", "callback_receipts", "callback_counts", "callback_enter_return_balance"]):
        invalid.append("order_matches")
    if invalid:
        return {"verdict": "INVALID", "invalid": invalid, "failed": []}

    failed = []
    if not _typed_equal(pending, 0):
        failed.append({"id": "pending_count_empty", "obligation": "O5"})
    if not _typed_equal(pending_ids, []):
        failed.append({"id": "pending_ids_empty", "obligation": "O5"})
    if not _typed_equal(receipts, ["op_b", "op_a"]):
        failed.append({"id": "receipt_order", "obligation": "O5"})
    if not _typed_equal(counts, {"op_a": 1, "op_b": 1}):
        failed.append({"id": "callback_once", "obligation": "O5"})
    if not _typed_equal(balance, {"op_a": [1, 1], "op_b": [1, 1]}):
        failed.append({"id": "callback_balanced", "obligation": "O5"})
    return {"verdict": "DETECTED" if failed else "INVARIANT", "failed": failed}


def normalized_evaluate(case, trace):
    """Transport boundary; only the plain integer case IDs 79 and 94 are valid."""
    try:
        if type(case) is not int:
            raise TraceInputError("Case must be integer 79 or 94")
        if case == 79:
            return evaluate79(trace)
        if case == 94:
            return evaluate94(trace)
        raise TraceInputError("Unknown case")
    except Exception:
        return {"verdict": "ERROR", "failed": []}
