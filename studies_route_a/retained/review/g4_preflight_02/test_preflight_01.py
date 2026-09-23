"""Independent literal synthetic G4 contract and orchestration regression.

No saved native observations are used as method input. Native launch, target
imports, network access, and writes outside this review folder are prohibited.
"""
import argparse
import ast
import copy
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from review_io import ROOT, put, sha

FORBIDDEN_IMPORTS = ('celery', 'django', 'keras', 'tf_keras', 'tensorflow', 'kombu', 'vine', 'billiard')


def audit(event, args):
    if event == 'import' and str(args[0]).split('.')[0] in FORBIDDEN_IMPORTS:
        raise RuntimeError('Target import prohibited in reviewer QA')
    if event.startswith(('subprocess.', 'socket.')) or event in ('os.system', 'os.exec', 'os.spawn'):
        raise RuntimeError('No child or network operation in synthetic tests')
    if event == 'open' and not isinstance(args[0], int):
        mode, flags = args[1], args[2]
        writing = (isinstance(mode, str) and any(s in mode for s in 'wax+'))
        writing |= isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        if writing:
            Path(args[0]).resolve().relative_to(HERE)
    if event in ('os.mkdir', 'os.remove', 'os.rmdir', 'os.rename', 'os.replace'):
        Path(args[0]).resolve().relative_to(HERE)
        if event in ('os.rename', 'os.replace'):
            Path(args[1]).resolve().relative_to(HERE)


sys.addaudithook(audit)
sys.path.insert(0, str(ROOT / 'harness'))
import lcma_arm
import projection
import evaluate_arm
import g4_native
import g4_config
import g4_methods
import formal_batch
import preservation
import seal_g4

handoff = json.loads((ROOT / 'baseline/INDEPENDENT_BASELINE_HANDOFF.json').read_text(encoding='utf-8'))
selected = Path(handoff['selected_module']['path']).resolve()
spec = importlib.util.spec_from_file_location('review_selected_rich', selected)
rich = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rich)
CHECKS = []
INPUTS = {}


def check(name, condition, detail=None):
    CHECKS.append(dict(name=name, passed=bool(condition), detail=detail))


def rejects(name, call, exception=Exception):
    try:
        call()
    except exception as exc:
        check(name, True, dict(exception=type(exc).__name__, message=str(exc)[:200]))
    else:
        check(name, False, 'Unexpected acceptance')


ATTRS = ('file_equal', 'name', 'url', 'storage', 'instance', 'field')
FIELDS = ('pending_after', 'pending_ids_after', 'callback_receipts', 'callback_counts', 'callback_enter_return_balance')
IDS94 = ('pending_count_empty', 'pending_ids_empty', 'receipt_order', 'callback_once', 'callback_balanced')
ELIGIBLE_KEYS = ('protocol_id', 'observation_point', 'observation_order')
ELIGIBLE_IDS = ('protocol_matches', 'point_matches', 'order_matches')
ERROR = dict(verdict='ERROR', failed=[])
OK = dict(verdict='INVARIANT', failed=[])


def fixture(rank):
    if rank == 79:
        return dict(context=dict(protocol_id='G4-ASSOCIATION-RESTORE-1',
            observation_point='post_restore_property_window', observation_order=list(ATTRS)),
            samples=dict(checks={a:dict(status='VALUE', equal=True) for a in ATTRS}))
    return dict(context=dict(protocol_id='G4-PENDING-CALLBACK-1',
        observation_point='immediate_native_exit_before_cleanup', observation_order=list(FIELDS)),
        samples=dict(pending_after=0, pending_ids_after=[], callback_receipts=['op_b', 'op_a'],
                     callback_counts=dict(op_a=1, op_b=1), callback_enter_return_balance=dict(op_a=[1,1], op_b=[1,1])))


def expected_failed(rank, indexes):
    ids = ['restored_' + a for a in ATTRS] if rank == 79 else IDS94
    return dict(verdict='DETECTED' if indexes else 'INVARIANT',
                failed=[dict(id=ids[i], obligation='O3' if rank == 79 else 'O5') for i in indexes])


def operand_box(trace, rank):
    return trace['samples']['checks'] if rank == 79 else trace['samples']


def both(name, rank, trace, expected, immutable=True):
    before = copy.deepcopy(trace) if immutable else None
    for arm, function in (('lcma', lcma_arm.normalized_evaluate), ('rich', rich.normalized_evaluate)):
        got = function(rank, trace)
        check('%s/r%r/%s' % (name, rank, arm), got == expected, dict(expected=expected, actual=got))
    if immutable:
        check('%s/r%r/no_mutation' % (name, rank), before == trace)


def comparison_tests():
    for rank in (79, 94):
        fields = ATTRS if rank == 79 else FIELDS
        for mask in range(1 << len(fields)):
            trace = fixture(rank)
            indexes = [i for i in range(len(fields)) if mask & (1 << i)]
            for i in indexes:
                operand_box(trace, rank)[fields[i]] = None
            both('truth_mask_%02d' % mask, rank, trace, expected_failed(rank, indexes))
        for mask in range(8):
            trace = fixture(rank)
            indexes = [i for i in range(3) if mask & (1 << i)]
            for i in indexes:
                trace['context'][ELIGIBLE_KEYS[i]] = None
            want = dict(verdict='INVALID', invalid=[ELIGIBLE_IDS[i] for i in indexes], failed=[]) if indexes else OK
            both('eligibility_mask_%d' % mask, rank, trace, want)
        for i, field in enumerate(fields):
            trace = fixture(rank)
            del operand_box(trace, rank)[field]
            trace['context']['protocol_id'] = 'not-the-registered-protocol'
            path = 'samples.' + ('checks.' if rank == 79 else '') + field
            both('missing_precedes_invalid_' + field, rank, trace, dict(verdict='UNSUPPORTED', missing=[path], failed=[]))
        trace = fixture(rank)
        trace['context'] = {}
        trace['samples'] = {}
        paths = ['context.' + k for k in ELIGIBLE_KEYS]
        paths += ['samples.' + ('checks.' if rank == 79 else '') + f for f in fields]
        both('all_missing_in_order', rank, trace, dict(verdict='UNSUPPORTED', missing=paths, failed=[]))
        for value in ({}, [], None, 0, False, 'other'):
            trace = fixture(rank)
            trace['context'] = value
            both('arbitrary_context_' + repr(value), rank, trace,
                 dict(verdict='UNSUPPORTED', missing=['context.'+k for k in ELIGIBLE_KEYS], failed=[]))
        for value in ({}, [], None, 0, False, 'other'):
            trace = fixture(rank)
            operand_box(trace, rank)[fields[0]] = value
            want = OK if rank == 94 and type(value) is int and value == 0 else expected_failed(rank, [0])
            both('present_operand_' + repr(value), rank, trace, want)
        trace = fixture(rank)
        trace['samples']['ignored'] = {'z': [None, False, 1, 1.0, '1', {}, []]}
        trace['context']['ignored'] = 'legal extra'
        both('finite_extra_ignored', rank, trace, OK)
        for value in (float('nan'), float('inf'), float('-inf'), object(), (1, 2), {1, 2}, b'bytes'):
            trace = fixture(rank)
            trace['samples']['ignored'] = value
            both('invalid_extra_' + type(value).__name__ + '_' + str(len(CHECKS)), rank, trace, ERROR, immutable=False)
        for label in ('native_outcome', 'cell', 'version', 'pid', 'oracle', 'source_commit'):
            trace = fixture(rank)
            trace[label] = 'hidden management value'
            both('reject_outer_' + label, rank, trace, ERROR)
        for i, malformed in enumerate((None, {}, [], ['context', 'samples'], {'context':{}}, {'samples':{}})):
            both('invalid_envelope_%d' % i, rank, malformed, ERROR)
        cycle = []
        cycle.append(cycle)
        trace = fixture(rank)
        trace['samples']['ignored'] = cycle
        both('cyclic_non_json', rank, trace, ERROR, immutable=False)
        deep = None
        for _ in range(1500):
            deep = [deep]
        trace = fixture(rank)
        trace['samples']['ignored'] = deep
        both('finite_acyclic_depth_1500', rank, trace, OK, immutable=False)
        class PretendPrimitive(type):
            def __eq__(cls, other):
                return other in (str, int, bool, type(None))
        class NonJson(metaclass=PretendPrimitive):
            pass
        trace = fixture(rank)
        trace['samples']['ignored'] = NonJson()
        both('unsupported_metaclass_value', rank, trace, ERROR, immutable=False)
        class IntChild(int):
            pass
        for invalid_rank in (True, False, float(rank), str(rank), None, IntChild(rank), 80):
            both('case_type_' + type(invalid_rank).__name__ + '_' + repr(invalid_rank),
                 invalid_rank, fixture(rank), ERROR)
    trace = fixture(79)
    trace['samples']['checks']['name'] = {'status':'VALUE', 'equal':1}
    both('boolean_not_int', 79, trace, expected_failed(79, [1]))
    trace = fixture(79)
    trace['samples']['checks']['name'] = {'status':'ATTRIBUTE_ERROR', 'equal':None}
    both('attribute_error_is_present', 79, trace, expected_failed(79, [1]))
    for wrong in (False, 0.0):
        trace = fixture(94)
        trace['samples']['pending_after'] = wrong
        both('pending_exact_int_' + repr(wrong), 94, trace, expected_failed(94, [0]))
    trace = fixture(94)
    trace['samples']['callback_counts'] = dict(op_b=1, op_a=1)
    both('object_order_irrelevant', 94, trace, OK)
    trace['samples']['callback_receipts'].reverse()
    both('list_order_significant', 94, trace, expected_failed(94, [2]))


def projection_tests():
    for rank in (79, 94):
        good = fixture(rank)
        events = ([dict(event='PROPERTY_CHECK:' + a, fields=copy.deepcopy(good['samples']['checks'][a])) for a in ATTRS]
                  if rank == 79 else [dict(event='TERMINAL_SNAPSHOT', fields=copy.deepcopy(good['samples']))])
        for event in events:
            event.update(pid=55, cell='before-trigger', native_outcome='VIOLATED', source_commit='SECRET')
            event['fields'].update(traceback='SECRET', version='SECRET', oracle={'verdict':'SECRET'})
        events.append(dict(event='UNRELATED_METADATA', fields=dict(secret='SECRET')))
        original = copy.deepcopy(events)
        projected = projection.project(rank, events)
        check('projection_whitelist_r%d' % rank, projected == good and 'SECRET' not in json.dumps(projected))
        check('projection_no_mutation_r%d' % rank, original == events)
        if rank == 94:
            projected['samples']['callback_receipts'].append('changed-copy-only')
        else:
            projected['samples']['checks']['name']['status'] = 'changed-copy-only'
        check('projection_detached_r%d' % rank, original == events)
        rejects('projection_duplicate_window_r%d' % rank, lambda: projection.project(rank, events + [copy.deepcopy(events[0])]))
        rejects('projection_missing_window_r%d' % rank, lambda: projection.project(rank, events[1:]))
        rejects('projection_nonlist_r%d' % rank, lambda: projection.project(rank, {}))


def orchestration_tests(work):
    check('selected_handoff_sha', sha(selected) == handoff['selected_module']['sha256'])
    before = fixture(94)
    input_path, output_path = work/'dispatch_input.json', work/'dispatch_result.json'
    put(input_path, [before])
    evaluate_arm.main(SimpleNamespace(input=str(input_path), output=str(output_path), arm='rich', rank=94))
    result = json.loads(output_path.read_text(encoding='utf-8'))
    expected_map = {str(selected): sha(selected)}
    actual_map = {str(Path(p).resolve()): h for p, h in result['implementation_sha256'].items()}
    check('actual_loader_selects_exact_R02', actual_map == expected_map, dict(expected=expected_map, actual=actual_map))
    check('dispatch_pure_fixture_result', result['results'] == [OK] and result['input_sha256'] == sha(input_path))
    check('dispatch_timing_contract', len(result['timed_ns_per_trace_batches']) == 7 and
          result['warmup_rounds'] == 20 and result['evaluations_per_trace_per_batch'] == 100)
    for rank in (79, 94):
        config = g4_config.config(rank)
        capture = g4_native.native_capture(config)
        runner_path = Path(capture.__code__.co_filename).resolve()
        runner_root = runner_path.parents[1]
        check('native_capture_exact_origin_r%d' % rank,
              runner_path == config['native_runner'].resolve() and runner_root == config['anchor'].resolve(),
              dict(actual_path=str(runner_path), module=capture.__module__))
        check('native_capture_root_matches_run_scope_r%d' % rank, config['runs'].is_relative_to(runner_root))
        check('native_capture_distinct_module_r%d' % rank, capture.__module__ == 'owned_native_capture_%d' % rank)
        check('native_original_helper_bytes_r%d' % rank,
              sha(runner_path) == sha(ROOT/'harness/bounded_runner_v4.py') and
              sha(runner_path.with_name('_child_launcher.py')) == sha(ROOT/'harness/_child_launcher.py'))
        with patch.object(capture.__globals__['subprocess'], 'Popen', side_effect=RuntimeError('No launch allowed')) as popen:
            rejects('native_original_guard_invalid_cwd_r%d' % rank,
                    lambda: capture([sys.executable, '-B', '-c', 'pass'], work/'GUARD_CWD_NEVER_CREATED',
                                    cwd='../outside', timeout_seconds=1), ValueError)
            rejects('native_original_guard_foreign_path_r%d' % rank,
                    lambda: capture([sys.executable, '-B', '-c', 'pass'], work/'GUARD_FOREIGN_NEVER_CREATED',
                                    cwd='work', timeout_seconds=1), ValueError)
            check('native_guard_zero_process_calls_r%d' % rank, popen.call_count == 0)
            check('native_guard_zero_residue_r%d' % rank,
                  not (work/'GUARD_CWD_NEVER_CREATED').exists() and not (work/'GUARD_FOREIGN_NEVER_CREATED').exists())
        for kind in ('runner', 'launcher'):
            bad_path = config['native_runner'] if kind=='runner' else config['native_runner'].with_name('_child_launcher.py')
            original_sha = g4_native.sha256
            with patch.object(g4_native, 'sha256',
                              side_effect=lambda p: 'bad' if Path(p).resolve()==bad_path.resolve() else original_sha(p)):
                rejects('native_reject_%s_drift_r%d' % (kind,rank), lambda:g4_native.native_capture(config), ValueError)
        bad_config = dict(config, runs=ROOT/'not_an_authorized_native_anchor')
        rejects('native_reject_foreign_ownership_r%d' % rank, lambda:g4_native.native_capture(bad_config), ValueError)
        check('fresh_native_root_absent_r%d' % rank, not config['runs'].exists())
        plan_path = config['out']/'CASE_PLAN.json'
        INPUTS[str(plan_path.resolve())] = sha(plan_path)
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        cells = plan['cells']
        check('plan_12_distinct_ids_r%d' % rank, len(cells) == len({c['run_id'] for c in cells}) == 12)
        check('plan_exact_order_r%d' % rank, [c['cell'] for c in cells] == sum(g4_config.ORDERS, []))
        check('plan_exact_sequence_r%d' % rank, plan['sequence_start'] == (0 if rank == 79 else 1))
        check('plan_resource_contract_r%d' % rank, plan['process_bound_seconds'] == 180 and
              plan['case_bound_seconds'] == 900 and plan['max_stream_bytes'] == 16777216)
        for i, item in enumerate(cells, 1):
            path = Path(item['path']).resolve()
            INPUTS[str(path)] = sha(path)
            spec_data = json.loads(path.read_text(encoding='utf-8'))
            check('plan_spec_binding_r%d_%02d' % (rank, i), sha(path) == item['sha256'] and
                  spec_data['run_id'] == item['run_id'] and
                  Path(spec_data['cwd']).resolve() == (Path(item['run_directory'])/'work').resolve())
    for invalid in (80, True, 79.0, '94'):
        rejects('config_reject_' + repr(invalid), lambda: g4_config.config(invalid))
    tree = ast.parse(selected.read_text(encoding='utf-8'))
    imports = [n.names[0].name for n in ast.walk(tree) if isinstance(n, ast.Import)]
    check('baseline_static_independence_math_only', imports == ['math'] and
          not any(isinstance(n, ast.ImportFrom) for n in ast.walk(tree)))
    check('baseline_no_optimizer_removed_assertions', not any(isinstance(n, ast.Assert) for n in ast.walk(tree)))
    check('unchanged_core_identity', sha(ROOT/'core/frozen_core.py') ==
          'ace349aa9a7750e7891acdf6ccbf1705cecc5bae3f3ec67fdbebb28f31e6fc13')


def method_analysis_tests():
    rows, procmap = [], {}
    for i in range(12):
        rows.append(dict(ordinal=i+1, repetition=i//4+1, cell=g4_config.ORDERS[i//4][i%4],
            native_outcome='VIOLATED' if i < 4 else 'SATISFIED', process_record='FAKE_%d' % i,
            projection_serialization_and_hash_seconds=.01))
        procmap['FAKE_%d' % i] = dict(target_result=dict(pid=100+i), elapsed_seconds=1,
            resource_metrics=dict(cpu_seconds=.5, peak_job_memory_bytes=1000))
    results = [dict(verdict=v, failed=[]) for v in
               ('DETECTED','INVARIANT','ERROR','UNSUPPORTED','DETECTED','INVARIANT','INVALID','ERROR',
                'INVARIANT','INVARIANT','INVARIANT','INVARIANT')]
    arms = [dict(arm=a, results=copy.deepcopy(results), median_ns_per_trace=100, pid=200+i, input_sha256='shared')
            for i,a in enumerate(('lcma','rich','rich','lcma'))]
    processes = [dict(elapsed_seconds=.1,resource_metrics=dict(cpu_seconds=.01,peak_job_memory_bytes=100)) for _ in arms]
    with patch.object(g4_methods, 'read_json', side_effect=lambda p:copy.deepcopy(procmap[p])):
        result = g4_methods.analyze(94, dict(rows=rows), arms, processes, .03)
        stats = result['arms']['lcma']
        check('analysis_nonselective_error_accounting', all(stats[k] == v for k,v in dict(
              native_violations=4,native_satisfied=8,detected_violations=1,missed_violations=1,
              false_alarms=1,unsupported=1,invalid=1,errors=2).items()))
        check('analysis_equal_information_and_parity', result['diagnostic_parity'] and result['same_input_sha256']=='shared')
        check('analysis_cost_labels_distinct', abs(result['raw_projection_serialization_hash_seconds']-.12)<1e-12 and
              result['projected_input_packing_seconds']==.03)
        check('analysis_no_independent_bug_inflation', result['root_count']==1 and result['native_processes']==12 and
              result['claims']['new_root_delta']==0 and result['claims']['population_inference'] is False and
              result['claims']['timing_is_descriptive_not_cpu_pinned'] is True)
        bad = copy.deepcopy(arms)
        bad[1]['input_sha256'] = 'different'
        rejects('analysis_reject_unequal_input', lambda:g4_methods.analyze(94,dict(rows=rows),bad,processes,.03))
        bad = copy.deepcopy(arms)
        bad[1]['pid'] = bad[0]['pid']
        rejects('analysis_reject_reused_method_pid', lambda:g4_methods.analyze(94,dict(rows=rows),bad,processes,.03))
        bad = copy.deepcopy(arms)
        bad[3]['results'][0]['verdict'] = 'INVARIANT'
        rejects('analysis_reject_replay_drift', lambda:g4_methods.analyze(94,dict(rows=rows),bad,processes,.03))
        badrows = copy.deepcopy(rows)
        badrows[0]['native_outcome'] = 'UNRESOLVED'
        rejects('analysis_reject_unresolved', lambda:g4_methods.analyze(94,dict(rows=badrows),arms,processes,.03))
        procmap['FAKE_1']['target_result']['pid'] = 100
        rejects('analysis_reject_reused_native_pid', lambda:g4_methods.analyze(94,dict(rows=rows),arms,processes,.03))


def batch_tests():
    for failure_at in (None, 0, 2, 4):
        calls, written = [], []
        def capture(argv, path, **kwargs):
            calls.append(dict(argv=argv, path=str(path), kwargs=kwargs))
            failed = len(calls)-1 == failure_at
            return dict(status='COMPLETED', exit_code=1 if failed else 0, cleanup_errors=[])
        with patch.object(formal_batch,'capture',side_effect=capture), patch.object(formal_batch,'verify'), \
             patch.object(formal_batch,'read_json',return_value=dict(files_sha256={})), \
             patch.object(formal_batch,'write_json_new',side_effect=lambda p,v:written.append((str(p),v))):
            try:
                formal_batch.main()
                rejected = False
            except ValueError:
                rejected = True
        name = 'batch_' + str(failure_at)
        check(name+'_stop_or_complete', rejected == (failure_at is not None) and
              len(calls) == (6 if failure_at is None else failure_at+1))
        check(name+'_resource_limits', all(0 < c['kwargs']['timeout_seconds'] <= 900 and
              c['kwargs']['max_log_bytes']==16777216 for c in calls))
        check(name+'_new_output_scope', all(Path(c['path']).is_relative_to(ROOT) for c in calls))
        check(name+'_no_retry', len({c['path'] for c in calls})==len(calls))
        check(name+'_durable_status', written[-1][1]['passed'] == (failure_at is None))
        if failure_at is None:
            check('batch_serial_rank_mode_order', [(Path(c['argv'][2]).name,c['argv'][3:]) for c in calls] ==
                  [('g4_native.py',['run','79']),('g4_native.py',['recheck','79']),('g4_methods.py',['79']),
                   ('g4_native.py',['run','94']),('g4_native.py',['recheck','94']),('g4_methods.py',['94'])])


def preservation_tests():
    oldpath = str(g4_config.OLD79/'historical.json')
    old = dict(files={oldpath:dict(bytes=3,sha256='abc')},links={})
    for label in ('unchanged','changed','missing','allowed_add','unexpected_add','reparse_change'):
        current = copy.deepcopy(old)
        if label == 'changed': current['files'][oldpath]['sha256']='different'
        if label == 'missing': del current['files'][oldpath]
        if label == 'allowed_add': current['files'][str(g4_config.config(79)['runs']/'new.json')]=dict(bytes=1,sha256='new')
        if label == 'unexpected_add': current['files'][str(g4_config.OLD79/'new.json')]=dict(bytes=1,sha256='new')
        if label == 'reparse_change': current['links']['fake']='elsewhere'
        written = []
        with patch.object(preservation,'inventory',return_value=current), patch.object(preservation,'read_json',return_value=old), \
             patch.object(preservation,'sha256',return_value='sealed'), \
             patch.object(preservation,'write_json_new',side_effect=lambda p,v:written.append(v)):
            try:
                preservation.main('after')
                rejected = False
            except ValueError:
                rejected = True
        want = label in ('unchanged','allowed_add')
        check('preservation_'+label, written[-1]['passed'] is want and rejected is not want)


def seal_tests():
    base = json.loads((HERE/'PREFLIGHT_INPUTS_START_01.json').read_text(encoding='utf-8'))
    hashes = {p:sha(p) for p in base['reviewed_files_sha256']}
    fixture_path = HERE/'PREFLIGHT_INPUTS_START_01.json'
    for label in ('valid', 'review_failed', 'open_blocker', 'boolean_blocker_count', 'missing_current_review',
                  'reviewed_bytes_drift', 'native_root_exists', 'wrong_plan_rank', 'core_drift',
                  'baseline_drift', 'old_bytes_drift'):
        review = dict(passed=True,open_acceptance_blockers=0,reviewed_files_sha256=dict(hashes),
                      independent_ai=True,independent_human=False)
        if label == 'review_failed': review['passed']=False
        if label == 'open_blocker': review['open_acceptance_blockers']=1
        if label == 'boolean_blocker_count': review['open_acceptance_blockers']=False
        if label == 'missing_current_review': del review['reviewed_files_sha256'][str((ROOT/'harness/g4_methods.py').resolve())]
        if label == 'reviewed_bytes_drift': review['reviewed_files_sha256'][str(selected)]='bad'
        def read(path):
            path=Path(path)
            if path.name=='G4_PREFLIGHT_REVIEW.json': return review
            if path.name=='INDEPENDENT_BASELINE_HANDOFF.json': return handoff
            if path.name=='HISTORICAL_BYTES_BEFORE.json':
                return dict(files={str(fixture_path):dict(sha256='bad' if label=='old_bytes_drift' else sha(fixture_path))})
            if path.name=='CASE_PLAN.json':
                rank=79 if 'r079' in path.parts else 94
                return dict(files_sha256={},cells=list(range(12)),rank=80 if label=='wrong_plan_rank' else rank)
            raise RuntimeError('Unexpected pure-seal read: '+str(path))
        def config(rank):
            result=g4_config.config(rank)
            if label=='native_root_exists': result['runs']=HERE
            return result
        def digest(path):
            path=Path(path).resolve()
            if path.name=='G4_PREFLIGHT_REVIEW.json': return sha(fixture_path)
            if label=='core_drift' and path==(ROOT/'core/frozen_core.py').resolve(): return 'bad'
            if label=='baseline_drift' and path==selected: return 'bad'
            return sha(path)
        written=[]
        with patch.object(seal_g4,'read_json',side_effect=read), patch.object(seal_g4,'config',side_effect=config), \
             patch.object(seal_g4,'sha256',side_effect=digest), \
             patch.object(seal_g4,'write_json_new',side_effect=lambda p,v:written.append((str(p),v))):
            try:
                seal_g4.main()
                rejected=False
            except ValueError:
                rejected=True
        check('seal_'+label, rejected == (label!='valid'))
        if label=='valid':
            seal=written[-1][1]
            check('seal_planned_counts_not_bug_counts', seal['formal_native_runs_planned']==24 and
                  seal['new_independent_roots']==0 and seal['independent_humans']==0 and
                  seal['method_processes_planned']==8)
            check('seal_binds_current_orchestration_and_preservation', all(str(ROOT/'harness'/n) in seal['files_sha256']
                  for n in ('seal_g4.py','g4_methods.py','formal_batch.py','collector_v5.py','bounded_runner_v4.py','preservation.py')))


def successor_tests():
    old_report_path = ROOT/'review/g4_preflight_01/G4_PREFLIGHT_REVIEW.json'
    old_report = json.loads(old_report_path.read_text(encoding='utf-8'))
    prior_hashes = old_report['reviewed_files_sha256']
    backup = ROOT/'harness/superseded_preflight01'
    for name in ('g4_native.py','g4_config.py','lcma_arm.py','projection.py','seal_g4.py'):
        check('prior_author_bytes_preserved_'+name,
              sha(backup/name) == prior_hashes[str((ROOT/'harness'/name).resolve())])
    for path in (ROOT/'core/frozen_core.py', selected, ROOT/'harness/evaluate_arm.py',
                 ROOT/'harness/g4_methods.py', ROOT/'harness/formal_batch.py',
                 ROOT/'contracts/COMPARISON_SEMANTICS.md',ROOT/'contracts/TRANSPORT_CLARIFICATION_01.md'):
        check('unchanged_scientific_or_dispatch_bytes_'+path.name,
              sha(path)==prior_hashes[str(path.resolve())])

    def function(path, name):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        return next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
    for name in ('context',):
        check('projection_declared_context_AST_unchanged',
              ast.dump(function(ROOT/'harness/projection.py',name))==ast.dump(function(backup/'projection.py',name)))
    check('LCMA_declared_contract_AST_unchanged',
          ast.dump(function(ROOT/'harness/lcma_arm.py','contract'))==ast.dump(function(backup/'lcma_arm.py','contract')))
    for name in ('prepare','old_collect','runtime','source','load_original','load_admitted','recheck'):
        check('native_function_AST_unchanged_'+name,
              ast.dump(function(ROOT/'harness/g4_native.py',name))==ast.dump(function(backup/'g4_native.py',name)))
    new_run=function(ROOT/'harness/g4_native.py','run')
    old_run=function(backup/'g4_native.py','run')
    bindings=[n for n in new_run.body if isinstance(n,ast.Assign) and
              any(isinstance(t,ast.Name) and t.id=='capture' for t in n.targets)]
    check('native_run_uses_returned_capture', len(bindings)==1 and isinstance(bindings[0].value,ast.Call) and
          isinstance(bindings[0].value.func,ast.Name) and bindings[0].value.func.id=='native_capture')
    new_run.body=[n for n in new_run.body if n not in bindings]
    check('native_run_other_logic_AST_unchanged',ast.dump(new_run)==ast.dump(old_run))
    check('seal_binds_successor_review_path',
          "review/g4_preflight_02/G4_PREFLIGHT_REVIEW.json" in (ROOT/'harness/seal_g4.py').read_text(encoding='utf-8'))
    check('case_limit_is_preformal_documented',
          'Arbitrary-depth finite-JSON' in (ROOT/'contracts/PREFLIGHT_REPAIR_AND_LIMITS_02.md').read_text(encoding='utf-8'))

    for rank in (79,94):
        trace=fixture(rank)
        events=([dict(event='PROPERTY_CHECK:'+a,fields=copy.deepcopy(trace['samples']['checks'][a])) for a in ATTRS]
                if rank==79 else [dict(event='TERMINAL_SNAPSHOT',fields=copy.deepcopy(trace['samples']))])
        check('fixed_native_projection_depth_four_r%d'%rank,
              projection.json_depth(trace)==4 and projection.project(rank,events)==trace)
        wire=json.loads(json.dumps(projection.project(rank,events),allow_nan=False))
        both('wire_roundtrip_fixed_cohort',rank,wire,OK)
        too_deep=copy.deepcopy(events)
        if rank==79:
            too_deep[0]['fields']['equal']=[True]
        else:
            too_deep[0]['fields']['callback_enter_return_balance']['op_a'][0]=[1]
        rejects('projection_reject_depth_five_r%d'%rank,lambda:projection.project(rank,too_deep),ValueError)
        copied=copy.deepcopy(too_deep)
        try:
            projection.project(rank,too_deep)
        except ValueError:
            pass
        check('projection_failed_shape_not_mutated_r%d'%rank,copied==too_deep)
        for invalid in (None,['context','samples'],dict(context={},samples={},cell='label')):
            with patch.object(lcma_arm.frozen_core,'evaluate',side_effect=RuntimeError('Core must not see bad envelope')) as core:
                got=lcma_arm.normalized_evaluate(rank,invalid)
                check('bad_envelope_stopped_before_core_r%d_%s'%(rank,repr(invalid)),got==ERROR and core.call_count==0)
        shared=[1,None,False]
        trace=fixture(rank)
        trace['samples']['extra_a']=shared
        trace['samples']['extra_b']=shared
        both('noncyclic_aliases_legal',rank,trace,OK)
    cycle=[]
    cycle.append(cycle)
    check('projection_depth_walk_cycle_is_bounded',projection.json_depth(cycle)==5)


def main(output):
    manifest = json.loads((HERE/'PREFLIGHT_INPUTS_START_01.json').read_text(encoding='utf-8'))
    start = {p:sha(p) for p in manifest['reviewed_files_sha256']}
    comparison_tests()
    projection_tests()
    orchestration_tests(output.parent)
    method_analysis_tests()
    batch_tests()
    preservation_tests()
    seal_tests()
    successor_tests()
    check('no_target_imports', not any(k.split('.')[0] in FORBIDDEN_IMPORTS for k in sys.modules))
    end = {p:sha(p) for p in start}
    check('reviewed_input_bytes_unchanged_during_QA', start == end)
    failures = [c for c in CHECKS if not c['passed']]
    retained_names = {'finite_acyclic_depth_1500/r79/lcma', 'finite_acyclic_depth_1500/r94/lcma'}
    unexpected_failures = [c for c in failures if c['name'] not in retained_names]
    retained = [c for c in failures if c['name'] in retained_names]
    scoped_passed = not unexpected_failures and {c['name'] for c in retained} == retained_names
    report = dict(schema='G4_NONAUTHOR_PURE_SYNTHETIC_QA_1', independent_ai=True, independent_human=False,
        native_operations=0, target_imports=0, formal_observations_used=0, synthetic_literal_observations_only=True,
        optimized=sys.flags.optimize, python=sys.version, pid=os.getpid(), passed=not failures,
        case_scoped_passed=scoped_passed, open_case_acceptance_failures=len(unexpected_failures),
        retained_capacity_negative_count=len(retained), retained_capacity_negatives=retained,
        unrestricted_API_passed=False, scope='fixed validated shallow native wire projections only',
        checks=len(CHECKS), passed_checks=len(CHECKS)-len(failures), failed_checks=len(failures),
        reviewed_files_sha256=start, evidence_files_sha256=INPUTS, initial_final_hashes_match=start==end,
        test_script_sha256=sha(__file__), failures=failures, unexpected_failures=unexpected_failures, tests=CHECKS)
    put(output,report)
    print(json.dumps(dict(checks=report['checks'],passed=report['passed_checks'],failed=report['failed_checks'],
                         failures=[f['name'] for f in failures])),flush=True)
    return 0 if scoped_passed else 1


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    sys.exit(main(args.out.resolve()))
