"""Synthetic observations/driver errors only. Import guard forbids all target packages."""
import argparse
import ast
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True


class NoTargets:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('django', 'celery', 'airflow', 'keras', 'tensorflow', 'tf_keras'):
            raise AssertionError('Target import forbidden by synthetic test guard: ' + fullname)


sys.meta_path.insert(0, NoTargets())
from driver import Recorder, capture, run_cell
from evaluator import evaluate, qualify_four_cells
from identity import AdmissionFailure, IdentityFailure, sha256, validate_spec
from observations import ATTRS, CollectionFailure, loads
from spec_builder import build_rank79

ROOT = HERE.parents[1]
RECIPE = ROOT / 'protocols/django_celery/r079_django_pr12055/runnable_core_recipe.py'
PROTOCOL = ROOT / 'governance/frozen_protocols/r079/CASE_PILOT_PROTOCOL.json'
LOCK = ROOT / 'envs/r079/CASE_ENVIRONMENT_LOCK.json'
CHECKS = []


def events(rows):
    return [dict(seq=i, monotonic_ns=100, event=name, fields=copy.deepcopy(fields))
            for i, (name, fields) in enumerate([('begin', {})] + rows + [('end', {})])]


def sites79():
    return {'r79_restored_getattr': {'filename': str(RECIPE.resolve()), 'lineno': 37, 'function': 'run'},
            'r79_url_storage': {'filename': str((HERE / 'SYNTHETIC_ONLY_files.py').resolve()), 'lineno': 62, 'function': 'url'}}


def missing(attribute):
    member = 'storage' if attribute == 'url' else attribute
    sites = sites79()
    selected = [sites['r79_restored_getattr']]
    if attribute == 'url':
        selected.append(sites['r79_url_storage'])
    trace = 'Traceback (most recent call last):\n' + ''.join(
        '  File "{filename}", line {lineno}, in {function}\n    SYNTHETIC_ONLY\n'.format(**s) for s in selected)
    message = "'FieldFile' object has no attribute '{}'".format(member)
    return dict(type_fqn='builtins.AttributeError', message=message, observed_attribute=attribute,
                traceback=trace + 'AttributeError: ' + message + '\n')


def trace79(violation=False, unequal=None):
    checks = {a: dict(status='VALUE', equal=True, error=None) for a in ATTRS}
    witnesses = {'name': 'unused/test_file.py', 'url': '/s10-media/unused/test_file.py',
                 'storage_type': 'django.core.files.storage.DefaultStorage',
                 'instance_key': {'model_label': 'm003_s10_django_fixture.Document', 'pk': 1},
                 'field_key': {'model_label': 'm003_s10_django_fixture.Document', 'name': 'myfile'}}
    if violation:
        for a in ('url', 'storage', 'instance', 'field'):
            checks[a] = dict(status='ATTRIBUTE_ERROR', equal=None, error=missing(a))
        witnesses = {'name': 'unused/test_file.py'}
    if unequal:
        checks[unequal]['equal'] = False
    state = dict(serialization_calls=1, restoration_calls=1, pickle_protocol=4,
                 file_type='django.db.models.fields.files.FieldFile', checks=checks, witnesses=witnesses,
                 native_access_error_count=4 if violation else 0, terminal='RESTORATION_AND_CHECKS_COMPLETE')
    rows = [('FIXTURE_READY', {'pk': 1, 'name': 'unused/test_file.py'}),
            ('REFERENCE_CAPTURED', {'name': 'unused/test_file.py', 'url': '/s10-media/unused/test_file.py'}),
            ('SERIALIZE_ENTER', {'pickle_protocol': 4}), ('SERIALIZE_RETURN', {'bytes': 99}),
            ('RESTORE_ENTER', {}), ('RESTORE_RETURN', {}), ('FILE_SELECTED', {'file_type': state['file_type']})]
    rows += [('PROPERTY_CHECK:' + a, checks[a]) for a in ATTRS] + [('TERMINAL_SNAPSHOT', state)]
    return events(rows)


def replace_check(trace, attribute, check):
    for row in trace:
        if row['event'] == 'PROPERTY_CHECK:' + attribute:
            row['fields'] = copy.deepcopy(check)
        if row['event'] == 'TERMINAL_SNAPSHOT':
            row['fields']['checks'][attribute] = copy.deepcopy(check)


def replay(trace):
    def run(history, emit):
        for row in trace[1:-1]:
            emit(row['event'], row['fields'])
    return run


class Tests(unittest.TestCase):
    def expect(self, name, oracle, status, outcome):
        actual = (oracle['execution_status'], oracle['native_outcome'])
        passed = actual == (status, outcome)
        CHECKS.append(dict(name=name, passed=passed, actual=list(actual), expected=[status, outcome]))
        self.assertEqual(actual, (status, outcome), name + ': ' + oracle.get('reason', ''))

    def test_79_complete_and_no_contrast(self):
        good = evaluate(79, trace79(), sites79())
        bad = evaluate(79, trace79(True), sites79())
        self.expect('79-complete-satisfied', good, 'COMPLETED', 'SATISFIED')
        self.expect('79-declared-four-errors', bad, 'COMPLETED', 'VIOLATED')
        self.assertTrue(good['signature']['satisfied'])
        self.assertTrue(bad['signature']['declared_violation'])
        self.assertEqual(good['observations']['storage_identity'],
                         {'type_fqn': 'django.core.files.storage.DefaultStorage', 'within_cell_equal': True})
        self.assertEqual(bad['observations']['storage_identity']['status'], 'UNAVAILABLE')
        cells = dict(zip(('before-control', 'after-control', 'before-trigger', 'after-trigger'), (good, good, bad, good)))
        self.assertEqual(qualify_four_cells(cells), 'NATIVE_FIXED_PAIR_VERIFIED')
        cells['before-trigger'] = good
        self.assertEqual(qualify_four_cells(cells), 'NATIVE_CONTRAST_NOT_ESTABLISHED')
        cells['before-trigger'] = cells['after-trigger'] = bad
        self.assertEqual(qualify_four_cells(cells), 'NATIVE_CONTRAST_NOT_ESTABLISHED')
        CHECKS.append(dict(name='four-cell-valid-no-contrast-not-collection', passed=True))

    def test_79_each_equality(self):
        for attribute in ATTRS:
            oracle = evaluate(79, trace79(unequal=attribute), sites79())
            self.expect('79-unequal-' + attribute, oracle, 'COMPLETED', 'VIOLATED')
            self.assertFalse(oracle['signature']['declared_violation'])

    def test_79_typed_missing_counts(self):
        for key in ('serialization_calls', 'restoration_calls', 'pickle_protocol', 'native_access_error_count'):
            for value in (True, 1.0, '1'):
                trace = trace79()
                trace[-2]['fields'][key] = value
                self.expect('79-typed-' + key + '-' + repr(value), evaluate(79, trace, sites79()), 'COLLECTION_FAILURE', 'NOT_EVALUATED')
        for key in ('witnesses', 'terminal', 'file_type'):
            trace = trace79()
            del trace[-2]['fields'][key]
            self.expect('79-missing-' + key, evaluate(79, trace, sites79()), 'COLLECTION_FAILURE', 'NOT_EVALUATED')
        for value in (1, 0, None, 'true'):
            trace = trace79()
            replace_check(trace, 'storage', dict(status='VALUE', equal=value, error=None))
            self.expect('79-equality-type-' + repr(value), evaluate(79, trace, sites79()), 'COLLECTION_FAILURE', 'NOT_EVALUATED')

    def test_79_identity_and_unrelated_errors(self):
        for change in ('foreign-file', 'wrong-line', 'wrong-member', 'witness-phase', 'foreign-function'):
            trace = trace79(True)
            error = missing('storage')
            if change == 'foreign-file':
                error['traceback'] = error['traceback'].replace(str(RECIPE.resolve()), str(HERE / 'foreign' / RECIPE.name))
            elif change == 'wrong-line':
                error['traceback'] = error['traceback'].replace('line 37', 'line 38')
            elif change == 'wrong-member':
                error['message'] = "'FieldFile' object has no attribute 'unrelated'"
            elif change == 'witness-phase':
                error['traceback'] = error['traceback'].replace('line 37', 'line 49')
            else:
                error['traceback'] = error['traceback'].replace('in run', 'in other')
            replace_check(trace, 'storage', dict(status='ATTRIBUTE_ERROR', equal=None, error=error))
            self.expect('79-origin-' + change, evaluate(79, trace, sites79()), 'COMPLETED', 'UNRESOLVED')
        trace = trace79()
        trace[-2]['fields']['witnesses']['instance_key']['pk'] = True
        self.expect('79-pk-bool', evaluate(79, trace, sites79()), 'COLLECTION_FAILURE', 'NOT_EVALUATED')
        trace = trace79()
        trace[-2]['fields']['witnesses']['name'] = 'unexpected-but-observed'
        oracle = evaluate(79, trace, sites79())
        self.expect('79-valid-witness-deviation', oracle, 'COMPLETED', 'SATISFIED')
        self.assertFalse(oracle['signature']['satisfied'])

    def test_79_capture_driver(self):
        for violation in (False, True):
            rec = Recorder(io.StringIO())
            oracle = capture(79, replay(trace79(violation)), 'trigger', rec, sites79())
            self.expect('79-capture-' + str(violation), oracle, 'COMPLETED', 'VIOLATED' if violation else 'SATISFIED')
        def unexpected(history, emit):
            for row in trace79()[1:4]:
                emit(row['event'], row['fields'])
            raise RuntimeError('SYNTHETIC native-window failure, not a target call')
        rec = Recorder(io.StringIO())
        oracle = capture(79, unexpected, 'trigger', rec, sites79())
        self.expect('79-unexpected-native-window', oracle, 'COMPLETED', 'UNRESOLVED')
        self.assertFalse(any(e['event'] == 'TERMINAL_SNAPSHOT' for e in rec.events))
        def fixture_error(history, emit):
            raise ValueError('SYNTHETIC invalid fixture')
        self.expect('79-setup-failure', capture(79, fixture_error, 'control', Recorder(io.StringIO()), sites79()),
                    'ENVIRONMENT_FAILURE', 'NOT_EVALUATED')

    def test_recorder_sticky_failure_and_copy(self):
        class BadStream(io.StringIO):
            def flush(self):
                raise OSError('SYNTHETIC disk error')
        def swallowed(history, emit):
            try:
                emit('SYNTHETIC', {})
            except Exception:
                pass
        self.expect('sticky-stream-failure', capture(79, swallowed, 'control', Recorder(BadStream()), sites79()),
                    'COLLECTION_FAILURE', 'NOT_EVALUATED')
        rec = Recorder(io.StringIO())
        fields = {'value': [1]}
        rec.emit('SYNTHETIC', fields)
        fields['value'].append(2)
        self.assertEqual(rec.events[0]['fields'], {'value': [1]})
        self.assertRaises(CollectionFailure, Recorder(io.StringIO(), max_bytes=1).emit, 'SYNTHETIC', {})
        CHECKS.append(dict(name='snapshot-alias-copy-and-byte-cap', passed=True))

    def test_trace_integrity(self):
        for change in ('missing-terminal', 'seq-bool', 'time-regression', 'nan', 'raw-label', 'check-disagreement'):
            trace = trace79()
            if change == 'missing-terminal':
                trace.pop(-2)
                trace[-1]['seq'] -= 1
            elif change == 'seq-bool':
                trace[1]['seq'] = True
            elif change == 'time-regression':
                trace[2]['monotonic_ns'] = 99
            elif change == 'nan':
                trace[4]['fields']['bytes'] = float('nan')
            elif change == 'raw-label':
                trace[2]['fields']['case_id'] = 'forbidden'
            else:
                trace[-2]['fields']['checks']['name']['equal'] = False
            self.expect(change, evaluate(79, trace, sites79()), 'COLLECTION_FAILURE', 'NOT_EVALUATED')
        self.assertRaises(CollectionFailure, loads, '{"x":1,"x":2}')
        self.assertRaises(CollectionFailure, loads, '{"x":NaN}')

    def test_real_lock_builder_static_only(self):
        for cell in ('before-control', 'after-control', 'before-trigger', 'after-trigger'):
            spec = build_rank79(LOCK, PROTOCOL, RECIPE, cell, 'synthetic-spec-only', str(HERE / 'not_created_work'))
            self.assertFalse(spec['g3_parent_approved'])
            self.assertEqual(spec['callsite_ids']['r79_url_storage']['lineno'], 62)
            self.assertEqual(spec['python_version'], '3.8.20')
            self.assertRaises(AdmissionFailure, validate_spec, spec)
            bad = copy.deepcopy(spec)
            bad['recipe_sha256'] = '0' * 64
            self.assertRaises(IdentityFailure, validate_spec, bad, False, False)
            bad = copy.deepcopy(spec)
            bad['source_commit'] = '0' * 40
            self.assertRaises(IdentityFailure, validate_spec, bad, False, False)
            CHECKS.append(dict(name='sealed-spec-' + cell, passed=True))

    def test_sealed_identity_rejections(self):
        spec = build_rank79(LOCK, PROTOCOL, RECIPE, 'before-control', 'synthetic-spec-only', str(HERE / 'not_created_work'))
        for field in ('protocol_file_sha256', 'protocol_sha256', 'environment_lock_sha256', 'source_manifest_sha256'):
            bad = copy.deepcopy(spec)
            bad[field] = '0' * 64
            self.assertRaises(IdentityFailure, validate_spec, bad, False, False)
            CHECKS.append(dict(name='reject-identity-' + field, passed=True))
        for field in ('source_files', 'module_files', 'fixture_files', 'code_bindings', 'callsite_ids'):
            bad = copy.deepcopy(spec)
            bad[field].pop(next(iter(bad[field])))
            self.assertRaises(IdentityFailure, validate_spec, bad, False, False)
            CHECKS.append(dict(name='reject-missing-' + field, passed=True))
        bad = copy.deepcopy(spec)
        bad['callsite_ids']['r79_restored_getattr']['lineno'] = 38
        self.assertRaises(IdentityFailure, validate_spec, bad, False, False)
        CHECKS.append(dict(name='reject-unfrozen-recipe-callsite', passed=True))

    def test_interrupted_capture_prefix_and_chain(self):
        def interrupted(history, emit):
            for row in trace79()[1:4]:
                emit(row['event'], row['fields'])
            try:
                raise ValueError('SYNTHETIC inner error')
            except ValueError as exc:
                raise RuntimeError('SYNTHETIC outer error') from exc
        rec = Recorder(io.StringIO())
        self.expect('intact-chained-native-window-exception', capture(79, interrupted, 'trigger', rec, sites79()),
                    'COMPLETED', 'UNRESOLVED')
        def malformed(history, emit):
            emit('SERIALIZE_ENTER', {'pickle_protocol': 4})
            raise RuntimeError('SYNTHETIC missing fixture evidence')
        self.expect('interrupted-missing-prefix', capture(79, malformed, 'trigger', Recorder(io.StringIO()), sites79()),
                    'COLLECTION_FAILURE', 'NOT_EVALUATED')
        def wrong_type(history, emit):
            for row in trace79()[1:3]:
                emit(row['event'], row['fields'])
            emit('SERIALIZE_ENTER', {'pickle_protocol': True})
            raise RuntimeError('SYNTHETIC malformed interrupted observation')
        self.expect('interrupted-wrong-type', capture(79, wrong_type, 'trigger', Recorder(io.StringIO()), sites79()),
                    'COLLECTION_FAILURE', 'NOT_EVALUATED')

    def test_fixture_invalid_and_wrapper_preserved(self):
        trace = trace79()
        trace[1]['fields']['name'] = 'illegal-initial-input'
        self.expect('illegal-file-fixture-not-native-bug', evaluate(79, trace, sites79()), 'ENVIRONMENT_FAILURE', 'NOT_EVALUATED')
        trace = trace79()
        original = copy.deepcopy(trace)
        oracle = evaluate(79, trace, sites79())
        self.assertEqual(trace, original)
        self.assertEqual(oracle['observations']['witnesses']['storage_type'], 'django.core.files.storage.DefaultStorage')
        self.assertEqual(oracle['observations']['instance_identity']['pk'], 1)
        CHECKS.append(dict(name='lossless-wrapper-and-association-mapping', passed=True))

    def test_driver_admission_fails_before_import(self):
        scratch = HERE / 'synthetic_work'
        scratch.mkdir(exist_ok=True)
        old = Path.cwd()
        with tempfile.TemporaryDirectory(dir=str(scratch)) as path:
            try:
                os.chdir(path)
                self.expect('unapproved-driver-no-target-import', run_cell({'original_rank': 79,
                    'schema': 'M003-S10-NATIVE-V2-SPEC-1', 'g3_parent_approved': False}), 'NOT_RUN', 'NOT_EVALUATED')
            finally:
                os.chdir(str(old))

    def test_python38_syntax_only(self):
        for path in HERE.glob('*.py'):
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path), feature_version=(3, 8) if sys.version_info >= (3, 9) else 8)
        self.assertFalse(any(name.split('.')[0] in ('django', 'celery') for name in sys.modules))
        CHECKS.append(dict(name='python38-grammar-no-target-modules', passed=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    report = dict(evidence_class='SYNTHETIC_ONLY_NOT_NATIVE', python=sys.version,
                  tests_run=outcome.testsRun, failures=len(outcome.failures), errors=len(outcome.errors),
                  checks=CHECKS, passed=outcome.wasSuccessful(), target_imports=0, native_calls=0,
                  files={p.name: sha256(p) for p in HERE.glob('*.py')})
    with Path(args.report).open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write('\n')
    return 0 if outcome.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
