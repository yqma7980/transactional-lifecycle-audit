"""CPython 3.8-compatible native adapter. Importing this module runs no target."""
import argparse
import importlib.util
import json
import os
import platform
import sys
import time
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from evaluator import evaluate, evaluate_failure, result
from identity import (ADMITTED_RANK, RECOVERY_ROOT, AdmissionFailure, IdentityFailure,
                      file_map, inside, load_native, sha256, validate_spec, verify_loaded_targets)
from observations import CollectionFailure, FixtureFailure, json_value, loads

RUNTIME_FILES = ('driver.py', 'evaluator.py', 'observations.py', 'identity.py')
COLLECTOR_CONTRACT = 'TYPED_GRAMMAR_FIRST_GENERIC_INTEGRITY_V1'


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=True, allow_nan=False, indent=2)
        stream.write('\n')


def exception_record(exc):
    return {'type_fqn': type(exc).__module__ + '.' + type(exc).__qualname__, 'message': str(exc),
            'traceback': ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            'frames': [{'filename': str(Path(f.filename).resolve()), 'lineno': f.lineno, 'function': f.name}
                       for f in traceback.extract_tb(exc.__traceback__)]}


class Recorder:
    def __init__(self, stream, max_bytes=16 * 1024 * 1024, start_ns=None):
        self.stream = stream
        self.start_ns = time.monotonic_ns() if start_ns is None else start_ns
        if type(self.start_ns) is not int or self.start_ns < 0:
            raise ValueError('monotonic origin must be a nonnegative integer')
        self.max_bytes = max_bytes
        self.bytes = 0
        self.events = []
        self.failure = None

    def emit(self, name, fields):
        if self.failure is not None:
            raise CollectionFailure('earlier emit failure is sticky')
        try:
            if type(name) is not str or type(fields) is not dict:
                raise CollectionFailure('invalid emit arguments')
            json_value(fields, raw=True)
            elapsed_ns = time.monotonic_ns() - self.start_ns
            if elapsed_ns < 0:
                raise CollectionFailure('clock precedes cell origin')
            row = dict(seq=len(self.events) + 1, monotonic_ns=elapsed_ns, event=name, fields=fields)
            text = json.dumps(row, ensure_ascii=True, allow_nan=False) + '\n'
            count = len(text.encode('utf-8'))
            if self.bytes + count > self.max_bytes:
                raise CollectionFailure('raw trace byte cap exceeded')
            written = self.stream.write(text)
            if written != len(text):
                raise CollectionFailure('short trace write')
            self.stream.flush()
            self.bytes += count
            # Freeze the same serialized bytes, not aliases later changed by native code.
            self.events.append(loads(text))
        except Exception as exc:
            self.failure = exception_record(exc)
            raise CollectionFailure('emit/write failure') from exc


def capture(rank, run, history, recorder, sites):
    """Injectable only for synthetic tests; production uses the hash-bound frozen recipe."""
    failure = None
    start = {79: 'SERIALIZE_ENTER', 80: 'DECODE_ENTER', 94: 'SYNLOOP_ENTER'}[rank]
    try:
        recorder.emit('begin', {})
        run(history, recorder.emit)
    except BaseException as exc:
        native_started = any(e['event'] == start for e in recorder.events)
        terminal_seen = any(e['event'] == 'TERMINAL_SNAPSHOT' for e in recorder.events)
        phase = 'CLEANUP' if terminal_seen else ('NATIVE_WINDOW' if native_started else 'FIXTURE_SETUP')
        failure = dict(phase=phase, last_event=recorder.events[-1]['event'] if recorder.events else None,
                       exception=exception_record(exc), capture_intact=recorder.failure is None)
    if recorder.failure is not None:
        return result('COLLECTION_FAILURE', 'NOT_EVALUATED', 'Sticky recorder failure.',
                      failure_envelope=failure, recorder_failure=recorder.failure)
    try:
        recorder.emit('end', {})
    except CollectionFailure:
        return result('COLLECTION_FAILURE', 'NOT_EVALUATED', 'Failed to close raw capture.',
                      failure_envelope=failure, recorder_failure=recorder.failure)
    if failure is not None:
        if failure['phase'] == 'FIXTURE_SETUP':
            return result('ENVIRONMENT_FAILURE', 'NOT_EVALUATED', 'Fixture/setup failed before native window.',
                          failure_envelope=failure)
        if failure['phase'] == 'CLEANUP':
            return result('COLLECTION_FAILURE', 'NOT_EVALUATED', 'Recipe cleanup failed after terminal.',
                          failure_envelope=failure)
        return evaluate_failure(rank, recorder.events, failure)
    oracle = evaluate(rank, recorder.events, sites)
    if oracle['execution_status'] == 'COMPLETED':
        # Invocation-history binding is administrative; evaluate() remains label-blind.
        state = oracle['observations']
        wrong = rank == 80 and state['serialized_argument_count'] != (1 if history == 'control' else 0)
        if rank == 94:
            expected = 'RETURN_NONE' if history == 'control' else 'RAISE_SYSTEM_EXIT'
            wrong = any(e['event'] in ('MAYBE_SHUTDOWN_RETURN', 'MAYBE_SHUTDOWN_RAISE') and
                        e['event'] != ('MAYBE_SHUTDOWN_RETURN' if expected == 'RETURN_NONE' else 'MAYBE_SHUTDOWN_RAISE')
                        for e in recorder.events)
        if wrong:
            return result('ENVIRONMENT_FAILURE', 'NOT_EVALUATED', 'Observed boundary input differs from frozen invocation.',
                          fixture_invalid=True)
    return oracle


def run_cell(spec):
    cell_started_ns = time.monotonic_ns()
    if not inside(Path.cwd(), RECOVERY_ROOT) or inside(Path.cwd(), RECOVERY_ROOT / 'sources'):
        raise IdentityFailure('output working directory must be in recovery and outside sources')
    dest = Path.cwd() / 'native'
    dest.mkdir(exist_ok=False)
    recorder = None
    identity = None
    phase = 'SPEC_IDENTITY'
    try:
        if spec.get('original_rank') != ADMITTED_RANK:
            raise AdmissionFailure('This adapter admits only its assigned recovery rank.')
        validate_spec(spec)
        if spec['collector_contract'] != COLLECTOR_CONTRACT:
            raise IdentityFailure('parent must use typed grammar before generic integrity collector')
        expected_adapter = {str(HERE / name) for name in RUNTIME_FILES}
        if set(spec['adapter_files']) != expected_adapter:
            raise IdentityFailure('missing/extra adapter hash bindings')
        file_map(spec['adapter_files'])
        phase = 'NATIVE_IMPORT_SETUP'
        observed = load_native(spec)
        identity = {k: spec[k] for k in ('case_id', 'run_id', 'cell', 'source_commit', 'protocol_sha256',
                    'protocol_file_sha256', 'environment_lock_sha256', 'source_manifest_sha256', 'source_files', 'fixture_files',
                    'recipe_sha256', 'callsite_ids', 'adapter_files', 'collector_contract',
                    'executable_sha256', 'dependency_paths', 'dependency_files', 'source_manifest_path')}
        identity.update(observed, pid=os.getpid(), executable=sys.executable,
                        python_version=platform.python_version(), adapter_version='celery_completion_r094_v4',
                        cell_monotonic_origin_ns=cell_started_ns,
                        monotonic_ns_contract='ELAPSED_NS_SINCE_RUN_CELL_ENTRY')
        write_new(dest / 'identity.json', identity)
        phase = 'RECIPE_IDENTITY'
        if sha256(spec['recipe']) != spec['recipe_sha256']:
            raise IdentityFailure('recipe changed before import')
        recipe_spec = importlib.util.spec_from_file_location('s10_native_recipe', spec['recipe'])
        recipe = importlib.util.module_from_spec(recipe_spec)
        recipe_spec.loader.exec_module(recipe)
        phase = 'CAPTURE'
        with (dest / 'raw_trace.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
            recorder = Recorder(stream, start_ns=cell_started_ns)
            oracle = capture(spec['original_rank'], recipe.run, spec['history'], recorder, spec['callsite_ids'])
        phase = 'POST_CAPTURE_IDENTITY'
        verify_loaded_targets(spec)
        file_map(spec['source_files'])
        file_map(spec['dependency_files'])
        file_map(spec['fixture_files'])
        file_map(spec['adapter_files'])
        if sha256(spec['recipe']) != spec['recipe_sha256']:
            raise IdentityFailure('recipe changed during capture')
    except AdmissionFailure as exc:
        oracle = result('NOT_RUN', 'NOT_EVALUATED', str(exc))
    except IdentityFailure as exc:
        oracle = result('SOURCE_IDENTITY_FAILURE', 'NOT_EVALUATED', str(exc),
                        failure_envelope={'phase': phase, 'exception': exception_record(exc)})
    except BaseException as exc:
        status = 'ENVIRONMENT_FAILURE' if phase == 'NATIVE_IMPORT_SETUP' else 'COLLECTION_FAILURE'
        oracle = result(status, 'NOT_EVALUATED', 'Driver boundary failure: ' + phase,
                        failure_envelope={'phase': phase, 'exception': exception_record(exc)})
    raw = dest / 'raw_trace.jsonl'
    digest = sha256(raw) if raw.exists() else None
    count = len(recorder.events) if recorder is not None else 0
    failure = oracle.get('failure_envelope')
    if failure is not None or oracle.get('recorder_failure') is not None:
        write_new(dest / 'failure.json', {'failure_envelope': failure, 'recorder_failure': oracle.get('recorder_failure'),
                                        'raw_trace_sha256': digest, 'events': count})
    write_new(dest / 'trace_manifest.json', {'sha256': digest, 'events': count,
        'cell_monotonic_origin_ns': cell_started_ns,
        'monotonic_ns_contract': 'ELAPSED_NS_SINCE_RUN_CELL_ENTRY',
        'observation_validated': oracle['execution_status'] == 'COMPLETED',
        'capture_intact': recorder is not None and recorder.failure is None})
    oracle.update({k: spec.get(k) for k in ('case_id', 'run_id', 'cell', 'protocol_sha256')})
    oracle.update(raw_trace_sha256=digest, events=count, evaluator_sha256=sha256(HERE / 'evaluator.py'),
                  adapter_version='celery_completion_r094_v4', collector_contract=COLLECTOR_CONTRACT)
    if oracle['execution_status'] == 'COMPLETED':
        oracle['validated_event_order'] = [e['event'] for e in recorder.events]
    write_new(dest / 'native_oracle.json', oracle)
    return oracle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True)
    args = parser.parse_args()
    spec = loads(Path(args.spec).read_text(encoding='utf-8'))
    oracle = run_cell(spec)
    print(json.dumps({k: oracle[k] for k in ('execution_status', 'native_outcome', 'adapter_version')}))
    return 0 if oracle['execution_status'] == 'COMPLETED' else 2


if __name__ == '__main__':
    sys.exit(main())
