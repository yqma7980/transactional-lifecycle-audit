"""One information-restricted fresh method process; no native target imports."""
import argparse
import copy
import importlib.util
import json
import os
import statistics
import sys
import time
from pathlib import Path
sys.dont_write_bytecode = True
from kit_io import read_json, sha256, write_json_new
from g4_config import ROOT


def main(args):
    input_file = Path(args.input)
    data = read_json(input_file)
    if type(data) is not list or not data:
        raise ValueError('Method input is only an ordinal list of label-free traces')
    if args.arm == 'lcma':
        import lcma_arm
        declared = lcma_arm.contract(args.rank)
        evaluate = lambda trace: lcma_arm.normalized_evaluate(args.rank, trace, declared)
        impl = [Path(lcma_arm.__file__), ROOT / 'core/frozen_core.py', ROOT / 'harness/projection.py']
    else:
        selected = ROOT / 'baseline/successors/R02_TYPED_JSON_20260907/rich_compare.py'
        if sha256(selected) != '3909177d7942525dc01c7368bdfceb32f540e2693b88a1e98fa3bf3900a42f5b':
            raise ValueError('Selected independently authored baseline bytes changed')
        spec = importlib.util.spec_from_file_location('rich_compare', selected)
        rich_compare = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rich_compare)
        evaluate = lambda trace: rich_compare.normalized_evaluate(args.rank, trace)
        impl = [Path(rich_compare.__file__)]
    original = copy.deepcopy(data)
    results = [evaluate(trace) for trace in data]
    if original != data:
        raise ValueError('Method mutated its observations')
    for _ in range(20):
        for trace in data:
            evaluate(trace)
    timings = []
    cpu_start = time.process_time_ns()
    for _ in range(7):
        start = time.perf_counter_ns()
        for _ in range(100):
            for trace in data:
                evaluate(trace)
        timings.append((time.perf_counter_ns() - start) / (100 * len(data)))
    if original != data or [evaluate(t) for t in data] != results:
        raise ValueError('Method state drift in repeated evaluation')
    write_json_new(args.output, dict(pid=os.getpid(), rank=args.rank, arm=args.arm,
        input_sha256=sha256(input_file), input_rows=len(data), results=results,
        implementation_sha256={str(p):sha256(p) for p in impl},
        timed_ns_per_trace_batches=timings, median_ns_per_trace=statistics.median(timings),
        batch_cpu_seconds=(time.process_time_ns()-cpu_start)/1e9,
        warmup_rounds=20, timed_batches=7, evaluations_per_trace_per_batch=100,
        native_target_imports=0, native_verdict_inputs=False, management_label_inputs=False,
        input_path_is_ordinal_transport_only=True, precomputed_contract_outside_timer=True,
        validation_warmup_and_serialization_excluded_from_pure_evaluator_timing=True))
    print(json.dumps(dict(arm=args.arm, rank=args.rank, rows=len(data), pid=os.getpid())), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--arm', choices=['lcma','rich'], required=True)
    p.add_argument('--rank', choices=[79,94], type=int, required=True)
    p.add_argument('--input', required=True)
    p.add_argument('--output', required=True)
    main(p.parse_args())
