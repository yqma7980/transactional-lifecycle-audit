"""Seal authorized scope and unchanged core before any new-project exposure."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
BASE=ROOT.parent

def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()

def main():
    original=BASE/'M-2026-003_S09_COMPARISON_20260906/src/frozen_core.py'
    core=ROOT/'core/frozen_core.py'
    expected='ace349aa9a7750e7891acdf6ccbf1705cecc5bae3f3ec67fdbebb28f31e6fc13'
    if digest(core)!=expected or digest(original)!=expected:
        raise ValueError('Core authority mismatch')
    paths=[BASE/'M-2026-003_S10_BATCH02_G2G3_20260906_220323/runs/G4_20260907_174304',
           BASE/'M-2026-003_S10_G2G3_COMPLETION_20260907_124427/runs/G4_20260907_174304']
    if any(p.exists() for p in paths):raise ValueError('New native run identity reused')
    files=[original,core,ROOT/'governance/AUTHORIZED_SCOPE.md',Path(__file__)]
    files+=list((ROOT/'harness').glob('*.py'))
    seal=dict(utc=datetime.now(timezone.utc).isoformat(),stage='CORE_FROZEN_BEFORE_NEW_PROJECT_SELECTION',
              passed=True,files_sha256={str(p):digest(p) for p in files},
              allowed_new_native_directories=[str(p) for p in paths],
              original_core_sha256=expected,new_project_results_viewed=False,
              formal_native_runs=0,human_experiments_authorized=False,remote_publication_authorized=False)
    with (ROOT/'governance/CORE_AND_SCOPE_FREEZE.json').open('x',encoding='utf-8') as f:
        json.dump(seal,f,indent=2);f.write('\n')
    print(json.dumps(seal,indent=2))

if __name__=='__main__':main()
