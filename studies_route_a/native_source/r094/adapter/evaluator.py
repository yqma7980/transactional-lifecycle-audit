"""Version-blind properties and separate frozen signatures; no target imports."""
import re
from pathlib import Path

from observations import (ATTRS, FQN, MESSAGE, CollectionFailure, FixtureFailure,
                          envelope, error_record, require, same, validate, validate79_prefix, validate80_prefix, validate94_prefix)


FRAME = re.compile(r'^  File "([^"\r\n]+)", line ([1-9][0-9]*), in ([^\r\n]+)$', re.MULTILINE)
MISSING = re.compile(r"^'FieldFile' object has no attribute '(storage|instance|field)'$")


def traceback_frames(text):
    # Chained exceptions require review rather than mixing frames from separate failures.
    if text.count('Traceback (most recent call last):') != 1:
        return []
    return [{'filename': str(Path(path).resolve()), 'lineno': int(line), 'function': function}
            for path, line, function in FRAME.findall(text)]


def at(frame, site):
    return (frame['filename'] == site['filename'] and frame['lineno'] == site['lineno'] and
            frame['function'] == site['function'])


def origin79(attribute, error, sites):
    if error['type_fqn'] != 'builtins.AttributeError' or error['observed_attribute'] != attribute:
        return False
    match = MISSING.fullmatch(error['message'])
    member = 'storage' if attribute == 'url' else attribute
    if match is None or match.group(1) != member:
        return False
    frames = traceback_frames(error['traceback'])
    ids = ['r79_restored_getattr', 'r79_url_storage'] if attribute == 'url' else ['r79_restored_getattr']
    return len(frames) == len(ids) and all(key in sites and at(frame, sites[key]) for frame, key in zip(frames, ids))


def origin80(state, sites):
    error = state['escaping_exception']
    if (state['serialized_argument_count'] != 0 or error['type_fqn'] != 'builtins.TypeError' or
            error['phase'] != 'NATIVE_CALL_REQUIRES_ORIGIN_REVIEW'):
        return False
    frames = traceback_frames(error['traceback'])
    ids = ['r80_recipe_call', 'r80_constructor']
    return len(frames) == 2 and all(key in sites and at(frame, sites[key]) for frame, key in zip(frames, ids))


def result(status, outcome, reason, **extra):
    return dict(execution_status=status, native_outcome=outcome, reason=reason, **extra)


def evaluate(rank, events, callsite_ids):
    """callsite_ids must come from the driver's verified identity, never a raw event."""
    try:
        state = validate(rank, events)
    except CollectionFailure as exc:
        return result('COLLECTION_FAILURE', 'NOT_EVALUATED', str(exc))
    except FixtureFailure as exc:
        return result('ENVIRONMENT_FAILURE', 'NOT_EVALUATED', str(exc), fixture_invalid=True)
    declared_violation = False
    satisfied_signature = False
    if rank == 79:
        checks = state['checks']
        satisfied = all(c['status'] == 'VALUE' and c['equal'] is True for c in checks.values())
        known_errors = all(c['status'] == 'VALUE' or origin79(a, c['error'], callsite_ids)
                           for a, c in checks.items())
        outcome = 'SATISFIED' if satisfied else ('VIOLATED' if known_errors else 'UNRESOLVED')
        witnesses = state['witnesses']
        base = (state['file_type'] == 'django.db.models.fields.files.FieldFile' and
                witnesses.get('name') == 'unused/test_file.py')
        expected_witnesses = {
            'name': 'unused/test_file.py', 'url': '/s10-media/unused/test_file.py',
            'instance_key': {'model_label': 'm003_s10_django_fixture.Document', 'pk': 1},
            'field_key': {'model_label': 'm003_s10_django_fixture.Document', 'name': 'myfile'}}
        satisfied_signature = (base and satisfied and
            all(same(witnesses.get(k), v) for k, v in expected_witnesses.items()))
        # Preserve the wrapper's raw type; the configured backend is separate identity metadata.
        state = dict(state, storage_identity=(
            {'type_fqn': witnesses['storage_type'], 'within_cell_equal': checks['storage']['equal']}
            if checks['storage']['status'] == 'VALUE' else {'status': 'UNAVAILABLE', 'reason': 'ATTRIBUTE_ERROR'}))
        for key, witness in (('name', 'name'), ('url', 'url'),
                             ('instance_identity', 'instance_key'), ('field_identity', 'field_key')):
            state[key] = witnesses[witness] if witness in witnesses else {'status': 'UNAVAILABLE', 'reason': 'ATTRIBUTE_ERROR'}
        declared_violation = (base and known_errors and state['native_access_error_count'] == 4 and
            all(checks[a]['status'] == 'VALUE' and checks[a]['equal'] is True for a in ('file_equal', 'name')) and
            all(checks[a]['status'] == 'ATTRIBUTE_ERROR' for a in ('url', 'storage', 'instance', 'field')))
        reason = 'Same six native association comparisons; exact missing-member origins reviewed separately.'
    elif rank == 80:
        if not state['returned']:
            declared_violation = origin80(state, callsite_ids)
            outcome = 'VIOLATED' if declared_violation else 'UNRESOLVED'
        else:
            if state['serialized_argument_count'] == 1:
                expected_type, message, param = FQN, MESSAGE, MESSAGE
            else:
                expected_type = 'builtins.Exception'
                message = "<class 'm003_s10_celery5500_fixture.paramexception'>([])"
                param = {'status': 'ABSENT'}
            satisfied_signature = (state['result_is_base_exception'] is True and
                state['result_type_fqn'] == expected_type and state['result_message'] == message and
                same(state['result_param'], param) and state['escaping_exception'] is None and
                state['result_args'] == {'python_container_type': 'tuple', 'items': [message]})
            outcome = 'SATISFIED' if satisfied_signature else 'VIOLATED'
        reason = 'Same usable-exception contract, selected only by the recorded legal or mismatched payload.'
    else:
        satisfied = (state['pending_after'] == 0 and state['pending_ids_after'] == [] and
                     state['callback_receipts'] == ['op_b', 'op_a'] and
                     state['callback_counts'] == {'op_a': 1, 'op_b': 1} and
                     state['callback_enter_return_balance'] == {'op_a': [1, 1], 'op_b': [1, 1]})
        outcome = 'SATISFIED' if satisfied else 'VIOLATED'
        boundary = state['maybe_shutdown_outcome']
        exit_matches = ((boundary == 'RETURN_NONE' and state['native_exit'] == 'RETURN_NONE' and
                         state['system_exit_code'] is None) or
                        (boundary == 'RAISE_SYSTEM_EXIT' and state['native_exit'] == 'SYSTEM_EXIT' and
                         state['system_exit_code'] == 0))
        common = (state['maybe_shutdown_calls'] == state['consume_calls'] == state['on_ready_calls'] == 1 and exit_matches)
        satisfied_signature = (satisfied and common and state['native_perform_calls'] == state['drain_events_calls'] == 1 and
                               state['drain_timeout_seconds'] in ([2], [2.0]))
        declared_violation = (common and boundary == 'RAISE_SYSTEM_EXIT' and state['pending_after'] == 2 and
            state['pending_ids_after'] == ['op_a', 'op_b'] and not state['callback_receipts'] and
            state['native_perform_calls'] == state['drain_events_calls'] == 0 and state['drain_timeout_seconds'] == [])
        reason = 'Actual callback receipts, not empty-queue check count, define the shared property.'
    return result('COMPLETED', outcome, reason, observations=state,
                  signature={'satisfied': bool(satisfied_signature), 'declared_violation': bool(declared_violation)})


def evaluate_failure(rank, events, failure):
    """An intact exception envelope is not a fabricated successful terminal snapshot."""
    try:
        require(type(rank) is int and rank in (79, 80, 94), 'unsupported rank type')
        body = envelope(events)
        require(not any(e['event'] == 'TERMINAL_SNAPSHOT' for e in body), 'failure after terminal/cleanup')
        if rank == 79:
            validate79_prefix(body)
        elif rank == 80:
            validate80_prefix(body)
        elif rank == 94:
            validate94_prefix(body)
        start = {79: 'SERIALIZE_ENTER', 80: 'DECODE_ENTER', 94: 'SYNLOOP_ENTER'}[rank]
        require(any(e['event'] == start for e in body), 'native window never entered')
        require(failure['phase'] == 'NATIVE_WINDOW' and failure['capture_intact'] is True, 'invalid failure envelope')
        require(failure['last_event'] == body[-1]['event'], 'failure/trace phase disagreement')
        error_record({k: failure['exception'][k] for k in ('type_fqn', 'message', 'traceback')})
        text = failure['exception']['traceback']
        marker = 'Traceback (most recent call last):'
        last_trace = marker + text.rsplit(marker, 1)[-1] if marker in text else text
        require(same(failure['exception']['frames'], traceback_frames(last_trace)),
                'failure traceback frame disagreement')
        require(bool(failure['exception']['frames']), 'missing exception frames')
    except (CollectionFailure, KeyError, TypeError) as exc:
        return result('COLLECTION_FAILURE', 'NOT_EVALUATED', str(exc))
    except FixtureFailure as exc:
        return result('ENVIRONMENT_FAILURE', 'NOT_EVALUATED', str(exc), fixture_invalid=True)
    return result('COMPLETED', 'UNRESOLVED', 'Unexpected native-window exception; origin requires review.',
                  failure_envelope=failure, signature={'satisfied': False, 'declared_violation': False})


def qualify_four_cells(cells):
    """Administrative aggregation only; version labels never enter evaluate()."""
    names = ('before-control', 'after-control', 'before-trigger', 'after-trigger')
    if set(cells) != set(names):
        return 'COLLECTION_HOLD'
    for status, hold in (('SOURCE_IDENTITY_FAILURE', 'SOURCE_IDENTITY_HOLD'),
                         ('COLLECTION_FAILURE', 'COLLECTION_HOLD'),
                         ('ENVIRONMENT_FAILURE', 'ENVIRONMENT_HOLD'), ('TIMEOUT', 'ENVIRONMENT_HOLD'),
                         ('NOT_RUN', 'PROTOCOL_HOLD')):
        if any(c['execution_status'] == status for c in cells.values()):
            return hold
    if not all(c['execution_status'] == 'COMPLETED' for c in cells.values()):
        return 'COLLECTION_HOLD'
    closed = all(cells[k]['native_outcome'] == 'SATISFIED' and
                 cells[k].get('signature', {}).get('satisfied') is True
                 for k in ('before-control', 'after-control', 'after-trigger'))
    closed = closed and cells['before-trigger']['native_outcome'] == 'VIOLATED' and \
        cells['before-trigger'].get('signature', {}).get('declared_violation') is True
    return 'NATIVE_FIXED_PAIR_VERIFIED' if closed else 'NATIVE_CONTRAST_NOT_ESTABLISHED'


def require_process_identity(identity, supervisor_pid, footer_pid):
    """Parent calls after process exit; never accept a launcher/child PID set."""
    for value in (identity.get('pid'), supervisor_pid, footer_pid):
        require(type(value) is int and value > 0, 'PID must be positive integer, not bool/string')
    require(identity['pid'] == supervisor_pid == footer_pid, 'supervisor/native/footer PID mismatch')
    return True
