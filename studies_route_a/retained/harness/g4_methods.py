"""Frozen equal-input execution and nonselective descriptive analysis for G4."""
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
sys.dont_write_bytecode = True
from g4_config import ROOT, PYTHON, config
from kit_io import read_json, sha256, write_json_new
from bounded_runner_v4 import capture
from g4_native import verify, require


def now():
    return datetime.now(timezone.utc).isoformat()


def analyze(rank, data, arms, processes, adaptation_seconds):
    rows = data['rows']
    by_arm = {}
    for name in ('lcma', 'rich'):
        versions = [a for a in arms if a['arm'] == name]
        require(len(versions) == 2, 'Two fresh arm processes required')
        require(versions[0]['results'] == versions[1]['results'], 'Same-arm replay disagreement')
        results = versions[0]['results']
        require(len(results) == len(rows), 'Result count changed')
        stats = dict(native_violations=0, native_satisfied=0, detected_violations=0,
            missed_violations=0, false_alarms=0, unsupported=0, invalid=0, errors=0)
        diagnostics = []
        for row, result in zip(rows, results):
            native, verdict = row['native_outcome'], result['verdict']
            if native == 'VIOLATED':
                stats['native_violations'] += 1
                stats['detected_violations'] += int(verdict == 'DETECTED')
                stats['missed_violations'] += int(verdict == 'INVARIANT')
            else:
                require(native == 'SATISFIED', 'Do not score unresolved native evidence')
                stats['native_satisfied'] += 1
                stats['false_alarms'] += int(verdict == 'DETECTED')
            for label, key in (('UNSUPPORTED','unsupported'), ('INVALID','invalid'), ('ERROR','errors')):
                stats[key] += int(verdict == label)
            diagnostics.append(dict(ordinal=row['ordinal'], native_reference=native, **result))
        times = [v['median_ns_per_trace'] for v in versions]
        by_arm[name] = dict(**stats, median_ns_per_trace_by_fresh_process=times,
            median_ns_per_trace=statistics.median(times), diagnoses=diagnostics)
    native_processes = [read_json(r['process_record']) for r in rows]
    native_pids = [p['target_result']['pid'] for p in native_processes]
    method_pids = [a['pid'] for a in arms]
    require(len(set(native_pids)) == len(native_pids) == 12, 'Native PID uniqueness failed')
    require(len(set(method_pids)) == len(method_pids) == 4, 'Method PID uniqueness failed')
    require(all(a['input_sha256'] == arms[0]['input_sha256'] for a in arms), 'Unequal method observations')
    ratio = by_arm['lcma']['median_ns_per_trace'] / by_arm['rich']['median_ns_per_trace']
    parity = by_arm['lcma']['diagnoses'] == by_arm['rich']['diagnoses']
    expected = {'before-control':'SATISFIED', 'after-control':'SATISFIED',
                'before-trigger':'VIOLATED', 'after-trigger':'SATISFIED'}
    contrasts = [dict(repetition=i, matched=all(r['native_outcome'] == expected[r['cell']]
        for r in rows if r['repetition'] == i)) for i in (1,2,3)]
    return dict(utc=now(), rank=rank, root_count=1, project_count=1,
        evidence_class='EXPOSED_PROJECT_EQUAL_INFORMATION_FORMAL_COMPARISON',
        native_processes=12, method_processes=4, same_input_sha256=arms[0]['input_sha256'],
        native_pids=native_pids, method_pids=method_pids, native_contrast_replays=contrasts,
        diagnostic_parity=parity, arms=by_arm, lcma_over_rich_pure_evaluator_time_ratio=ratio,
        shared_native_wall_seconds=sum(p['elapsed_seconds'] for p in native_processes),
        shared_native_cpu_seconds=sum(p['resource_metrics']['cpu_seconds'] for p in native_processes),
        shared_native_peak_job_memory_bytes=max(p['resource_metrics']['peak_job_memory_bytes'] for p in native_processes),
        projected_input_packing_seconds=adaptation_seconds,
        raw_projection_serialization_hash_seconds=sum(r['projection_serialization_and_hash_seconds'] for r in rows),
        evaluator_process_costs=[dict(arm=a['arm'], pid=a['pid'], wall_seconds=p['elapsed_seconds'],
            cpu_seconds=p['resource_metrics']['cpu_seconds'], peak_job_memory_bytes=p['resource_metrics']['peak_job_memory_bytes'])
            for a,p in zip(arms,processes)],
        claims=dict(new_root_delta=0, developed_project_not_holdout=True, independent_humans=0,
            production_validation=0, population_inference=False, diagnostic_ids_are_not_causal_localization=True,
            timing_is_descriptive_not_cpu_pinned=True, native_collection_shared_not_instrumentation_baseline=True,
            precomputed_primitive_observation_oracle_not_invented_by_lcma=True))


def run_rank(rank):
    c = config(rank)
    verify(read_json(ROOT / 'governance/G4_FORMAL_SEAL.json')['files_sha256'])
    data = read_json(c['out'] / 'FORMAL_NATIVE_RESULT.json')
    require(data['passed'] and read_json(c['out'] / 'FRESH_PARENT_READBACK.json')['passed'], 'Native gate incomplete')
    folder = c['out'] / 'methods'
    folder.mkdir(exist_ok=False)
    started = time.perf_counter()
    traces = []
    for row in data['rows']:
        require(sha256(row['method_input']) == row['method_input_sha256'], 'Projected input drift')
        traces.append(read_json(row['method_input']))
    input_path = folder / 'input.json'
    write_json_new(input_path, traces)
    adaptation_seconds = time.perf_counter() - started
    write_json_new(folder / 'INPUT_SEAL.json', dict(utc=now(), input_sha256=sha256(input_path),
        source_input_hashes=[r['method_input_sha256'] for r in data['rows']],
        operational_labels_in_separate_parent_records=True, information_same_for_both_arms=True))
    arms, processes = [], []
    for ordinal, arm in enumerate(('lcma','rich','rich','lcma'), 1):
        verify(read_json(ROOT / 'governance/G4_FORMAL_SEAL.json')['files_sha256'])
        result_path = folder / ('E%02d.json' % ordinal)
        argv = [PYTHON, '-B', str(ROOT / 'harness/evaluate_arm.py'), '--arm', arm,
            '--rank', str(rank), '--input', str(input_path), '--output', str(result_path)]
        process = capture(argv, folder / ('E%02d' % ordinal), cwd='work', timeout_seconds=180,
            max_log_bytes=16777216, directory_limits=[{'paths':[str(folder)],'bytes':2147483648}])
        require(process['status'] == 'COMPLETED' and process['exit_code'] == 0 and not process['cleanup_errors'], 'Arm process failed')
        result = read_json(result_path)
        require(result['pid'] == process['target_result']['pid'], 'Method PID not bound to process')
        require(result['input_sha256'] == sha256(input_path), 'Arm did not use sealed input')
        arms.append(result)
        processes.append(process)
    report = analyze(rank, data, arms, processes, adaptation_seconds)
    write_json_new(folder / 'COMPARISON.json', report)
    print('r%d parity=%s LCMA/rich pure-evaluator ratio=%.4f' %
          (rank, report['diagnostic_parity'], report['lcma_over_rich_pure_evaluator_time_ratio']), flush=True)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('rank', type=int, choices=[79,94])
    run_rank(p.parse_args().rank)
