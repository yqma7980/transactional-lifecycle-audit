"""Typed, read-only observation validation. No target imports or verdict labels."""
import json
import math


class CollectionFailure(ValueError):
    pass


class FixtureFailure(ValueError):
    pass


ATTRS = ('file_equal', 'name', 'url', 'storage', 'instance', 'field')
TOKENS = ('op_a', 'op_b')
FQN = 'm003_s10_celery5500_fixture.paramexception'
MESSAGE = 'Raise Custom Message'
RESERVED = {'case_id', 'run_id', 'cell', 'before_after', 'version_label',
            'history_label', 'native_outcome', 'expected_outcome', 'ground_truth',
            'expected_native_outcome', 'trigger_control', 'rank', 'original_rank',
            'history', 'cell_id', 'source_commit', 'expected', 'oracle', 'verdict',
            'pid', 'PID', 'execution_status', 'signature'}


def require(condition, message):
    if not condition:
        raise CollectionFailure(message)


def fixture(condition, message):
    if not condition:
        raise FixtureFailure(message)


def keys(value, required, optional=()):
    require(type(value) is dict, 'expected object')
    require(set(required) <= set(value) <= set(required) | set(optional),
            'missing/extra fields: ' + repr(sorted(value)))


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'expected non-bool integer')


def string(value):
    require(type(value) is str, 'expected string')


def strings(value):
    require(type(value) is list, 'expected string array')
    for item in value:
        string(item)


def numeric(value):
    require(type(value) is int or (type(value) is float and math.isfinite(value)), 'expected finite number')


def json_value(value, raw=False):
    if type(value) is dict:
        require(all(type(k) is str for k in value), 'non-string JSON key')
        require(not raw or not RESERVED.intersection(value), 'management label in raw trace')
        for item in value.values():
            json_value(item, raw)
    elif type(value) is list:
        for item in value:
            json_value(item, raw)
    elif type(value) is float:
        require(math.isfinite(value), 'nonfinite JSON number')
    else:
        require(value is None or type(value) in (str, int, bool), 'non-JSON observation')


def loads(text):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    def bad(value):
        raise CollectionFailure('nonfinite JSON constant: ' + value)
    try:
        result = json.loads(text, object_pairs_hook=pairs, parse_constant=bad)
    except (TypeError, json.JSONDecodeError) as exc:
        raise CollectionFailure('invalid JSON') from exc
    json_value(result)
    return result


def same(left, right):
    """JSON equality that never aliases bool, int and float."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(same(v, right[k]) for k, v in left.items())
    if type(left) is list:
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    return left == right


def envelope(events):
    require(type(events) is list and len(events) >= 2, 'missing trace')
    last = -1
    for index, row in enumerate(events):
        keys(row, ('seq', 'monotonic_ns', 'event', 'fields'))
        integer(row['seq'])
        integer(row['monotonic_ns'])
        require(row['seq'] == index + 1 and row['monotonic_ns'] >= last, 'invalid sequence/time')
        last = row['monotonic_ns']
        string(row['event'])
        require(type(row['fields']) is dict, 'invalid event payload')
        json_value(row['fields'], raw=True)
    require(events[0]['event'] == 'begin' and events[-1]['event'] == 'end', 'missing boundaries')
    require(events[0]['fields'] == events[-1]['fields'] == {}, 'invalid boundary payload')
    require(all(e['event'] not in ('begin', 'end') for e in events[1:-1]), 'duplicate boundaries')
    return events[1:-1]


def error_record(error, extra=()):
    keys(error, ('type_fqn', 'message', 'traceback') + tuple(extra))
    for value in error.values():
        string(value)
    require(bool(error['type_fqn']) and bool(error['traceback']), 'empty exception evidence')


def validate79_prefix(body):
    """Validate an interrupted native window without inventing a terminal or missing values."""
    names = ['FIXTURE_READY', 'REFERENCE_CAPTURED', 'SERIALIZE_ENTER', 'SERIALIZE_RETURN',
             'RESTORE_ENTER', 'RESTORE_RETURN', 'FILE_SELECTED'] + ['PROPERTY_CHECK:' + a for a in ATTRS]
    require(3 <= len(body) <= len(names) and [e['event'] for e in body] == names[:len(body)],
            'invalid interrupted Django event prefix')
    for row in body:
        name, fields = row['event'], row['fields']
        if name == 'FIXTURE_READY':
            keys(fields, ('pk', 'name'))
            integer(fields['pk'])
            fixture(fields == {'pk': 1, 'name': 'unused/test_file.py'}, 'invalid interrupted fixture')
        elif name == 'REFERENCE_CAPTURED':
            fixture(fields == {'name': 'unused/test_file.py', 'url': '/s10-media/unused/test_file.py'},
                    'invalid interrupted reference')
        elif name == 'SERIALIZE_ENTER':
            keys(fields, ('pickle_protocol',))
            integer(fields['pickle_protocol'])
            fixture(fields['pickle_protocol'] == 4, 'invalid interrupted pickle input')
        elif name == 'SERIALIZE_RETURN':
            keys(fields, ('bytes',))
            integer(fields['bytes'], 1)
        elif name in ('RESTORE_ENTER', 'RESTORE_RETURN'):
            require(fields == {}, 'invalid interrupted restore event')
        elif name == 'FILE_SELECTED':
            keys(fields, ('file_type',))
            string(fields['file_type'])
        else:
            keys(fields, ('status', 'equal', 'error'))
            require(fields['status'] in ('VALUE', 'ATTRIBUTE_ERROR'), 'invalid interrupted check status')
            if fields['status'] == 'VALUE':
                require(type(fields['equal']) is bool and fields['error'] is None, 'invalid interrupted equality')
            else:
                require(fields['equal'] is None, 'unavailable interrupted check must be null')
                error_record(fields['error'], ('observed_attribute',))
                require(fields['error']['observed_attribute'] == name.split(':', 1)[1], 'wrong interrupted check identity')


def validate79(body, state):
    names = ['FIXTURE_READY', 'REFERENCE_CAPTURED', 'SERIALIZE_ENTER', 'SERIALIZE_RETURN',
             'RESTORE_ENTER', 'RESTORE_RETURN', 'FILE_SELECTED']
    names += ['PROPERTY_CHECK:' + a for a in ATTRS] + ['TERMINAL_SNAPSHOT']
    require([e['event'] for e in body] == names, 'incomplete Django observation plan')
    fields = {e['event']: e['fields'] for e in body}
    keys(fields['FIXTURE_READY'], ('pk', 'name'))
    integer(fields['FIXTURE_READY']['pk'])
    string(fields['FIXTURE_READY']['name'])
    fixture(fields['FIXTURE_READY'] == {'pk': 1, 'name': 'unused/test_file.py'}, 'invalid file fixture')
    keys(fields['REFERENCE_CAPTURED'], ('name', 'url'))
    fixture(fields['REFERENCE_CAPTURED'] == {'name': 'unused/test_file.py',
                                            'url': '/s10-media/unused/test_file.py'}, 'invalid reference')
    keys(fields['SERIALIZE_ENTER'], ('pickle_protocol',))
    integer(fields['SERIALIZE_ENTER']['pickle_protocol'])
    fixture(fields['SERIALIZE_ENTER']['pickle_protocol'] == 4, 'invalid pickle input')
    keys(fields['SERIALIZE_RETURN'], ('bytes',))
    integer(fields['SERIALIZE_RETURN']['bytes'], 1)
    require(fields['RESTORE_ENTER'] == fields['RESTORE_RETURN'] == {}, 'invalid restore events')
    keys(fields['FILE_SELECTED'], ('file_type',))
    string(fields['FILE_SELECTED']['file_type'])
    keys(state, ('serialization_calls', 'restoration_calls', 'pickle_protocol', 'file_type',
                 'checks', 'witnesses', 'native_access_error_count', 'terminal'))
    for key in ('serialization_calls', 'restoration_calls', 'pickle_protocol', 'native_access_error_count'):
        integer(state[key])
    require(state['serialization_calls'] == state['restoration_calls'] == 1 and
            state['pickle_protocol'] == 4, 'roundtrip evidence disagreement')
    require(state['file_type'] == fields['FILE_SELECTED']['file_type'], 'file type disagreement')
    require(state['terminal'] == 'RESTORATION_AND_CHECKS_COMPLETE', 'invalid terminal marker')
    keys(state['checks'], ATTRS)
    witness_names = {'name': 'name', 'url': 'url', 'storage': 'storage_type',
                     'instance': 'instance_key', 'field': 'field_key'}
    needed = []
    errors = 0
    for attribute, check in state['checks'].items():
        keys(check, ('status', 'equal', 'error'))
        require(check['status'] in ('VALUE', 'ATTRIBUTE_ERROR'), 'invalid check status')
        if check['status'] == 'VALUE':
            require(type(check['equal']) is bool and check['error'] is None, 'invalid equality observation')
            if attribute in witness_names:
                needed.append(witness_names[attribute])
        else:
            require(check['equal'] is None, 'missing attribute is not false/zero')
            error_record(check['error'], ('observed_attribute',))
            require(check['error']['observed_attribute'] == attribute, 'wrong observed check')
            errors += 1
        require(same(check, fields['PROPERTY_CHECK:' + attribute]), 'check/terminal disagreement')
    require(state['native_access_error_count'] == errors, 'wrong access-error count')
    witnesses = state['witnesses']
    keys(witnesses, needed)
    for key in ('name', 'url', 'storage_type'):
        if key in witnesses:
            string(witnesses[key])
    if 'instance_key' in witnesses:
        keys(witnesses['instance_key'], ('model_label', 'pk'))
        string(witnesses['instance_key']['model_label'])
        integer(witnesses['instance_key']['pk'])
    if 'field_key' in witnesses:
        keys(witnesses['field_key'], ('model_label', 'name'))
        for value in witnesses['field_key'].values():
            string(value)
    return state


def validate80(body, state):
    names = [e['event'] for e in body]
    prefix = ['FIXTURE_CLASS_REGISTERED', 'LEGAL_CONSTRUCTOR_VALIDATED',
              'BACKEND_IDENTITY_CONFIRMED', 'DECODE_ENTER']
    require(len(names) == 7 and names[:4] == prefix and names[4] in ('DECODE_RETURN', 'DECODE_RAISE')
            and names[5:] == ['READ_RESULT_OR_EXCEPTION', 'TERMINAL_SNAPSHOT'], 'incomplete decode observation')
    f = [e['fields'] for e in body]
    keys(f[0], ('fixture_class_fqn', 'lookup_class_fqn'))
    fixture(f[0] == {'fixture_class_fqn': FQN, 'lookup_class_fqn': FQN}, 'invalid fixture class binding')
    keys(f[1], ('constructor_required_args',))
    integer(f[1]['constructor_required_args'])
    fixture(f[1]['constructor_required_args'] == 1, 'invalid constructor preflight')
    keys(f[2], ('serializer',))
    fixture(f[2]['serializer'] == 'json', 'invalid serializer preflight')
    keys(f[3], ('payload',))
    payload = f[3]['payload']
    keys(payload, ('exc_type', 'exc_module', 'exc_message'))
    strings(payload['exc_message'])
    fixture(payload['exc_type'] == 'TestParamException' and payload['exc_module'] == 'celery' and
            payload['exc_message'] in ([], [MESSAGE]), 'unregistered native input')
    keys(state, ('returned', 'result_type_fqn', 'result_message', 'result_args', 'result_param',
                 'escaping_exception', 'target_call_count', 'constructor_required_args',
                 'serialized_argument_count', 'serializer'), ('result_is_base_exception',))
    require(type(state['returned']) is bool, 'returned must be bool')
    for key in ('target_call_count', 'constructor_required_args', 'serialized_argument_count'):
        integer(state[key])
    require(state['target_call_count'] == 1 and state['constructor_required_args'] == 1 and
            state['serialized_argument_count'] == len(payload['exc_message']) and state['serializer'] == 'json',
            'input/terminal disagreement')
    keys(f[4], ('type_fqn',))
    string(f[4]['type_fqn'])
    if state['returned']:
        require(names[4] == 'DECODE_RETURN', 'return/raise disagreement')
        require(type(state.get('result_is_base_exception')) is bool, 'missing BaseException observation')
        string(state['result_type_fqn'])
        string(state['result_message'])
        keys(state['result_args'], ('python_container_type', 'items'))
        require(state['result_args']['python_container_type'] == 'tuple', 'args container lost')
        strings(state['result_args']['items'])
        require(type(state['result_param']) is str or state['result_param'] == {'status': 'ABSENT'},
                'invalid param observation')
        require(state['escaping_exception'] is None and f[4]['type_fqn'] == state['result_type_fqn'],
                'contradictory return evidence')
    else:
        require(names[4] == 'DECODE_RAISE', 'raise/return disagreement')
        require(all(state[k] is None for k in ('result_type_fqn', 'result_message', 'result_args', 'result_param')),
                'fabricated result on exception')
        require(state.get('result_is_base_exception') is None, 'fabricated BaseException result')
        error_record(state['escaping_exception'], ('phase',))
        require(f[4]['type_fqn'] == state['escaping_exception']['type_fqn'], 'exception identity disagreement')
    require(same(f[5], state), 'result/terminal disagreement')
    result = dict(state, payload=payload, fixture_class_fqn=f[0]['fixture_class_fqn'])
    # This nullable field is omitted by the frozen no-return recipe, not observed as a result.
    result.setdefault('result_is_base_exception', None)
    return result


def validate94(body, state):
    validate94_prefix(body[:-1], require_closed=True)
    names = [e['event'] for e in body]
    require(names[:4] == ['CALL_SOON:op_a', 'CALL_SOON:op_b', 'PENDING_SNAPSHOT:2', 'SYNLOOP_ENTER'],
            'missing enqueue/window boundary')
    require(body[0]['fields'] == body[1]['fields'] == body[3]['fields'] == {}, 'invalid enqueue payload')
    keys(body[2]['fields'], ('pending_ids',))
    fixture(body[2]['fields']['pending_ids'] == list(TOKENS), 'invalid initial queue')
    keys(state, ('pending_before', 'pending_after', 'pending_ids_before', 'pending_ids_after',
                 'callback_receipts', 'callback_counts', 'callback_enter_return_balance',
                 'unexpected_callback_exceptions', 'native_perform_calls', 'maybe_shutdown_calls',
                 'maybe_shutdown_outcome', 'drain_events_calls', 'drain_timeout_seconds',
                 'consume_calls', 'on_ready_calls', 'native_exit', 'system_exit_code'))
    for key in ('pending_before', 'pending_after', 'native_perform_calls', 'maybe_shutdown_calls',
                'drain_events_calls', 'consume_calls', 'on_ready_calls'):
        integer(state[key])
    for key in ('pending_ids_before', 'pending_ids_after', 'callback_receipts'):
        strings(state[key])
        require(all(x in TOKENS for x in state[key]), 'unknown callback ID')
    require(state['pending_ids_before'] == body[2]['fields']['pending_ids'] and state['pending_before'] == 2
            and state['pending_after'] == len(state['pending_ids_after']), 'queue snapshot disagreement')
    keys(state['callback_counts'], TOKENS)
    keys(state['callback_enter_return_balance'], TOKENS)
    for token in TOKENS:
        integer(state['callback_counts'][token])
        pair = state['callback_enter_return_balance'][token]
        require(type(pair) is list and len(pair) == 2, 'invalid callback balance')
        for count in pair:
            integer(count)
    require(type(state['unexpected_callback_exceptions']) is list, 'invalid callback errors')
    require(not state['unexpected_callback_exceptions'], 'record-only callback/emit failed, possibly swallowed by native code')
    require(type(state['drain_timeout_seconds']) is list, 'missing timeout list')
    for timeout in state['drain_timeout_seconds']:
        numeric(timeout)
    require(state['maybe_shutdown_outcome'] in (None, 'RETURN_NONE', 'RAISE_SYSTEM_EXIT'), 'invalid shutdown outcome')
    require(state['native_exit'] in ('RETURN_NONE', 'SYSTEM_EXIT'), 'invalid native exit')
    if state['native_exit'] == 'SYSTEM_EXIT':
        require(type(state['system_exit_code']) is int, 'SystemExit code must be integer, not bool')
    else:
        require(state['system_exit_code'] is None, 'normal exit code must be null')
    enters, returns, drains, shutdown = [], [], [], []
    calls = {'TASK_CONSUMER_CONSUME': 0, 'ON_READY': 0, 'NATIVE_PERFORM_ENTER': 0}
    active = []
    profile_depth = 0
    exit_events = []
    for row in body[4:-1]:
        name, fields = row['event'], row['fields']
        if name.startswith('CALLBACK_ENTER:') or name.startswith('CALLBACK_RETURN:'):
            require(profile_depth == 1, 'callback outside native perform window')
            require(fields == {}, 'invalid callback payload')
            token = name.split(':', 1)[1]
            require(token in TOKENS, 'unknown callback event')
            if name.startswith('CALLBACK_ENTER:'):
                enters.append(token)
                active.append(token)
            else:
                require(active and active.pop() == token, 'unpaired callback return')
                returns.append(token)
        elif name == 'DRAIN_EVENTS':
            require(profile_depth == 0 and not active, 'drain inside unfinished native perform/callback')
            keys(fields, ('timeout_seconds',))
            numeric(fields['timeout_seconds'])
            drains.append(fields['timeout_seconds'])
        elif name in ('MAYBE_SHUTDOWN_RETURN', 'MAYBE_SHUTDOWN_RAISE'):
            if name.endswith('RAISE'):
                keys(fields, ('type_fqn', 'code'))
                require(type(fields['code']) is int, 'invalid injected exit code')
                fixture(fields == {'type_fqn': 'builtins.SystemExit', 'code': 0}, 'invalid shutdown boundary')
                shutdown.append('RAISE_SYSTEM_EXIT')
            else:
                require(fields == {}, 'invalid shutdown return')
                shutdown.append('RETURN_NONE')
        elif name in ('SYNLOOP_RETURN', 'SYNLOOP_SYSTEM_EXIT'):
            if name == 'SYNLOOP_SYSTEM_EXIT':
                keys(fields, ('code',))
                require(type(fields['code']) is int, 'invalid observed exit code')
                exit_events.append(('SYSTEM_EXIT', fields['code']))
            else:
                require(fields == {}, 'invalid return payload')
                exit_events.append(('RETURN_NONE', None))
        else:
            require(name in ('TASK_HANDLER_CREATED', 'TASK_CONSUMER_CONSUME', 'ON_READY',
                             'NATIVE_PERFORM_ENTER', 'NATIVE_PERFORM_RETURN'), 'unknown loop observation')
            require(fields == {}, 'invalid loop payload')
            if name in calls:
                calls[name] += 1
            if name == 'NATIVE_PERFORM_ENTER':
                require(profile_depth == 0 and not active, 'nested native perform event')
                profile_depth += 1
            if name == 'NATIVE_PERFORM_RETURN':
                require(not active, 'native perform returned before callback returned')
                profile_depth -= 1
                require(profile_depth >= 0, 'unpaired profile return')
        require(not exit_events or row is body[-2], 'event after native exit/window end')
    require(not active and profile_depth == 0, 'incomplete callback/profile capture')
    require(exit_events == [(state['native_exit'], state['system_exit_code'])], 'exit snapshot disagreement')
    require(state['callback_receipts'] == enters == returns, 'receipt/event disagreement')
    for token in TOKENS:
        require(state['callback_counts'][token] == enters.count(token) and
                state['callback_enter_return_balance'][token] == [enters.count(token), returns.count(token)],
                'callback count disagreement')
    require(state['native_perform_calls'] == calls['NATIVE_PERFORM_ENTER'] and
            state['consume_calls'] == calls['TASK_CONSUMER_CONSUME'] and state['on_ready_calls'] == calls['ON_READY'],
            'native call count disagreement')
    require(state['maybe_shutdown_calls'] == len(shutdown) and
            state['maybe_shutdown_outcome'] == (shutdown[-1] if shutdown else None), 'shutdown count disagreement')
    require(state['drain_events_calls'] == len(drains) and same(state['drain_timeout_seconds'], drains),
            'drain snapshot disagreement')
    return state


def validate(rank, events):
    body = envelope(events)
    require(body and body[-1]['event'] == 'TERMINAL_SNAPSHOT', 'missing terminal observation')
    require(sum(e['event'] == 'TERMINAL_SNAPSHOT' for e in body) == 1, 'duplicate terminal')
    require(type(rank) is int and rank in (79, 80, 94), 'unsupported rank')
    return {79: validate79, 80: validate80, 94: validate94}[rank](body, body[-1]['fields'])


def validate80_prefix(body):
    require(4 <= len(body) <= 5, 'invalid interrupted decode prefix length')
    names = ['FIXTURE_CLASS_REGISTERED', 'LEGAL_CONSTRUCTOR_VALIDATED',
             'BACKEND_IDENTITY_CONFIRMED', 'DECODE_ENTER']
    require([r['event'] for r in body[:4]] == names, 'invalid interrupted decode prefix')
    f = [r['fields'] for r in body]
    keys(f[0], ('fixture_class_fqn', 'lookup_class_fqn'))
    fixture(f[0] == {'fixture_class_fqn': FQN, 'lookup_class_fqn': FQN}, 'invalid interrupted class')
    keys(f[1], ('constructor_required_args',))
    integer(f[1]['constructor_required_args'])
    fixture(f[1]['constructor_required_args'] == 1, 'invalid interrupted constructor')
    keys(f[2], ('serializer',))
    fixture(f[2]['serializer'] == 'json', 'invalid interrupted backend')
    keys(f[3], ('payload',))
    keys(f[3]['payload'], ('exc_type', 'exc_module', 'exc_message'))
    p = f[3]['payload']
    strings(p['exc_message'])
    fixture(p['exc_type'] == 'TestParamException' and p['exc_module'] == 'celery' and
            p['exc_message'] in ([], [MESSAGE]), 'invalid interrupted payload')
    if len(body) == 5:
        require(body[4]['event'] in ('DECODE_RETURN', 'DECODE_RAISE'), 'invalid interrupted result event')
        keys(f[4], ('type_fqn',))
        string(f[4]['type_fqn'])


def validate94_prefix(body, require_closed=False):
    """Version-blind causal grammar, including a possibly interrupted native window."""
    prefix = ['CALL_SOON:op_a', 'CALL_SOON:op_b', 'PENDING_SNAPSHOT:2', 'SYNLOOP_ENTER',
              'TASK_HANDLER_CREATED', 'TASK_CONSUMER_CONSUME', 'ON_READY']
    require(len(body) >= 4, 'incomplete enqueue/native entry evidence')
    count = min(len(body), len(prefix))
    require([r['event'] for r in body[:count]] == prefix[:count], 'invalid sync-loop setup order')
    for i, row in enumerate(body[:count]):
        if i == 2:
            keys(row['fields'], ('pending_ids',))
            strings(row['fields']['pending_ids'])
            fixture(row['fields']['pending_ids'] == list(TOKENS), 'invalid initial queue')
        else:
            require(row['fields'] == {}, 'invalid setup boundary payload')
    depth, active, exited = 0, None, False
    for row in body[len(prefix):]:
        name, fields = row['event'], row['fields']
        require(not exited, 'event after native window exit')
        if name == 'NATIVE_PERFORM_ENTER':
            require(fields == {} and depth == 0 and active is None, 'invalid perform entry')
            depth = 1
        elif name == 'NATIVE_PERFORM_RETURN':
            require(fields == {} and depth == 1 and active is None, 'invalid perform return')
            depth = 0
        elif name.startswith('CALLBACK_ENTER:'):
            token = name.split(':', 1)[1]
            require(fields == {} and token in TOKENS and depth == 1 and active is None,
                    'callback not caused within native perform window')
            active = token
        elif name.startswith('CALLBACK_RETURN:'):
            token = name.split(':', 1)[1]
            require(fields == {} and depth == 1 and active == token, 'unpaired callback return')
            active = None
        elif name == 'DRAIN_EVENTS':
            require(depth == 0 and active is None, 'drain during native perform')
            keys(fields, ('timeout_seconds',))
            numeric(fields['timeout_seconds'])
        elif name in ('MAYBE_SHUTDOWN_RETURN', 'MAYBE_SHUTDOWN_RAISE'):
            require(depth == 0 and active is None, 'shutdown inside callback')
            if name.endswith('RETURN'):
                require(fields == {}, 'invalid shutdown return payload')
            else:
                keys(fields, ('type_fqn', 'code'))
                integer(fields['code'])
                fixture(fields == {'type_fqn': 'builtins.SystemExit', 'code': 0}, 'wrong shutdown input')
        elif name in ('SYNLOOP_RETURN', 'SYNLOOP_SYSTEM_EXIT'):
            require(depth == 0 and active is None, 'native exit during active callback')
            if name.endswith('RETURN'):
                require(fields == {}, 'invalid synloop return')
            else:
                keys(fields, ('code',))
                require(type(fields['code']) is int, 'exit code must be integer')
            exited = True
        else:
            raise CollectionFailure('unknown or misplaced sync-loop event: ' + name)
    if require_closed:
        require(exited and depth == 0 and active is None, 'incomplete sync-loop capture')
