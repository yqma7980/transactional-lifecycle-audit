"""Synthetic collector/identity tests only. Never import target or frozen recipe."""
import argparse
import copy
import hashlib
import importlib.abc
import io
import json
import os
import platform
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCOPE = HERE.parent
ROOT = HERE.parents[2]
OLD = ROOT.parent / 'M-2026-003_S10_BATCH02_G2G3_20260906_220323'
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
ATTEMPTED_IMPORTS = []


class NoTarget(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('celery', 'django', 'kombu', 'amqp', 'vine', 'billiard',
                                     'm003_s10_celery5500_fixture'):
            ATTEMPTED_IMPORTS.append(fullname)
            raise RuntimeError('Synthetic test attempted target import: ' + fullname)


sys.meta_path.insert(0, NoTarget())
from driver import Recorder, capture
from evaluator import evaluate, evaluate_failure, qualify_four_cells, require_process_identity
from identity import AdmissionFailure, IdentityFailure, sha256, validate_spec
from observations import CollectionFailure, FQN, MESSAGE, loads
from spec_builder import build_rank94

PROTOCOL_PATH = OLD / 'governance/frozen_protocols/r094/CASE_PILOT_PROTOCOL.json'
RECIPE_PATH = PROTOCOL_PATH.parent / 'runnable_core_recipe.py'
PROTOCOL = loads(PROTOCOL_PATH.read_text(encoding='utf-8'))
SOURCE_BASE = ROOT / 'sources/r094/git_transport/acquisition_001'


def rows(body):
    return [dict(seq=i + 1, monotonic_ns=7, event=name, fields=copy.deepcopy(fields))
            for i, (name, fields) in enumerate([('begin', {})] + body + [('end', {})])]


def trace94(kind='control', extra_empty=False):
    key = {'control': 'expected_before_control', 'stranded': 'expected_before_trigger',
           'flushed_exit': 'expected_after_trigger'}[kind]
    state = {k: copy.deepcopy(v) for k, v in PROTOCOL[key].items()
             if k not in ('execution_status', 'native_outcome', 'violation')}
    body = [('CALL_SOON:op_a', {}), ('CALL_SOON:op_b', {}),
            ('PENDING_SNAPSHOT:2', {'pending_ids': ['op_a', 'op_b']}),
            ('SYNLOOP_ENTER', {}), ('TASK_HANDLER_CREATED', {}),
            ('TASK_CONSUMER_CONSUME', {}), ('ON_READY', {})]
    body += [('MAYBE_SHUTDOWN_RETURN', {})] if kind == 'control' else [
        ('MAYBE_SHUTDOWN_RAISE', {'type_fqn': 'builtins.SystemExit', 'code': 0})]
    if kind != 'stranded':
        body += [('NATIVE_PERFORM_ENTER', {}), ('CALLBACK_ENTER:op_b', {}), ('CALLBACK_RETURN:op_b', {}),
                 ('CALLBACK_ENTER:op_a', {}), ('CALLBACK_RETURN:op_a', {}), ('NATIVE_PERFORM_RETURN', {})]
        if extra_empty:
            body += [('NATIVE_PERFORM_ENTER', {}), ('NATIVE_PERFORM_RETURN', {})]
            state['native_perform_calls'] = 2
        body += [('DRAIN_EVENTS', {'timeout_seconds': 2.0})]
        state['drain_timeout_seconds'] = [2.0]
    body += [('SYNLOOP_RETURN', {})] if kind == 'control' else [('SYNLOOP_SYSTEM_EXIT', {'code': 0})]
    body += [('TERMINAL_SNAPSHOT', state)]
    return rows(body)


class Tests(unittest.TestCase):
    def test_clock_is_cell_elapsed_and_ties_allowed(self):
        from unittest.mock import patch
        with patch('driver.time.monotonic_ns', side_effect=[1000000, 1000005, 1000005]):
            rec = Recorder(io.StringIO())
            rec.emit('begin', {})
            rec.emit('end', {})
        self.assertEqual([r['monotonic_ns'] for r in rec.events], [5, 5])
        with patch('driver.time.monotonic_ns', return_value=130):
            rec = Recorder(io.StringIO(), start_ns=100)
            rec.emit('begin', {})
        self.assertEqual(rec.events[0]['monotonic_ns'], 30)
        with self.assertRaises(ValueError):
            Recorder(io.StringIO(), start_ns=True)
        with patch('driver.time.monotonic_ns', return_value=99):
            rec = Recorder(io.StringIO(), start_ns=100)
            with self.assertRaises(CollectionFailure):
                rec.emit('begin', {})

    def test_four_cell_synthetic_signatures(self):
        cells = {label: evaluate(94, trace94(kind), {}) for label, kind in (
            ('before-control', 'control'), ('after-control', 'control'),
            ('before-trigger', 'stranded'), ('after-trigger', 'flushed_exit'))}
        self.assertTrue(all(c['execution_status'] == 'COMPLETED' for c in cells.values()))
        self.assertEqual(qualify_four_cells(cells), 'NATIVE_FIXED_PAIR_VERIFIED')
        cells['before-trigger'] = evaluate(94, trace94('flushed_exit'), {})
        self.assertEqual(qualify_four_cells(cells), 'NATIVE_CONTRAST_NOT_ESTABLISHED')

    def test_empty_scan_not_duplicate_callback(self):
        value = evaluate(94, trace94(extra_empty=True), {})
        self.assertEqual(value['execution_status'], 'COMPLETED')
        self.assertEqual(value['native_outcome'], 'SATISFIED')
        self.assertFalse(value['signature']['satisfied'])
        self.assertEqual(value['observations']['callback_counts'], {'op_a': 1, 'op_b': 1})

    def test_callback_order_not_sorted_away(self):
        e = trace94()
        mapping = {'op_a': 'op_b', 'op_b': 'op_a'}
        for row in e:
            if row['event'].startswith(('CALLBACK_ENTER:', 'CALLBACK_RETURN:')):
                prefix, token = row['event'].split(':')
                row['event'] = prefix + ':' + mapping[token]
        e[-2]['fields']['callback_receipts'] = ['op_a', 'op_b']
        value = evaluate(94, e, {})
        self.assertEqual((value['execution_status'], value['native_outcome']), ('COMPLETED', 'VIOLATED'))

    def test_receipts_must_be_inside_native_profile(self):
        e = trace94()
        e = [r for r in e if r['event'] not in ('NATIVE_PERFORM_ENTER', 'NATIVE_PERFORM_RETURN')]
        for i, row in enumerate(e):
            row['seq'] = i + 1
        e[-2]['fields']['native_perform_calls'] = 0
        self.assertEqual(evaluate(94, e, {})['execution_status'], 'COLLECTION_FAILURE')
        e = trace94()
        i = next(i for i, r in enumerate(e) if r['event'] == 'CALLBACK_RETURN:op_b')
        e[i]['event'] = 'NATIVE_PERFORM_RETURN'
        self.assertEqual(evaluate(94, e, {})['execution_status'], 'COLLECTION_FAILURE')

    def test_typed_counts_and_exact_numeric_timeout(self):
        for bad in (True, 1.0, '1', None):
            e = trace94()
            e[-2]['fields']['callback_counts']['op_a'] = bad
            self.assertEqual(evaluate(94, e, {})['execution_status'], 'COLLECTION_FAILURE')
        e = trace94()
        e[-2]['fields']['drain_timeout_seconds'] = [2.0000000001]
        for r in e:
            if r['event'] == 'DRAIN_EVENTS':
                r['fields']['timeout_seconds'] = 2.0000000001
        value = evaluate(94, e, {})
        self.assertEqual(value['execution_status'], 'COMPLETED')
        self.assertFalse(value['signature']['satisfied'])
        for bad in (True, float('nan'), float('inf'), '2'):
            e = trace94()
            e[-2]['fields']['drain_timeout_seconds'] = [bad]
            for r in e:
                if r['event'] == 'DRAIN_EVENTS':
                    r['fields']['timeout_seconds'] = bad
            self.assertEqual(evaluate(94, e, {})['execution_status'], 'COLLECTION_FAILURE')

    def test_exit_type_and_balance(self):
        e = trace94('flushed_exit')
        e[-2]['fields']['system_exit_code'] = True
        e[-3]['fields']['code'] = True
        self.assertEqual(evaluate(94, e, {})['execution_status'], 'COLLECTION_FAILURE')
        e = trace94()
        e[-2]['fields']['callback_enter_return_balance']['op_a'] = [1, 0]
        self.assertEqual(evaluate(94, e, {})['execution_status'], 'COLLECTION_FAILURE')

    def test_invalid_input_queue_is_environment_not_bug(self):
        e = trace94()
        e[3]['fields']['pending_ids'] = ['op_a']
        self.assertEqual(evaluate(94, e, {})['execution_status'], 'ENVIRONMENT_FAILURE')

    def test_failure_typed_prefix_and_history(self):
        def synthetic(history, emit):
            for row in trace94()[1:9]:
                emit(row['event'], row['fields'])
            raise ValueError('synthetic unexpected native-window exception')
        value = capture(94, synthetic, 'control', Recorder(io.StringIO()), {})
        self.assertEqual((value['execution_status'], value['native_outcome']), ('COMPLETED', 'UNRESOLVED'))
        def wrong(history, emit):
            for row in trace94('stranded')[1:-1]:
                emit(row['event'], row['fields'])
        self.assertEqual(capture(94, wrong, 'control', Recorder(io.StringIO()), {})['execution_status'],
                         'ENVIRONMENT_FAILURE')
        def malformed(history, emit):
            emit('SYNLOOP_ENTER', {})
            raise ValueError('synthetic missing preconditions')
        self.assertEqual(capture(94, malformed, 'control', Recorder(io.StringIO()), {})['execution_status'],
                         'COLLECTION_FAILURE')

    def test_raw_labels_missing_events_and_seq(self):
        for change in (lambda e: e[1]['fields'].update(original_rank=94),
                       lambda e: e[-2]['fields'].update(native_outcome='SATISFIED'),
                       lambda e: e[0].update(seq=0),
                       lambda e: e[4].update(monotonic_ns=True),
                       lambda e: e.pop(6)):
            e = trace94()
            change(e)
            self.assertEqual(evaluate(94, e, {})['execution_status'], 'COLLECTION_FAILURE')
        self.assertEqual(evaluate(94, trace94(), {})['execution_status'], 'COMPLETED')
        for text in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":'):
            with self.assertRaises(CollectionFailure):
                loads(text)

    def test_sticky_recorder(self):
        rec = Recorder(io.StringIO(), max_bytes=1)
        with self.assertRaises(CollectionFailure):
            rec.emit('begin', {})
        rec.max_bytes = 100000
        with self.assertRaises(CollectionFailure):
            rec.emit('end', {})

    def test_exact_pid(self):
        self.assertTrue(require_process_identity({'pid': 900}, 900, 900))
        for native, supervisor, footer in ((True, 1, 1), (900, 901, 900), (900, 900, 901), ('900', 900, 900)):
            with self.assertRaises(CollectionFailure):
                require_process_identity({'pid': native}, supervisor, footer)

    def test_static_binding_on_both_exact_trees(self):
        work = SCOPE / 'synthetic_work'
        work.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='r94_', dir=str(work)) as temporary:
            temp = Path(temporary)
            fixture = temp / 'fixture'
            fixture.mkdir()
            runtime = temp / 'standalone'
            runtime.mkdir()
            exe = runtime / 'python.exe'
            exe.write_bytes(b'SYNTHETIC NONEXECUTABLE IDENTITY FIXTURE; NEVER LAUNCH')
            deps = runtime / 'dependencies'
            deps.mkdir()
            marker = deps / 'SYNTHETIC.txt'
            marker.write_bytes(b'NOT AN INSTALLED ENVIRONMENT')
            versions = {}
            for side in ('before', 'after'):
                tree = SOURCE_BASE / side / 'tree'
                manifest_path = tree.parent / 'SOURCE_MANIFEST.json'
                manifest = loads(manifest_path.read_text(encoding='utf-8'))
                versions[side] = dict(executable=str(exe), executable_sha256=sha256(exe),
                    source_root=str(tree), source_commit=PROTOCOL[side + '_sha'], fixture_root=str(fixture),
                    python_version='3.12.10', package_version='5.5.0rc1', source_manifest_sha256=sha256(manifest_path),
                    source_files={str(tree / p): v['sha256'] for p, v in manifest['files'].items()},
                    module_files={name: str(tree / relative) for name, relative in (
                        ('celery', 'celery/__init__.py'), ('celery.worker.loops', 'celery/worker/loops.py'),
                        ('celery.worker.consumer.consumer', 'celery/worker/consumer/consumer.py'),
                        ('celery.bootsteps', 'celery/bootsteps.py'), ('celery.worker.state', 'celery/worker/state.py'))},
                    dependency_paths=[str(deps)], dependency_files={str(marker): sha256(marker)})
            lock = dict(rank=94, status='ENVIRONMENT_AND_IMPORT_IDENTITY_FROZEN', synthetic_test_only=True,
                        never_use_for_native=True, versions=versions, fixture_files={}, protocol_sha256=sha256(PROTOCOL_PATH))
            lp = temp / 'SYNTHETIC_ENVIRONMENT_LOCK.json'
            lp.write_text(json.dumps(lock), encoding='utf-8')
            for side in ('before', 'after'):
                spec = build_rank94(lp, PROTOCOL_PATH, RECIPE_PATH, side + '-control',
                                    'SYNTHETIC_ONLY', temp / 'cell', parent_approved=False)
                self.assertEqual(spec['code_bindings']['synloop']['firstlineno'], 108)
                self.assertEqual(spec['code_bindings']['perform_pending_operations']['firstlineno'], 246)
                self.assertEqual(spec['code_bindings']['call_soon']['firstlineno'], 239)
                self.assertIn('maybe_shutdown', spec['code_bindings'])
                self.assertEqual(spec['callsite_ids'], {})
                with self.assertRaises(AdmissionFailure):
                    validate_spec(spec, runtime=False)
                bad = copy.deepcopy(spec)
                bad['original_rank'] = 80
                with self.assertRaises(IdentityFailure):
                    validate_spec(bad, runtime=False, require_approval=False)
        self.assertFalse((SOURCE_BASE / 'before/tree/t/unit/test_loops.py').exists())
        self.assertTrue((SOURCE_BASE / 'after/tree/t/unit/test_loops.py').is_file())

    def test_frozen_bytes_and_target_guard(self):
        self.assertEqual(sha256(RECIPE_PATH), PROTOCOL['runnable_recipe']['sha256'])
        self.assertEqual(sha256(PROTOCOL_PATH), '18dac2117e71a91a26308c1609a446390dcbe709f00e8c8e5dc66795e32dde3f')
        self.assertEqual(ATTEMPTED_IMPORTS, [])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', required=True)
    a = p.parse_args()
    report = Path(a.report).resolve()
    if SCOPE not in report.parents:
        raise ValueError('Report must be inside owned scope')
    adapter_before = {str(p): sha256(p) for p in HERE.glob('*.py')}
    baseline = {str(p): sha256(p) for p in
                list((OLD / 'harness/native_v2').glob('*.py')) + [PROTOCOL_PATH, RECIPE_PATH]}
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    changed = [p for p, h in baseline.items() if sha256(p) != h]
    adapter_drift = [p for p, h in adapter_before.items() if sha256(p) != h]
    payload = dict(schema='SYNTHETIC_ONLY_NOT_NATIVE', rank=94, python=platform.python_version(),
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        passed=result.wasSuccessful() and not changed and not adapter_drift and not ATTEMPTED_IMPORTS,
        adapter_file_hashes=adapter_before, adapter_file_drift=adapter_drift,
        attempted_target_imports=ATTEMPTED_IMPORTS, native_operations=0, network_calls=0,
        old_input_drift=changed, old_input_hashes=baseline,
        failure_details=[text for _, text in result.failures + result.errors])
    with report.open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: payload[k] for k in ('tests_run', 'passed', 'failures', 'errors')}))
    return 0 if payload['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
