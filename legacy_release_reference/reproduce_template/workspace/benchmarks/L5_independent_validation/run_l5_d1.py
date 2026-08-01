"""Double-locked one-case runner for independent L5-D1."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import sys

BENCHMARK_ROOT=Path(__file__).resolve().parent
NCS_ROOT=BENCHMARK_ROOT.parents[1]
if str(NCS_ROOT) not in sys.path:
    sys.path.insert(0,str(NCS_ROOT))

from benchmarks.L5_independent_validation.src.l5_cases import (
    EVENT_COLUMNS,METRIC_COLUMNS,PROFILE_COLUMNS,execute_case,load_design,
)

AUTHORIZED_CASES=(
 "L5-IV-REF-01","L5-IV-CV-01","L5-IV-MB-01","L5-IV-FR-01",
 "L5-IV-OP-01","L5-IV-RT-01","L5-IV-RT-02","L5-IV-XP-01",
)

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _write_json(path: Path,value: object) -> None:
    path.write_text(json.dumps(value,ensure_ascii=True,indent=2,sort_keys=True,allow_nan=False)+"\n",encoding="utf-8")

def _write_csv(path: Path,columns: tuple[str,...],rows: list[dict[str,object]]) -> None:
    with path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=columns,extrasaction="raise")
        writer.writeheader()
        writer.writerows({key:row.get(key,"NA") for key in columns} for row in rows)

def _parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description="Run one independent L5-D1 case")
    parser.add_argument("--case-id",required=True,choices=AUTHORIZED_CASES)
    parser.add_argument("--run-id",required=True)
    parser.add_argument("--execute-authorized",action="store_true")
    parser.add_argument("--output-root",type=Path,default=None)
    return parser

def _authorize(args: argparse.Namespace) -> None:
    if not args.execute_authorized:
        raise SystemExit("Execution denied: --execute-authorized is required")
    if os.environ.get("L5_D1_EXECUTION_AUTHORIZED")!="YES":
        raise SystemExit("Execution denied: L5_D1_EXECUTION_AUTHORIZED=YES is required")
    if os.environ.get("L5_D1_THREADS")!="1":
        raise SystemExit("Execution denied: L5_D1_THREADS=1 is required")

def main(argv: list[str] | None=None) -> int:
    args=_parser().parse_args(argv)
    _authorize(args)
    freeze,matrix=load_design(NCS_ROOT)
    if args.case_id not in matrix:
        raise SystemExit("case is not frozen")
    output_root=args.output_root or BENCHMARK_ROOT/"results"/"L5_D1_independent_validation"
    output=output_root/args.case_id/args.run_id
    if output.exists():
        raise SystemExit(f"Refusing to overwrite {output}")
    payload=execute_case(NCS_ROOT,args.case_id,args.run_id)
    output.mkdir(parents=True,exist_ok=False)
    result_path=output/"case_result.json"
    metric_path=output/"metric_comparison.csv"
    profile_path=output/"accepted_profile.csv"
    event_path=output/"lifecycle_event_log.csv"
    manifest_path=output/"case_manifest.json"
    _write_json(result_path,payload["case_result"])
    _write_csv(metric_path,METRIC_COLUMNS,payload["metric_comparison"])
    _write_csv(profile_path,PROFILE_COLUMNS,payload["accepted_profile"])
    _write_csv(event_path,EVENT_COLUMNS,payload["lifecycle_event_log"])
    _write_json(manifest_path,{
        "design_version":freeze["design_version"],
        "host_version":payload["case_result"]["host_version"],
        "case_id":args.case_id,"run_id":args.run_id,
        "execution_authorized":True,
        "processes_per_repetition":1,"threads_per_process":1,
        "python_version":platform.python_version(),"platform":platform.platform(),
        "thread_environment":{key:os.environ.get(key) for key in ("L5_D1_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS")},
        "abaqus_used":False,"production_model_used":False,
        "inputs":{
            "L5_D1_execution_freeze.json":_sha(BENCHMARK_ROOT/"L5_D1_execution_freeze.json"),
            "L5_D0_case_matrix.csv":_sha(BENCHMARK_ROOT/"L5_D0_case_matrix.csv"),
            "L5_D0_independence_contract.md":_sha(BENCHMARK_ROOT/"L5_D0_independence_contract.md"),
        },
        "outputs":{p.name:_sha(p) for p in (result_path,metric_path,profile_path,event_path)},
        "manifest_self_hash_embedded":False,
    })
    return 0 if payload["case_result"]["pass_flag"] else 2

if __name__=="__main__":
    raise SystemExit(main())
