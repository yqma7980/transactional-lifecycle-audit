"""Capture integrity with an explicit, protocol-bound sequence origin."""
import math
from pathlib import Path
from kit_io import loads, read_json, sha256

RESERVED = {'case_id', 'run_id', 'cell', 'before_after', 'version_label', 'history_label',
            'native_outcome', 'expected_native_outcome', 'expected_outcome', 'ground_truth',
            'trigger_control'}

def no_management_labels(value):
    if isinstance(value, dict):
        if RESERVED.intersection(value):
            raise ValueError('management labels in raw observation')
        for v in value.values():
            no_management_labels(v)
    elif isinstance(value, list):
        for v in value:
            no_management_labels(v)

def finite(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError('nonfinite numeric field')
    if isinstance(value, dict):
        for v in value.values():
            finite(v)
    if isinstance(value, list):
        for v in value:
            finite(v)

def validate_trace(text, expected_count, sequence_start):
    if type(sequence_start) is not int or sequence_start not in (0, 1):
        raise ValueError('missing or invalid frozen sequence origin')
    if type(expected_count) is not int:
        raise ValueError('invalid expected event count')
    if not text.endswith('\n'):
        raise ValueError('unterminated/truncated trace')
    events = [loads(line) for line in text.splitlines()]
    if len(events) != expected_count or len(events) < 2:
        raise ValueError('event count mismatch')
    last_time = -1
    for seq, row in enumerate(events, start=sequence_start):
        if set(row) != {'seq', 'monotonic_ns', 'event', 'fields'}:
            raise ValueError('unexpected raw-trace schema or management-label leakage')
        if type(row['seq']) is not int or row['seq'] != seq:
            raise ValueError('missing/duplicate/out-of-order sequence')
        stamp = row['monotonic_ns']
        if type(stamp) is not int or stamp < 0 or stamp < last_time:
            raise ValueError('invalid monotonic timestamp')
        last_time = stamp
        if not isinstance(row['event'], str) or not isinstance(row['fields'], dict):
            raise ValueError('invalid event/fields')
        finite(row)
        no_management_labels(row['fields'])
    if events[0]['event'] != 'begin' or events[-1]['event'] != 'end':
        raise ValueError('missing boundary events')
    return events

def validate_native(folder, process, expected):
    folder = Path(folder).resolve()
    run = Path(expected['run_directory']).resolve()
    if folder != run / 'work' / 'native' or Path(process['run_directory']).resolve() != run:
        raise ValueError('foreign native/log directory')
    if process['run_id'] != expected['run_id'] or process['argv'][0] != expected['executable']:
        raise ValueError('process run or executable mismatch')
    if process != read_json(run / 'process.json'):
        raise ValueError('process record not identical to saved evidence')
    request = read_json(run / 'request.json')
    if any(process[k] != v for k, v in request.items()):
        raise ValueError('process/request divergence')
    if process['cwd'] != str(run / 'work') or request['argv'] != expected['argv']:
        raise ValueError('unexpected invocation or working directory')
    start = read_json(run / 'target_start.json')
    footer = read_json(run / 'target_exit.json')
    for record in (start, footer, process['target_result']):
        if type(record.get('pid')) is not int or record['pid'] <= 0:
            raise ValueError('launcher/footer PID must be a positive integer')
    if (footer != process['target_result'] or start['pid'] != footer['pid'] or
        start['argv'] != request['argv'] or start['cwd'] != request['cwd']):
        raise ValueError('launcher start/footer divergence')
    if process['target_executable_sha256'] != sha256(expected['executable']):
        raise ValueError('executable drift')
    if process['status'] != 'COMPLETED' or process['exit_code'] != 0 or process['cleanup_errors']:
        raise ValueError('process not cleanly completed')
    if any(x.get('truncated') or x.get('error') for x in process['streams'].values()):
        raise ValueError('stream failure')
    for stream in ['stdout', 'stderr']:
        stats = process['streams'][stream]
        if (type(stats.get('observed_bytes')) is not int or type(stats.get('saved_bytes')) is not int or
            not 0 <= stats['observed_bytes'] == stats['saved_bytes'] <= process['max_log_bytes_per_stream']):
            raise ValueError('incomplete or invalid stream byte count')
        log = Path(process['run_directory']) / (stream + '.log')
        if (sha256(log) != process['artifacts'][stream]['sha256'] or
                log.stat().st_size != process['streams'][stream]['saved_bytes']):
            raise ValueError('missing or altered captured stream: '+stream)
    ident = read_json(folder / 'identity.json')
    for key in ['case_id', 'run_id', 'cell', 'executable', 'source_commit', 'python_version',
                'package_version', 'protocol_sha256', 'environment_lock_sha256']:
        if ident[key] != expected[key]:
            raise ValueError('identity mismatch: ' + key)
    if type(ident.get('pid')) is not int or ident['pid'] <= 0:
        raise ValueError('native PID must be a positive integer')
    if ident['pid'] != process['target_result']['pid']:
        raise ValueError('PID mismatch')
    if not ident.get('python_version') or not ident.get('package_version'):
        raise ValueError('missing runtime version')
    if ident['source_files'] != expected['source_files']:
        raise ValueError('wrong source file identity')
    for filename, digest in ident['source_files'].items():
        if sha256(filename) != digest:
            raise ValueError('source drift')
    if ident['module_files'] != expected['module_files']:
        raise ValueError('missing, extra or mismatched native module')
    for name, filepath in ident['module_files'].items():
        if filepath not in expected['source_files']:
            raise ValueError('unbound imported module: ' + name)
    if not ident['module_files']:
        raise ValueError('no native module imported')
    manifest = read_json(folder / 'trace_manifest.json')
    raw = folder / 'raw_trace.jsonl'
    if sha256(raw) != manifest['sha256']:
        raise ValueError('trace checksum mismatch')
    events = validate_trace(raw.read_text(encoding='utf-8'), manifest['events'],
                            expected['sequence_start'])
    orders = expected.get('allowed_event_orders', [expected.get('event_order')])
    if [x['event'] for x in events] not in orders:
        raise ValueError('required observation plan incomplete or changed')
    oracle = read_json(folder / 'native_oracle.json')
    finite(oracle)
    if type(oracle.get('events')) is not int or oracle['events'] < 2:
        raise ValueError('oracle event count must be an integer >= 2')
    for k in ['case_id','run_id','cell','protocol_sha256']:
        if oracle[k] != expected[k]:
            raise ValueError('oracle not bound to current case/run/protocol')
    if oracle['raw_trace_sha256'] != manifest['sha256'] or oracle['events'] != len(events):
        raise ValueError('oracle not bound to complete current trace')
    if oracle['evaluator_sha256'] != expected['evaluator_sha256']:
        raise ValueError('unexpected native evaluator')
    if oracle['native_outcome'] not in ['SATISFIED', 'VIOLATED', 'UNRESOLVED']:
        raise ValueError('invalid native outcome')
    return dict(execution_status='COMPLETED', native_outcome=oracle['native_outcome'],
                pid=ident['pid'], events=len(events), raw_sha256=manifest['sha256'],
                evidence_layer='ADAPTED_UPSTREAM_NATIVE_PROPERTY_NOT_FORMAL_METHOD_COMPARISON')
