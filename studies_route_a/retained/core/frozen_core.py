"""Case-independent equality contracts over raw JSON observations.

This deliberately small interpreter does not generate tests, inspect versions,
or infer hidden-state completeness. It implements a declared observation layer.
"""

import math


class ContractError(ValueError):
    pass


class MissingObservation(KeyError):
    pass


def validate_json(value):
    if type(value) in (str, int, bool, type(None)):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            validate_json(item)
        return
    if type(value) is dict and all(type(k) is str for k in value):
        for item in value.values():
            validate_json(item)
        return
    raise ContractError("non-JSON or non-finite observed value")


def value_at(trace, path):
    if not isinstance(path, list) or not path or any(type(p) not in (str, int) for p in path):
        raise ContractError("path must be a nonempty string/integer list")
    current = trace
    for key in path:
        if type(current) is dict and type(key) is str and key in current:
            current = current[key]
        elif type(current) is list and type(key) is int and 0 <= key < len(current):
            current = current[key]
        else:
            raise MissingObservation(tuple(path))
    return current


def equal(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(equal(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(equal(a, b) for a, b in zip(left, right))
    return left == right


def operand(spec, trace):
    if type(spec) is not dict or len(spec) != 1:
        raise ContractError("operand must contain exactly path or literal")
    if "path" in spec:
        return value_at(trace, spec["path"])
    if "literal" in spec:
        validate_json(spec["literal"])
        return spec["literal"]
    raise ContractError("unknown operand")


def evaluate(trace, contract):
    """Return coverage, eligibility, and failed declared relations without mutation."""
    if set(trace) != {"context", "samples"}:
        raise ContractError("trace accepts only context and samples, not labels or revisions")
    validate_json(trace)
    if set(contract) != {"schema", "eligibility", "relations"} or contract["schema"] != "S06-EQUALITY-1":
        raise ContractError("unsupported contract schema")
    if not contract["relations"]:
        raise ContractError("at least one relation is required")
    resolved, missing = [], []
    identifiers = set()
    for group in ("eligibility", "relations"):
        for rule in contract[group]:
            required = {"id", "left", "right"} | ({"obligation"} if group == "relations" else set())
            if type(rule) is not dict or set(rule) != required or not isinstance(rule["id"], str):
                raise ContractError("invalid relation declaration")
            if rule["id"] in identifiers:
                raise ContractError("duplicate relation identifier")
            identifiers.add(rule["id"])
            if group == "relations" and rule["obligation"] not in {"O1", "O2", "O3", "O4", "O5", "O6"}:
                raise ContractError("unknown obligation")
            pair = []
            for side in ("left", "right"):
                try:
                    pair.append(operand(rule[side], trace))
                except MissingObservation:
                    missing.append(rule[side]["path"])
            if len(pair) == 2:
                resolved.append((group, rule, equal(*pair)))
    if missing:
        return {"verdict": "UNSUPPORTED", "missing": missing, "failed": []}
    invalid = [r["id"] for group, r, ok in resolved if group == "eligibility" and not ok]
    if invalid:
        return {"verdict": "INVALID", "invalid": invalid, "failed": []}
    failed = [{"id": r["id"], "obligation": r["obligation"]}
              for group, r, ok in resolved if group == "relations" and not ok]
    return {"verdict": "DETECTED" if failed else "INVARIANT", "failed": failed}
