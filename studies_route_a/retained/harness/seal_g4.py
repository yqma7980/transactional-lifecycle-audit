"""Admit only the exact nonauthor-reviewed implementation before native exposure."""
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.dont_write_bytecode = True
from g4_config import ROOT, config
from kit_io import read_json, sha256, write_json_new
from g4_native import require, verify
from lcma_arm import contract


def main():
    path = ROOT / 'review/g4_preflight_02/G4_PREFLIGHT_REVIEW.json'
    review = read_json(path)
    require(review['passed'] is True and type(review['open_acceptance_blockers']) is int and
            review['open_acceptance_blockers'] == 0, 'Nonauthor review not passed')
    verify(review['reviewed_files_sha256'])
    handoff_path = ROOT / 'baseline/INDEPENDENT_BASELINE_HANDOFF.json'
    handoff = read_json(handoff_path)
    selected = Path(handoff['selected_module']['path'])
    require(handoff['executedtests']['selected_run']['passed'] is True, 'Baseline tests not passed')
    require(sha256(selected) == handoff['selected_module']['sha256'], 'Selected baseline changed')
    mandatory = [ROOT / 'harness' / n for n in ('g4_native.py','g4_config.py','g4_methods.py',
        'formal_batch.py','projection.py','lcma_arm.py','evaluate_arm.py')]
    mandatory += [ROOT / 'core/frozen_core.py', selected]
    normalized_review = {str(Path(p).resolve()):h for p,h in review['reviewed_files_sha256'].items()}
    for p in mandatory:
        require(normalized_review.get(str(p.resolve())) == sha256(p), 'Current implementation not reviewed: ' + str(p))
    require(sha256(ROOT / 'core/frozen_core.py') ==
        'ace349aa9a7750e7891acdf6ccbf1705cecc5bae3f3ec67fdbebb28f31e6fc13', 'Core changed')
    historical = read_json(ROOT / 'governance/HISTORICAL_BYTES_BEFORE.json')
    verify({p:v['sha256'] for p,v in historical['files'].items()})
    for rank in (79,94):
        c = config(rank)
        require(not c['runs'].exists(), 'Seal cannot follow new native observations')
        require(not (c['out'] / 'FORMAL_START.json').exists(), 'Formal evidence already exposed')
        plan = read_json(c['out'] / 'CASE_PLAN.json')
        verify(plan['files_sha256'])
        require(len(plan['cells']) == 12 and plan['rank'] == rank, 'Wrong case plan')
        write_json_new(ROOT / ('contracts/R%03d.json' % rank), contract(rank))
    files = {}
    for sub in ('harness', 'core', 'tests'):
        files.update({str(p):sha256(p) for p in (ROOT / sub).glob('*.py')})
    files.update({str(p):sha256(p) for p in (ROOT / 'contracts').glob('*') if p.is_file()})
    files.update({str(p):sha256(p) for p in selected.parent.glob('*.py')})
    for p in (path, handoff_path, ROOT / 'governance/AUTHORIZED_SCOPE.md',
              ROOT / 'governance/CORE_AND_SCOPE_FREEZE.json', ROOT / 'governance/HISTORICAL_BYTES_BEFORE.json',
              config(79)['out'] / 'CASE_PLAN.json', config(94)['out'] / 'CASE_PLAN.json'):
        files[str(p)] = sha256(p)
    write_json_new(ROOT / 'governance/G4_FORMAL_SEAL.json', dict(schema='M003-G4-FORMAL-SEAL-1',
        utc=datetime.now(timezone.utc).isoformat(), passed=True, native_runs_before_seal=0,
        reviewed_by_separate_ai=True, independent_humans=0, formal_native_runs_planned=24,
        method_processes_planned=8, new_independent_roots=0, new_project_holdout=False,
        original_core_sha256=sha256(ROOT / 'core/frozen_core.py'), files_sha256=files,
        selected_baseline=str(selected), local_content_seal_not_external_timestamp=True))
    print('G4 sealed before new native exposure; old evidence preserved.', flush=True)


if __name__ == '__main__':
    main()
