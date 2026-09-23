"""Whitelist raw measurements only, after an external native provenance gate.

No version, cell, source identity, oracle verdict, or error stack enters either arm.
"""
import copy

ATTRS79 = ('file_equal', 'name', 'url', 'storage', 'instance', 'field')
FIELDS94 = ('pending_after', 'pending_ids_after', 'callback_receipts',
            'callback_counts', 'callback_enter_return_balance')


def json_depth(value):
    pending, deepest = [(value, 0)], 0
    while pending:
        item, level = pending.pop()
        deepest = max(deepest, level)
        if deepest > 4:
            return deepest
        if type(item) is dict:
            pending.extend((v, level + 1) for v in item.values())
        elif type(item) is list:
            pending.extend((v, level + 1) for v in item)
    return deepest


def context(rank):
    if rank == 79:
        return dict(protocol_id='G4-ASSOCIATION-RESTORE-1',
            observation_point='post_restore_property_window', observation_order=list(ATTRS79))
    if rank == 94:
        return dict(protocol_id='G4-PENDING-CALLBACK-1',
            observation_point='immediate_native_exit_before_cleanup', observation_order=list(FIELDS94))
    raise ValueError('unregistered projection')


def project(rank, events):
    if type(events) is not list:
        raise ValueError('raw events must be a list')
    if rank == 79:
        checks = {}
        for attr in ATTRS79:
            matches = [e for e in events if e.get('event') == 'PROPERTY_CHECK:' + attr]
            if len(matches) != 1:
                raise ValueError('missing or duplicate raw property window: ' + attr)
            f = matches[0]['fields']
            checks[attr] = {k: copy.deepcopy(f[k]) for k in ('status', 'equal')}
        samples = dict(checks=checks)
    elif rank == 94:
        matches = [e for e in events if e.get('event') == 'TERMINAL_SNAPSHOT']
        if len(matches) != 1:
            raise ValueError('missing or duplicate raw terminal window')
        samples = {k: copy.deepcopy(matches[0]['fields'][k]) for k in FIELDS94}
    else:
        raise ValueError('unregistered projection')
    trace = dict(context=context(rank), samples=samples)
    # These two registered native grammars contain only scalars at depth four.
    # This is a cohort-shape assertion, not an imposed limit on the rich baseline.
    if json_depth(trace) > 4:
        raise ValueError('native whitelist projection exceeded its declared shallow shape')
    return trace
