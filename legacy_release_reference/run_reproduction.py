from __future__ import annotations
import argparse, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument("--execute-authorized",action="store_true");p.add_argument("--run-id",required=True);p.add_argument("--run-root",type=Path)
a=p.parse_args()
if not a.execute_authorized or os.environ.get("TSM_RELEASE_EXECUTION_AUTHORIZED")!="YES": raise SystemExit("dual authorization required")
target=(a.run_root.resolve() if a.run_root else ROOT/"local_runs"/a.run_id)
if target.exists(): raise SystemExit(f"refusing overwrite: {target}")
shutil.copytree(ROOT/"reproduce_template",target)
env=os.environ.copy();env["CR_D3_EXECUTION_AUTHORIZED"]="YES";env["PYTHONDONTWRITEBYTECODE"]="1";env["PYTHONHASHSEED"]="0"
for key in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):env[key]="1"
raise SystemExit(subprocess.run([sys.executable,str(target/"run_clean_rerun.py"),"--execute-authorized"],cwd=target,env=env,check=False).returncode)
