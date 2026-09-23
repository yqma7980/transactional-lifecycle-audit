"""Bounded, independently authored synthetic tests; no target evidence is read."""

import ast
import copy
import importlib.util
import itertools
import json
import os
from pathlib import Path
import sys
import time
import unittest


SOURCE = Path(__file__).resolve().with_name("rich_compare.py")
SPEC = importlib.util.spec_from_file_location("independent_rich_compare", SOURCE)
rich = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rich)

ATTRIBUTES = ("file_equal", "name", "url", "storage", "instance", "field")
FIELDS94 = ("pending_after", "pending_ids_after", "callback_receipts", "callback_counts", "callback_enter_return_balance")
IDS94 = ("pending_count_empty", "pending_ids_empty", "receipt_order", "callback_once", "callback_balanced")
ELIGIBILITY = ("protocol_id", "observation_point", "observation_order")
ELIGIBILITY_IDS = ("protocol_matches", "point_matches", "order_matches")
OBSERVATIONS = []
COVERAGE = {"r79_truth_patterns": 0, "r94_truth_patterns": 0, "r79_eligibility_patterns": 0, "r94_eligibility_patterns": 0}


def satisfied(case):
    if case == 79:
        return {
            "context": {
                "protocol_id": "G4-ASSOCIATION-RESTORE-1",
                "observation_point": "post_restore_property_window",
                "observation_order": list(ATTRIBUTES),
            },
            "samples": {"checks": {key: {"status": "VALUE", "equal": True} for key in ATTRIBUTES}},
        }
    return {
        "context": {
            "protocol_id": "G4-PENDING-CALLBACK-1",
            "observation_point": "immediate_native_exit_before_cleanup",
            "observation_order": list(FIELDS94),
        },
        "samples": {
            "pending_after": 0,
            "pending_ids_after": [],
            "callback_receipts": ["op_b", "op_a"],
            "callback_counts": {"op_a": 1, "op_b": 1},
            "callback_enter_return_balance": {"op_a": [1, 1], "op_b": [1, 1]},
        },
    }


def relations(case):
    if case == 79:
        return ["restored_" + key for key in ATTRIBUTES]
    return list(IDS94)


def paths(case):
    eligibility = ["context." + key for key in ELIGIBILITY]
    sample = ["samples.checks." + key for key in ATTRIBUTES] if case == 79 else ["samples." + key for key in FIELDS94]
    return eligibility + sample


def scored(case, failed_ids=()):
    return {
        "verdict": "DETECTED" if failed_ids else "INVARIANT",
        "failed": [{"id": key, "obligation": "O3" if case == 79 else "O5"} for key in failed_ids],
    }


def set_relation(trace, case, index, value):
    if case == 79:
        trace["samples"]["checks"][ATTRIBUTES[index]] = value
    else:
        trace["samples"][FIELDS94[index]] = value


def direct(case):
    return rich.evaluate79 if case == 79 else rich.evaluate94


class IntChild(int):
    pass


class FloatChild(float):
    pass


class StrChild(str):
    pass


class ListChild(list):
    pass


class DictChild(dict):
    pass


TYPE_EQUALITY_CALLS = []


class SpoofingType(type):
    def __eq__(cls, other):
        TYPE_EQUALITY_CALLS.append(cls.__name__)
        return True

    __hash__ = type.__hash__


class SpoofedValue(metaclass=SpoofingType):
    pass


class SpoofedInt(int, metaclass=SpoofingType):
    pass


class ExplodingType(type):
    def __eq__(cls, other):
        TYPE_EQUALITY_CALLS.append(cls.__name__)
        raise RuntimeError("A transport validator must not call this hook")

    __hash__ = type.__hash__


class ExplodingValue(metaclass=ExplodingType):
    pass


class RichComparatorTests(unittest.TestCase):
    def check(self, case, trace, expected):
        raw = direct(case)(trace)
        normalized = rich.normalized_evaluate(case, trace)
        self.assertEqual(raw, expected)
        self.assertEqual(normalized, expected)
        OBSERVATIONS.append({"test": self.id(), "case": case, "direct": copy.deepcopy(raw), "normalized": copy.deepcopy(normalized)})

    def error(self, case, trace):
        with self.assertRaises(rich.TraceInputError):
            direct(case)(trace)
        actual = rich.normalized_evaluate(case, trace)
        self.assertEqual(actual, {"verdict": "ERROR", "failed": []})
        self.assertEqual(set(actual), {"verdict", "failed"})
        OBSERVATIONS.append({"test": self.id(), "case": case, "raw_rejected": True, "normalized": actual})

    def equal(self, left, right, expected):
        actual = rich.typed_json_equal(left, right)
        reverse = rich.typed_json_equal(right, left)
        self.assertIs(actual, expected)
        self.assertIs(reverse, expected)
        OBSERVATIONS.append({"test": self.id(), "equality": actual, "reverse_equality": reverse})

    def test_satisfied_direct_and_normalized(self):
        for case in (79, 94):
            with self.subTest(case=case):
                self.check(case, satisfied(case), scored(case))

    def test_all_r79_eligible_truth_patterns(self):
        for bits in itertools.product((False, True), repeat=6):
            with self.subTest(bits=bits):
                trace = satisfied(79)
                failed = []
                for index, bit in enumerate(bits):
                    set_relation(trace, 79, index, {"status": "VALUE", "equal": bit})
                    if not bit:
                        failed.append("restored_" + ATTRIBUTES[index])
                self.check(79, trace, scored(79, failed))
                COVERAGE["r79_truth_patterns"] += 1

    def test_all_r94_eligible_truth_patterns(self):
        violations = (1, ["op_a"], ["op_a", "op_b"], {"op_a": 2, "op_b": 1}, {"op_a": [1, 0], "op_b": [1, 1]})
        for bits in itertools.product((False, True), repeat=5):
            with self.subTest(bits=bits):
                trace = satisfied(94)
                failed = []
                for index, bit in enumerate(bits):
                    if not bit:
                        set_relation(trace, 94, index, copy.deepcopy(violations[index]))
                        failed.append(IDS94[index])
                self.check(94, trace, scored(94, failed))
                COVERAGE["r94_truth_patterns"] += 1

    def test_all_eligibility_patterns_and_invalid_priority(self):
        for case in (79, 94):
            for bits in itertools.product((False, True), repeat=3):
                with self.subTest(case=case, bits=bits):
                    trace = satisfied(case)
                    for index in range(len(relations(case))):
                        set_relation(trace, case, index, None)
                    invalid = []
                    for key, identity, bit in zip(ELIGIBILITY, ELIGIBILITY_IDS, bits):
                        if not bit:
                            trace["context"][key] = None
                            invalid.append(identity)
                    expected = {"verdict": "INVALID", "invalid": invalid, "failed": []} if invalid else scored(case, relations(case))
                    self.check(case, trace, expected)
                    COVERAGE[f"r{case}_eligibility_patterns"] += 1

    def test_each_missing_operand(self):
        for case in (79, 94):
            for path in paths(case):
                with self.subTest(case=case, path=path):
                    trace = satisfied(case)
                    node = trace
                    components = path.split(".")
                    for component in components[:-1]:
                        node = node[component]
                    del node[components[-1]]
                    self.check(case, trace, {"verdict": "UNSUPPORTED", "missing": [path], "failed": []})

    def test_all_missing_paths_are_ordered(self):
        for case in (79, 94):
            for trace in ({"samples": {}, "context": {}}, {"samples": None, "context": None}):
                with self.subTest(case=case, trace=trace):
                    self.check(case, trace, {"verdict": "UNSUPPORTED", "missing": paths(case), "failed": []})

    def test_missing_outranks_invalid_and_failed(self):
        for case in (79, 94):
            trace = satisfied(case)
            trace["context"]["protocol_id"] = "ineligible"
            del trace["context"]["observation_point"]
            del trace["context"]["observation_order"]
            set_relation(trace, case, 0, None)
            last = paths(case)[-1]
            container = trace["samples"]["checks"] if case == 79 else trace["samples"]
            del container[last.split(".")[-1]]
            self.check(case, trace, {"verdict": "UNSUPPORTED", "missing": ["context.observation_point", "context.observation_order", last], "failed": []})

    def test_arbitrary_json_context_is_missing_not_error(self):
        for case in (79, 94):
            for value in (None, False, 0, 0.0, "context", [], ["protocol_id"]):
                with self.subTest(case=case, value=value):
                    trace = satisfied(case)
                    trace["context"] = value
                    self.check(case, trace, {"verdict": "UNSUPPORTED", "missing": paths(case)[:3], "failed": []})

    def test_arbitrary_json_samples_is_missing_not_error(self):
        for case in (79, 94):
            for value in (None, True, 1, 1.5, "samples", [], [None]):
                with self.subTest(case=case, value=value):
                    trace = satisfied(case)
                    trace["samples"] = value
                    self.check(case, trace, {"verdict": "UNSUPPORTED", "missing": paths(case)[3:], "failed": []})
        for value in (None, [], True, 1, {}, "checks"):
            trace = satisfied(79)
            trace["samples"]["checks"] = value
            self.check(79, trace, {"verdict": "UNSUPPORTED", "missing": paths(79)[3:], "failed": []})

    def test_present_null_eligibility_is_invalid(self):
        for case in (79, 94):
            for key, identity in zip(ELIGIBILITY, ELIGIBILITY_IDS):
                trace = satisfied(case)
                trace["context"][key] = None
                self.check(case, trace, {"verdict": "INVALID", "invalid": [identity], "failed": []})

    def test_present_null_relation_is_detected(self):
        for case in (79, 94):
            for index, identity in enumerate(relations(case)):
                trace = satisfied(case)
                set_relation(trace, case, index, None)
                self.check(case, trace, scored(case, [identity]))

    def test_r79_partial_and_nested_null_operands_are_values(self):
        values = ({}, {"status": "VALUE"}, {"equal": True}, {"status": None, "equal": True}, {"status": "VALUE", "equal": None}, {"status": "VALUE", "equal": {"nested": None}})
        for value in values:
            trace = satisfied(79)
            trace["samples"]["checks"]["name"] = value
            self.check(79, trace, scored(79, ["restored_name"]))

    def test_r79_attribute_error_is_present_violation(self):
        trace = satisfied(79)
        trace["samples"]["checks"]["storage"] = {"status": "ATTRIBUTE_ERROR", "equal": None}
        self.check(79, trace, scored(79, ["restored_storage"]))

    def test_r94_partial_and_nested_null_operands_are_values(self):
        replacements = (
            (1, [None]), (2, ["op_b", None]),
            (3, {}), (3, {"op_a": 1}), (3, {"op_a": 1, "op_b": None}),
            (4, {}), (4, {"op_a": [1, 1]}),
            (4, {"op_a": [1, None], "op_b": [1, 1]}),
        )
        for index, value in replacements:
            trace = satisfied(94)
            set_relation(trace, 94, index, value)
            self.check(94, trace, scored(94, [IDS94[index]]))

    def test_boolean_integer_float_distinction_in_properties(self):
        for value in (1, 1.0, "true", False):
            trace = satisfied(79)
            trace["samples"]["checks"]["file_equal"]["equal"] = value
            self.check(79, trace, scored(79, ["restored_file_equal"]))
        replacements = (
            (0, False), (0, 0.0), (0, "0"),
            (3, {"op_a": True, "op_b": 1}), (3, {"op_a": 1.0, "op_b": 1}),
            (4, {"op_a": [True, 1], "op_b": [1, 1]}),
            (4, {"op_a": [1, 1], "op_b": [1, 1.0]}),
        )
        for index, value in replacements:
            trace = satisfied(94)
            set_relation(trace, 94, index, value)
            self.check(94, trace, scored(94, [IDS94[index]]))

    def test_exact_eligibility_literals_and_list_order(self):
        for case in (79, 94):
            for key, identity in zip(ELIGIBILITY, ELIGIBILITY_IDS):
                trace = satisfied(case)
                expected = trace["context"][key]
                trace["context"][key] = list(reversed(expected)) if type(expected) is list else expected + " "
                self.check(case, trace, {"verdict": "INVALID", "invalid": [identity], "failed": []})
            trace = satisfied(case)
            trace["context"]["observation_order"].append("extra")
            self.check(case, trace, {"verdict": "INVALID", "invalid": ["order_matches"], "failed": []})

    def test_r94_receipt_order_and_duplicates(self):
        for value in (["op_a", "op_b"], ["op_b", "op_a", "op_a"], ["op_b"], []):
            trace = satisfied(94)
            trace["samples"]["callback_receipts"] = value
            self.check(94, trace, scored(94, ["receipt_order"]))

    def test_key_order_is_irrelevant(self):
        for case in (79, 94):
            trace = satisfied(case)
            trace["context"] = dict(reversed(list(trace["context"].items())))
            trace["samples"] = dict(reversed(list(trace["samples"].items())))
            if case == 79:
                trace["samples"]["checks"] = {key: {"equal": True, "status": "VALUE"} for key in reversed(ATTRIBUTES)}
            else:
                trace["samples"]["callback_counts"] = {"op_b": 1, "op_a": 1}
                trace["samples"]["callback_enter_return_balance"] = {"op_b": [1, 1], "op_a": [1, 1]}
            self.check(case, dict(reversed(list(trace.items()))), scored(case))

    def test_extra_legal_keys_are_ignored_outside_fixed_operands(self):
        for case in (79, 94):
            trace = satisfied(case)
            trace["context"]["synthetic_ignored"] = {"nested": [None, False, 1, 1.25]}
            trace["samples"]["synthetic_ignored"] = [None, {"unused": True}]
            if case == 79:
                trace["samples"]["checks"]["synthetic_extra"] = {"status": "ATTRIBUTE_ERROR", "equal": None}
            self.check(case, trace, scored(case))

    def test_extra_internal_keys_break_exact_object_equality(self):
        trace = satisfied(79)
        trace["samples"]["checks"]["field"]["extra"] = None
        self.check(79, trace, scored(79, ["restored_field"]))
        for key, identity in (("callback_counts", "callback_once"), ("callback_enter_return_balance", "callback_balanced")):
            trace = satisfied(94)
            trace["samples"][key]["extra"] = None
            self.check(94, trace, scored(94, [identity]))

    def test_deep_typed_equality(self):
        pairs = (
            (None, None, True), (False, 0, False), (True, 1, False), (1, 1.0, False),
            (0.0, -0.0, True), (0, -0.0, False), (10 ** 100, 10 ** 100, True),
            ({"b": [None, {"x": True}], "a": 1}, {"a": 1, "b": [None, {"x": True}]}, True),
            ({"x": None}, {}, False), ({"x": [None]}, {"x": []}, False),
            ({"x": [1, None]}, {"x": [True, None]}, False),
            ({"x": {"a": None}}, {"x": {}}, False),
            (["op_b", "op_a"], ["op_a", "op_b"], False),
            ([], {}, False), ("1", 1, False),
            ("\u00e9", "e\u0301", False),
        )
        for left, right, expected in pairs:
            self.equal(left, right, expected)

    def test_deep_acyclic_json_does_not_need_recursion(self):
        left = None
        right = None
        wrong = False
        for _ in range(1500):
            left = [left]
            right = [right]
            wrong = [wrong]
        self.equal(left, right, True)
        self.equal(left, wrong, False)
        for case in (79, 94):
            trace = satisfied(case)
            trace["samples"]["synthetic_deep"] = left
            self.check(case, trace, scored(case))

    def test_invalid_envelopes(self):
        malformed = (None, False, 79, 0.5, "trace", [], (), {}, {"context": {}}, {"samples": {}}, {"context": {}, "samples": {}, "extra": None}, {"context": {}, "sample": {}})
        for case in (79, 94):
            for trace in malformed:
                with self.subTest(case=case, trace=trace):
                    self.error(case, trace)

    def test_unsupported_values_and_container_subclasses(self):
        values = (object(), (1,), {1}, frozenset({1}), b"x", bytearray(b"x"), 1 + 2j, range(1), IntChild(1), FloatChild(1.0), StrChild("x"), ListChild([]), DictChild({}))
        for case in (79, 94):
            for value in values:
                with self.subTest(case=case, type_name=type(value).__name__):
                    trace = satisfied(case)
                    trace["samples"]["ignored_but_illegal"] = value
                    self.error(case, trace)
            self.error(case, DictChild(satisfied(case)))

    def test_nonstring_and_subclass_object_keys(self):
        for case in (79, 94):
            for key in (0, True, None, (1,), StrChild("x")):
                trace = satisfied(case)
                trace["context"]["ignored_but_illegal"] = {key: None}
                self.error(case, trace)

    def test_nonfinite_values_every_transport_region(self):
        for case in (79, 94):
            for value in (float("nan"), float("inf"), float("-inf")):
                for location in ("context", "samples", "relation"):
                    with self.subTest(case=case, location=location, value=str(value)):
                        trace = satisfied(case)
                        if location == "relation":
                            set_relation(trace, case, 0, {"deep": [None, value]})
                        else:
                            trace[location]["ignored_but_illegal"] = {"deep": [value]}
                        self.error(case, trace)

    def test_json_decoded_nonfinite_and_overflow(self):
        for token in ("NaN", "Infinity", "-Infinity", "1e999"):
            trace = json.loads('{"context": {}, "samples": {"illegal": ' + token + '}}')
            for case in (79, 94):
                self.error(case, trace)

    def test_transport_error_outranks_missing_and_invalid(self):
        for case in (79, 94):
            self.error(case, {"context": {}, "samples": {"x": float("nan")}})
            trace = satisfied(case)
            trace["context"]["protocol_id"] = "wrong"
            trace["samples"]["ignored_but_illegal"] = object()
            self.error(case, trace)

    def test_cycles_are_errors_but_aliases_are_legal(self):
        cyclic_list = []
        cyclic_list.append(cyclic_list)
        cyclic_dict = {}
        cyclic_dict["self"] = cyclic_dict
        mixed = {"child": []}
        mixed["child"].append(mixed)
        for case in (79, 94):
            for value in (cyclic_list, cyclic_dict, mixed):
                trace = satisfied(case)
                trace["samples"]["cycle"] = value
                self.error(case, trace)
            trace = satisfied(case)
            shared = {"nested": [None, True]}
            trace["context"]["alias"] = shared
            trace["samples"]["alias"] = shared
            self.check(case, trace, scored(case))
            self.assertIs(trace["context"]["alias"], trace["samples"]["alias"])

    def test_equality_rejects_malformed_both_sides(self):
        cyclic = []
        cyclic.append(cyclic)
        for value in (float("nan"), float("inf"), {1: None}, (None,), object(), cyclic):
            for left, right in ((value, None), (None, value)):
                with self.assertRaises(rich.TraceInputError):
                    rich.typed_json_equal(left, right)

    def test_normalized_case_domain_is_exact(self):
        for case in (None, True, False, 79.0, 94.0, "79", "94", 0, 80, [], {}, IntChild(79)):
            actual = rich.normalized_evaluate(case, satisfied(79))
            self.assertEqual(actual, {"verdict": "ERROR", "failed": []})
            OBSERVATIONS.append({"test": self.id(), "case_type": type(case).__name__, "normalized": actual})

    def test_no_mutation_for_all_normalized_verdicts(self):
        for case in (79, 94):
            variants = [satisfied(case)]
            detected = satisfied(case)
            set_relation(detected, case, 0, None)
            variants.append(detected)
            invalid = satisfied(case)
            invalid["context"]["protocol_id"] = None
            variants.append(invalid)
            variants.append({"context": {}, "samples": {}})
            for trace in variants:
                before = copy.deepcopy(trace)
                raw = direct(case)(trace)
                self.assertEqual(trace, before)
                normalized = rich.normalized_evaluate(case, trace)
                self.assertEqual(trace, before)
                self.assertEqual(normalized, raw)
                OBSERVATIONS.append({"test": self.id(), "case": case, "unchanged": True, "normalized": normalized})
            malformed = {"context": {}, "samples": {"illegal": (None, 1)}}
            before = copy.deepcopy(malformed)
            self.error(case, malformed)
            self.assertEqual(malformed, before)

    def test_no_mutation_for_equality_and_cyclic_error(self):
        left = {"a": [None, {"b": True}], "c": 1}
        right = {"c": 1, "a": [None, {"b": True}]}
        before_left, before_right = copy.deepcopy(left), copy.deepcopy(right)
        self.equal(left, right, True)
        self.assertEqual(left, before_left)
        self.assertEqual(right, before_right)
        cycle = []
        cycle.append(cycle)
        for case in (79, 94):
            trace = satisfied(case)
            trace["samples"]["cycle"] = cycle
            self.error(case, trace)
            self.assertEqual(len(cycle), 1)
            self.assertIs(cycle[0], cycle)
            self.assertIs(trace["samples"]["cycle"], cycle)

    def test_return_values_do_not_leak_mutable_state(self):
        for case in (79, 94):
            trace = satisfied(case)
            first = rich.normalized_evaluate(case, trace)
            first["failed"].append({"id": "tampered"})
            self.check(case, trace, scored(case))
            set_relation(trace, case, 0, None)
            failed = rich.normalized_evaluate(case, trace)
            failed["failed"][0]["id"] = "tampered"
            self.check(case, trace, scored(case, relations(case)[:1]))
            trace["context"]["protocol_id"] = None
            invalid = rich.normalized_evaluate(case, trace)
            invalid["invalid"].clear()
            self.check(case, trace, {"verdict": "INVALID", "invalid": ["protocol_matches"], "failed": []})
            missing = rich.normalized_evaluate(case, {"context": {}, "samples": {}})
            missing["missing"].reverse()
            self.check(case, {"context": {}, "samples": {}}, {"verdict": "UNSUPPORTED", "missing": paths(case), "failed": []})
            error = rich.normalized_evaluate(case, None)
            error["failed"].append("tampered")
            self.error(case, None)

    def test_hostile_metaclass_values_are_not_json(self):
        for case in (79, 94):
            for value in (SpoofedValue(), SpoofedInt(1), ExplodingValue()):
                for location in ("context", "samples", "relation"):
                    with self.subTest(case=case, type_name=type(value).__name__, location=location):
                        trace = satisfied(case)
                        if location == "relation":
                            set_relation(trace, case, 0, value)
                        else:
                            trace[location]["ignored_but_illegal"] = {"nested": [value]}
                        self.error(case, trace)
                self.error(case, value)

    def test_type_equality_hooks_are_never_called(self):
        TYPE_EQUALITY_CALLS.clear()
        for value in (SpoofedValue(), SpoofedInt(1), ExplodingValue()):
            with self.assertRaises(rich.TraceInputError):
                rich.typed_json_equal(value, None)
            with self.assertRaises(rich.TraceInputError):
                rich.typed_json_equal(None, value)
            for case in (79, 94):
                trace = satisfied(case)
                trace["samples"]["ignored_but_illegal"] = value
                self.error(case, trace)
        self.assertEqual(TYPE_EQUALITY_CALLS, [])

    def test_spoofed_case_is_exact_error(self):
        for case in (SpoofedInt(79), SpoofedInt(94)):
            actual = rich.normalized_evaluate(case, satisfied(int(case)))
            self.assertEqual(actual, {"verdict": "ERROR", "failed": []})
            OBSERVATIONS.append({"test": self.id(), "case_type": "SpoofedInt", "normalized": actual})

    def test_comparator_import_surface_and_no_optimization_asserts(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertEqual(len(imports), 1)
        self.assertIsInstance(imports[0], ast.Import)
        self.assertEqual([name.name for name in imports[0].names], ["math"])
        self.assertFalse(any(isinstance(node, ast.Assert) for node in ast.walk(tree)))


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.executed_ids = []
        self.subtests_executed = 0

    def startTest(self, test):
        self.executed_ids.append(test.id())
        super().startTest(test)

    def addSubTest(self, test, subtest, err):
        self.subtests_executed += 1
        super().addSubTest(test, subtest, err)


if __name__ == "__main__":
    started_cpu = time.process_time()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RichComparatorTests)
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    report = {
        "schema": "independent-rich-synthetic-v1",
        "python_version": list(sys.version_info[:3]),
        "python_executable": sys.executable,
        "optimization": sys.flags.optimize,
        "isolated": sys.flags.isolated,
        "dont_write_bytecode": sys.dont_write_bytecode,
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "cpu_seconds": time.process_time() - started_cpu,
        "tests_run": result.testsRun,
        "subtests_executed": result.subtests_executed,
        "test_ids": result.executed_ids,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "ok": result.wasSuccessful(),
        "coverage": COVERAGE,
        "behavior_checks": len(OBSERVATIONS),
        "behavior": OBSERVATIONS,
    }
    print("SYNTHETIC_REPORT_JSON=" + json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False))
    sys.exit(0 if result.wasSuccessful() else 1)
