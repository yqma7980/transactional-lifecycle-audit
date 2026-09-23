"""Declarative case data using the already-frozen generic interpreter unchanged."""
import sys
import math
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'core'))
import frozen_core
from projection import context, ATTRS79, FIELDS94


def validate_transport(trace):
    if type(trace) is not dict or set(trace) != {'context', 'samples'}:
        raise ValueError('wire trace must be a plain object with context and samples')
    pending = [(trace, ())]
    while pending:
        value, ancestors = pending.pop()
        kind = type(value)
        if value is None or kind is str or kind is int or kind is bool:
            continue
        if kind is float:
            if not math.isfinite(value):
                raise ValueError('nonfinite transport scalar')
        elif kind is list or kind is dict:
            identity = id(value)
            if identity in ancestors:
                raise ValueError('cyclic transport object')
            if kind is dict and any(type(k) is not str for k in value):
                raise ValueError('transport object keys must be plain strings')
            children = value.values() if kind is dict else value
            pending.extend((child, ancestors + (identity,)) for child in children)
        else:
            raise ValueError('not a plain JSON transport value')


def contract(rank):
    eligible = [dict(id=name, left=dict(path=['context', key]), right=dict(literal=value))
        for name, (key, value) in zip(('protocol_matches', 'point_matches', 'order_matches'), context(rank).items())]
    if rank == 79:
        relations = [dict(id='restored_' + attr, obligation='O3',
            left=dict(path=['samples', 'checks', attr]),
            right=dict(literal=dict(status='VALUE', equal=True))) for attr in ATTRS79]
    elif rank == 94:
        names = ('pending_count_empty', 'pending_ids_empty', 'receipt_order', 'callback_once', 'callback_balanced')
        literals = (0, [], ['op_b', 'op_a'], {'op_a': 1, 'op_b': 1}, {'op_a': [1, 1], 'op_b': [1, 1]})
        relations = [dict(id=name, obligation='O5', left=dict(path=['samples', key]),
            right=dict(literal=value)) for name, key, value in zip(names, FIELDS94, literals)]
    else:
        raise ValueError('unregistered contract')
    return dict(schema='S06-EQUALITY-1', eligibility=eligible, relations=relations)


def normalized_evaluate(rank, trace, declared=None):
    try:
        if type(rank) is not int or rank not in (79, 94):
            raise ValueError('case must be a registered plain integer')
        validate_transport(trace)
        result = frozen_core.evaluate(trace, contract(rank) if declared is None else declared)
        if result['verdict'] == 'UNSUPPORTED':
            result = dict(result, missing=['.'.join(p) for p in result['missing']])
        return result
    except Exception:
        return dict(verdict='ERROR', failed=[])
