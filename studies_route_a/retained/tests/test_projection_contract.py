"""Synthetic transport/projection checks; no target software imports or native calls."""
import copy
import sys
import unittest
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'harness'))
from projection import project, context, ATTRS79, FIELDS94
from lcma_arm import normalized_evaluate, contract


def events79():
    return [dict(event='PROPERTY_CHECK:' + a, fields=dict(status='VALUE', equal=True,
        error={'secret': 'management'}, native_outcome='not copied')) for a in ATTRS79]


def events94():
    return [dict(event='TERMINAL_SNAPSHOT', fields=dict(pending_after=0, pending_ids_after=[],
        callback_receipts=['op_b', 'op_a'], callback_counts={'op_a': 1, 'op_b': 1},
        callback_enter_return_balance={'op_a': [1, 1], 'op_b': [1, 1]},
        native_outcome='not copied', source_commit='not copied'))]


class Tests(unittest.TestCase):
    def test_exact_whitelist_and_copy(self):
        for rank, factory in ((79, events79), (94, events94)):
            raw = factory()
            old = copy.deepcopy(raw)
            trace = project(rank, raw)
            self.assertEqual(set(trace), {'context', 'samples'})
            self.assertNotIn('not copied', str(trace))
            self.assertNotIn('management', str(trace))
            self.assertEqual(normalized_evaluate(rank, trace), {'verdict': 'INVARIANT', 'failed': []})
            self.assertEqual(raw, old)
            trace['samples'].clear()
            self.assertEqual(raw, old)

    def test_missing_duplicate(self):
        for rank, factory in ((79, events79), (94, events94)):
            raw = factory()
            with self.assertRaises(ValueError):
                project(rank, raw[1:])
            with self.assertRaises(ValueError):
                project(rank, raw + [raw[0]])

    def test_errors_are_not_native_passes(self):
        for rank, factory in ((79, events79), (94, events94)):
            trace = project(rank, factory())
            trace['native_outcome'] = 'SATISFIED'
            self.assertEqual(normalized_evaluate(rank, trace)['verdict'], 'ERROR')
            trace.pop('native_outcome')
            trace['context']['observation_point'] = 'other'
            self.assertEqual(normalized_evaluate(rank, trace)['verdict'], 'INVALID')
            trace['samples'] = {}
            self.assertEqual(normalized_evaluate(rank, trace)['verdict'], 'UNSUPPORTED')

    def test_typed_bool_count_and_failure_ids(self):
        trace = project(94, events94())
        trace['samples']['pending_after'] = False
        self.assertEqual(normalized_evaluate(94, trace), dict(verdict='DETECTED',
            failed=[dict(id='pending_count_empty', obligation='O5')]))
        trace79 = project(79, events79())
        trace79['samples']['checks']['url'] = {'status': 'ATTRIBUTE_ERROR', 'equal': None}
        self.assertEqual(normalized_evaluate(79, trace79), dict(verdict='DETECTED',
            failed=[dict(id='restored_url', obligation='O3')]))

    def test_rule_order_and_reference_immutability(self):
        for rank, factory in ((79, events79), (94, events94)):
            c, trace = contract(rank), project(rank, factory())
            old = copy.deepcopy((c, trace))
            normalized_evaluate(rank, trace, c)
            self.assertEqual((c, trace), old)
            self.assertEqual(len(c['relations']), 6 if rank == 79 else 5)
            self.assertEqual(list(context(rank)), ['protocol_id', 'observation_point', 'observation_order'])


if __name__ == '__main__':
    unittest.main()
