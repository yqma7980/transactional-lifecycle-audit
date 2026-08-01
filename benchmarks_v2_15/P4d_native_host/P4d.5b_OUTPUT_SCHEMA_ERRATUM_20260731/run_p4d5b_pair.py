from __future__ import annotations
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/"src"))
from p4d5b_protocol import CASE_ID,EXPECTED_VERDICT,P4D_ROOT,RUN_IDS,pair_authorized,require_descendant,verify_protected_inputs,verify_retry_prerequisite
IMAGE="dolfinx/dolfinx@sha256:1bb0d528457c78db65ba5445421abe37d0cdfa542cc182bf36d3b4aca02f1fab"
CONTAINER_ROOT="/p4droot"; WORKDIR=f"{CONTAINER_ROOT}/{ROOT.name}"; DEP=f"{CONTAINER_ROOT}/P4d.2_FULL_IMPLEMENTATION_20260731/results/P4d2_formal_20260731"
def parse_args(argv=None):
 p=argparse.ArgumentParser(); p.add_argument("--execution-tag",required=True); p.add_argument("--execute-authorized",action="store_true"); return p.parse_args(argv)
def write_new(path,value):
 if path.exists(): raise RuntimeError(f"refusing to overwrite {path}")
 path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
def replace(path,value): path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
def norm(v):
 if isinstance(v,dict): return {k:norm(x) for k,x in v.items() if k!="run_id"}
 if isinstance(v,list): return [norm(x) for x in v]
 if isinstance(v,str): return v.replace("run_1","<run>").replace("run_2","<run>")
 return v
def run_one(run_id,tag,log_root):
 mount=f"type=bind,source={P4D_ROOT},target={CONTAINER_ROOT}"; cres=f"{WORKDIR}/results/{tag}"
 cmd=["docker","run","--rm","--network","none","--platform","linux/amd64","--env","PYTHONDONTWRITEBYTECODE=1","--env","OMP_NUM_THREADS=1","--env","OPENBLAS_NUM_THREADS=1","--env","MKL_NUM_THREADS=1","--env","P4D5B_EXECUTION_AUTHORIZED=YES","--mount",mount,"--workdir",WORKDIR,IMAGE,"python3","run_p4d5b.py","--case-id",CASE_ID,"--run-id",run_id,"--results-root",cres,"--dependency-root",DEP,"--execute-authorized"]
 c=subprocess.run(cmd,capture_output=True,text=True,check=False); (log_root/f"{CASE_ID}_{run_id}.log").write_text(c.stdout+c.stderr,encoding="utf-8",newline="\n")
 p=ROOT/"results"/tag/CASE_ID/run_id/"case_result.json"
 if not p.is_file(): return {"run_id":run_id,"exit_code":c.returncode,"infrastructure_failure":True}
 x=json.loads(p.read_text(encoding="utf-8")); x["exit_code"]=c.returncode; return x
def main(argv=None):
 a=parse_args(argv)
 if not pair_authorized(a.execute_authorized): raise SystemExit("P4d.5b pair execution requires both authorization locks")
 if not a.execution_tag.startswith("P4d5b_output_schema_"): raise SystemExit("invalid P4d.5b execution tag")
 verify_protected_inputs(); verify_retry_prerequisite()
 rr=require_descendant(ROOT/"results"/a.execution_tag,ROOT/"results"); lr=require_descendant(ROOT/"formal_execution_logs"/a.execution_tag,ROOT/"formal_execution_logs")
 if rr.exists() or lr.exists(): raise SystemExit("refusing to reuse result or log root")
 subprocess.run(["docker","image","inspect",IMAGE],check=True,capture_output=True,text=True)
 lr.mkdir(parents=True); progress=lr/"pair_progress.json"; write_new(progress,{"status":"RUNNING","records":[]})
 records=[]
 for run_id in RUN_IDS:
  records.append(run_one(run_id,a.execution_tag,lr)); replace(progress,{"status":"RUNNING","records":records})
 complete=not any(x.get("infrastructure_failure") for x in records)
 equal=complete and norm(records[0])==norm(records[1])
 passed=bool(complete and equal and all(bool(x.get("pass_flag")) and x.get("primary_verdict")==EXPECTED_VERDICT and x.get("implementation_erratum")=="P4d.5b" and x.get("output_schema_contract_version")=="P4D-ACCEPTED-OUTPUT-CSV-1.1" for x in records))
 final={"schema_version":"CMAME-P4D5B-RAW-PAIR-PROGRESS-1.0","status":"RAW_EXECUTION_COMPLETE_PENDING_FULL_FILE_QA","pair_classification":"PASS" if passed else "FAIL","normalized_case_results_equal":equal,"records":records}; replace(progress,final); return 0 if passed else 2
if __name__=="__main__": raise SystemExit(main())
