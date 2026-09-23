"""Fresh G4 native repetitions with unchanged admitted producers and environments.

This coordinator separates operational labels from the shared method input. It
does not evaluate either method arm. Each rank is loaded in a separate process.
"""
import argparse
import importlib.util
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
sys.dont_write_bytecode = True
from g4_config import ROOT, ORDERS, config
from kit_io import read_json, loads, sha256, write_json_new
from collector_v5 import validate_native
from projection import project


def now():
    return datetime.now(timezone.utc).isoformat()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def verify(files):
    for path, digest in files.items():
        require(Path(path).is_file() and sha256(path) == digest, 'File drift: ' + path)


def load_original(c):
    spec = importlib.util.spec_from_file_location('historical_native_parent', c['coordinator'])
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    modules = None if c['rank'] == 79 else original.adapter_modules(c['adapter'])
    return original, modules


def native_capture(c):
    path = c['native_runner']
    require(sha256(path) == sha256(ROOT/'harness/bounded_runner_v4.py'), 'Original native runner bytes changed')
    require(sha256(path.with_name('_child_launcher.py')) == sha256(ROOT/'harness/_child_launcher.py'), 'Original native launcher bytes changed')
    require(c['runs'].is_relative_to(path.resolve().parents[1]), 'Native runner/run ownership mismatch')
    spec = importlib.util.spec_from_file_location('owned_native_capture_%d' % c['rank'], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.capture


def old_collect(c, original, modules, item, manifest):
    if c['rank'] == 94:
        result = original.collect(94, item, manifest, modules)
    else:
        # Only the operational output root differs from the old pilot. The native
        # protocol's cell label is still carried by the immutable run spec.
        original.RUNS = Path(item['run_directory']).parent
        proc = read_json(Path(item['run_directory']) / 'process.json')
        spec = read_json(item['path'])
        result = original.collect_cell(Path(item['run_directory']).name, spec, item['argv'], proc)
    if result['execution_status'] != 'COMPLETED':
        return result
    run = Path(item['run_directory'])
    spec, proc = read_json(item['path']), read_json(run / 'process.json')
    native = run / 'work/native'
    events = [loads(s) for s in (native / 'raw_trace.jsonl').read_text(encoding='utf-8').splitlines()]
    expected = {k: spec[k] for k in ('case_id', 'run_id', 'cell', 'executable', 'source_commit',
        'python_version', 'package_version', 'protocol_sha256', 'environment_lock_sha256', 'source_files', 'module_files')}
    expected.update(run_directory=str(run), argv=item['argv'], sequence_start=c['sequence_start'],
        evaluator_sha256=sha256(c['adapter'] / 'evaluator.py'),
        allowed_event_orders=[[e['event'] for e in events]])
    result['strict_v5_integrity'] = validate_native(native, proc, expected)
    require(result['native_outcome'] in ('SATISFIED', 'VIOLATED'), 'UNRESOLVED is not scoreable')
    return result


def runtime(c, original, lock):
    if c['rank'] == 79:
        return original.runtime_files()
    return original.inventory([Path(lock['versions'][s]['executable']).parent for s in ('before', 'after')])


def source(c, original):
    result = original.check_source() if c['rank'] == 79 else original.source(94)
    require(result['passed'], 'Complete source check failed')
    if c['rank'] == 94:
        require(all(not v['source_semantics_holds'] for v in result['versions'].values()), 'Source semantics hold')
    return result


def prepare(c):
    out = c['out']
    out.mkdir(exist_ok=False)
    try:
        require(not c['runs'].exists(), 'Formal output already exists')
        original, modules = load_original(c)
        old = read_json(c['old_pilot'] / 'PILOT_RUN_MANIFEST.json')
        admission = read_json(c['old_pilot'] / 'G3_ADMISSION.json')
        require(admission['passed'] is True and admission['manifest_sha256'] == sha256(c['old_pilot'] / 'PILOT_RUN_MANIFEST.json'), 'Historical admission drift')
        verify(old['files_sha256'])
        pilot = read_json(c['old_pilot'] / 'PILOT_RESULT.json')
        require(pilot['disposition'] == 'NATIVE_FIXED_PAIR_VERIFIED', 'Not an admitted fixed pair')
        old_results = {}
        for item in old['cells']:
            got = old_collect(c, original, modules, item, old)
            require(got['execution_status'] == 'COMPLETED', 'Prior native evidence no longer qualifies')
            require(got['native_outcome'] == pilot['cells'][item['cell']]['native_outcome'], 'Prior native outcome drift')
            old_results[item['cell']] = got
        write_json_new(out / 'ADMISSION_READBACK.json', dict(utc=now(), pid=os.getpid(),
            native_reruns=0, development_only=True, formal_statistical_rows=0, cells=old_results))
        lock = read_json(c['lock'])
        inventory = runtime(c, original, lock)
        require(inventory == read_json(c['old_pilot'] / 'RUNTIME_FILE_MANIFEST.json')['files_sha256'], 'Runtime bytes or membership changed')
        write_json_new(out / 'RUNTIME_BEFORE.json', dict(files_sha256=inventory))
        write_json_new(out / 'SOURCE_BEFORE.json', source(c, original))
        items = []
        for repetition, order in enumerate(ORDERS, 1):
            for cell in order:
                ordinal = len(items) + 1
                run_id = 'G4_R%03d_%03d' % (c['rank'], ordinal)
                run = c['runs'] / run_id
                builder = original.build_rank79 if c['rank'] == 79 else modules['spec_builder'].build_rank94
                spec = builder(c['lock'], c['frozen'] / 'CASE_PILOT_PROTOCOL.json',
                    c['frozen'] / 'runnable_core_recipe.py', cell, run_id, str(run / 'work'), True)
                validator = original.validate_spec if c['rank'] == 79 else modules['identity'].validate_spec
                validator(spec, runtime=False, require_approval=True)
                spec_path = out / (run_id + '.spec.json')
                write_json_new(spec_path, spec)
                flags = ['-I', '-B'] if c['rank'] == 79 else ['-I', '-S', '-B']
                argv = [spec['executable'], *flags, str(c['adapter'] / 'driver.py'), '--spec', str(spec_path)]
                items.append(dict(ordinal=ordinal, repetition=repetition, cell=cell, run_id=run_id,
                    path=str(spec_path), sha256=sha256(spec_path), argv=argv, run_directory=str(run)))
        files = dict(old['files_sha256'])
        files.update({str(p): sha256(p) for p in out.glob('*.json')})
        files[str(c['old_pilot'] / 'PILOT_RESULT.json')] = sha256(c['old_pilot'] / 'PILOT_RESULT.json')
        write_json_new(out / 'CASE_PLAN.json', dict(schema='M003-G4-NATIVE-PLAN-1', utc=now(),
            rank=c['rank'], adapter=str(c['adapter']), lock=str(c['lock']), sequence_start=c['sequence_start'],
            runs=str(c['runs']), files_sha256=files, cells=items, native_runs=12,
            labels_only_for_orchestration=True, formal_input_excludes_labels=True,
            original_producer_metadata_retained=True, previous_pilot_excluded_from_formal_data=True,
            process_bound_seconds=180, case_bound_seconds=900, max_stream_bytes=16777216,
            result_bound_bytes=2147483648, methods_not_evaluated_by_native_coordinator=True))
        print('Prepared r%d: unchanged source/runtime, prior evidence readback, 12 fresh identities.' % c['rank'], flush=True)
    except BaseException:
        write_json_new(out / 'PREPARATION_FAILURE.json', dict(utc=now(), traceback=traceback.format_exc(), native_runs=0))
        raise


def load_admitted(c):
    seal = read_json(ROOT / 'governance/G4_FORMAL_SEAL.json')
    require(seal['passed'] is True and seal['native_runs_before_seal'] == 0, 'No formal seal')
    verify(seal['files_sha256'])
    plan = read_json(c['out'] / 'CASE_PLAN.json')
    verify(plan['files_sha256'])
    original, modules = load_original(c)
    return plan, original, modules


def run(c):
    plan, original, modules = load_admitted(c)
    capture = native_capture(c)
    require(not c['runs'].exists(), 'Never replay or overwrite a native attempt')
    lock = read_json(c['lock'])
    before = read_json(c['out'] / 'RUNTIME_BEFORE.json')['files_sha256']
    require(runtime(c, original, lock) == before, 'Runtime changed before native launch')
    source(c, original)
    started = time.monotonic()
    write_json_new(c['out'] / 'FORMAL_START.json', dict(utc=now(), pid=os.getpid(), g4_started=True,
        seal_sha256=sha256(ROOT / 'governance/G4_FORMAL_SEAL.json')))
    results, stop = [], None
    for item in plan['cells']:
        r = dict(run_id=item['run_id'], ordinal=item['ordinal'], repetition=item['repetition'], cell=item['cell'])
        if stop:
            r.update(execution_status='NOT_RUN', native_outcome='NOT_EVALUATED', reason=stop)
        else:
            try:
                remaining = 900 - (time.monotonic() - started)
                require(remaining > 5, 'Case wall budget exhausted')
                verify(read_json(ROOT / 'governance/G4_FORMAL_SEAL.json')['files_sha256'])
                spec = read_json(item['path'])
                validator = original.validate_spec if c['rank'] == 79 else modules['identity'].validate_spec
                validator(spec, runtime=False, require_approval=True)
                process = capture(item['argv'], item['run_directory'], cwd='work',
                    timeout_seconds=min(180, remaining), max_log_bytes=16777216,
                    directory_limits=[{'paths': [str(c['runs'])], 'bytes': 2147483648}])
                r.update(old_collect(c, original, modules, item, plan))
                if r['execution_status'] == 'COMPLETED':
                    raw_path = Path(item['run_directory']) / 'work/native/raw_trace.jsonl'
                    events = [loads(s) for s in raw_path.read_text(encoding='utf-8').splitlines()]
                    projection_start = time.perf_counter()
                    projected = project(c['rank'], events)
                    input_path = c['out'] / (item['run_id'] + '.trace.json')
                    write_json_new(input_path, projected)
                    r.update(method_input=str(input_path), method_input_sha256=sha256(input_path),
                        projection_serialization_and_hash_seconds=time.perf_counter()-projection_start,
                        raw_trace=str(raw_path), raw_trace_sha256=sha256(raw_path),
                        native_target_pid=process['target_result']['pid'])
                r.update(process_record=str(Path(item['run_directory']) / 'process.json'),
                    process_record_sha256=sha256(Path(item['run_directory']) / 'process.json'))
            except BaseException:
                r.update(execution_status='COLLECTION_FAILURE', native_outcome='NOT_EVALUATED', traceback=traceback.format_exc())
            if r['execution_status'] != 'COMPLETED':
                stop = 'Stopped after infrastructure/identity/unresolved observation failure: ' + item['run_id']
        results.append(r)
        write_json_new(c['out'] / (item['run_id'] + '.result.json'), r)
        print(item['run_id'], item['cell'], r['execution_status'], r['native_outcome'], flush=True)
    after = runtime(c, original, lock)
    source_after = source(c, original)
    write_json_new(c['out'] / 'PRESERVATION_AFTER.json', dict(utc=now(), source=source_after,
        runtime_unchanged=after == before, runtime_files=len(before),
        changed_or_missing=[p for p,v in before.items() if after.get(p) != v], added=sorted(set(after)-set(before))))
    pids = [r['native_target_pid'] for r in results if 'native_target_pid' in r]
    passed = len(pids) == len(set(pids)) == 12 and after == before
    write_json_new(c['out'] / 'FORMAL_NATIVE_RESULT.json', dict(utc=now(), rank=c['rank'],
        status='COMPLETE_NATIVE_EVIDENCE' if passed else 'PARTIAL_NATIVE_EVIDENCE_HOLD',
        passed=passed, elapsed_seconds=time.monotonic()-started, fresh_target_pids=pids,
        rows=results, root_count=1, native_processes_completed=len(pids), methods_evaluated=False,
        independent_humans=0, production_runs=0))
    if not passed:
        raise ValueError('Formal native evidence incomplete; preserve every row')


def recheck(c):
    plan, original, modules = load_admitted(c)
    saved = read_json(c['out'] / 'FORMAL_NATIVE_RESULT.json')
    require(saved['passed'], 'Incomplete formal case')
    previous_pid = read_json(c['out'] / 'FORMAL_START.json')['pid']
    require(previous_pid != os.getpid(), 'Readback must be a new parent process')
    checked = []
    for item, row in zip(plan['cells'], saved['rows']):
        got = old_collect(c, original, modules, item, plan)
        require(got['execution_status'] == 'COMPLETED' and got['native_outcome'] == row['native_outcome'], 'Native readback changed')
        verify({row['raw_trace']: row['raw_trace_sha256'], row['method_input']: row['method_input_sha256'],
                row['process_record']: row['process_record_sha256']})
        raw = [loads(s) for s in Path(row['raw_trace']).read_text(encoding='utf-8').splitlines()]
        require(project(c['rank'], raw) == read_json(row['method_input']), 'Projection readback changed')
        checked.append(item['run_id'])
    write_json_new(c['out'] / 'FRESH_PARENT_READBACK.json', dict(utc=now(), passed=True,
        pid=os.getpid(), native_parent_pid=previous_pid, checked=checked, native_reruns=0, independent_human=False))
    print('Fresh process native/projection readback:', c['rank'], len(checked), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'run', 'recheck'])
    parser.add_argument('rank', type=int, choices=[79,94])
    args = parser.parse_args()
    globals()[args.mode](config(args.rank))
