from __future__ import annotations
import argparse, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"src"))
from p4d5b_protocol import CASE_ID,P4D2_RESULTS_ROOT,P4D2_ROOT,case_authorized,require_case_and_run,require_descendant,require_single_thread_environment,verify_protected_inputs,verify_retry_prerequisite
from p4d5b_output_schema import install_erratum

def parse_args(argv=None):
 p=argparse.ArgumentParser(); p.add_argument("--case-id",required=True); p.add_argument("--run-id",required=True); p.add_argument("--results-root",required=True); p.add_argument("--dependency-root",required=True); p.add_argument("--execute-authorized",action="store_true"); return p.parse_args(argv)

def main(argv=None):
 args=parse_args(argv); require_case_and_run(args.case_id,args.run_id)
 if not case_authorized(args.execute_authorized): raise SystemExit("P4d.5b requires both case authorization locks")
 require_single_thread_environment(); verify_protected_inputs(); verify_retry_prerequisite()
 results_root=require_descendant(Path(args.results_root),ROOT/"results")
 if Path(args.dependency_root).resolve()!=P4D2_RESULTS_ROOT.resolve(): raise SystemExit("dependency root must be protected P4d.2 formal evidence")
 result_directory=results_root/CASE_ID/args.run_id
 if result_directory.exists(): raise SystemExit(f"refusing to overwrite {result_directory}")
 for path in (P4D2_ROOT/"src",P4D2_ROOT/"oracle"):
  if str(path) not in sys.path: sys.path.insert(0,str(path))
 from p4d_environment import collect_environment
 import p4d_cases
 patch=install_erratum(P4D2_ROOT)
 result_directory.mkdir(parents=True)
 try:
  result=p4d_cases.execute_case(root=P4D2_ROOT,case_id=CASE_ID,run_id=args.run_id,result_directory=result_directory,dependency_root=P4D2_RESULTS_ROOT,environment=collect_environment(args.run_id))
 finally:
  patch.restore()
 return 0 if result.get("pass_flag") is True or (type(result.get("pass_flag")) is int and result.get("pass_flag")==1) else 2
if __name__=="__main__": raise SystemExit(main())
