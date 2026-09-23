"""Read-only integrity and saved-result checks; no study code imports or reruns."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(test, message):
    if not test:
        raise ValueError(message)


def main():
    manifests = load('PROVENANCE_MANIFEST.json')
    for item in manifests:
        require(sha(ROOT / item['path']) == item['public_sha256'], item['path'])
    checksum_path = ROOT / 'SHA256SUMS.txt'
    if checksum_path.exists():
        for line in checksum_path.read_text().splitlines():
            expected, name = line.split('  ', 1)
            require(sha(ROOT / name) == expected, name)
    expected_ratios = {79: 2.1711461898692486, 94: 2.1639942817402056}
    checked = []
    for rank in (79, 94):
        base = f'retained/g4/r{rank:03d}/'
        native = load(base + 'FORMAL_NATIVE_RESULT.json')
        rows = native['rows']
        require(len(rows) == 12, 'native observations')
        require(sum(r['native_outcome'] == 'VIOLATED' for r in rows) == 3, 'native violations')
        require(sum(r['native_outcome'] == 'SATISFIED' for r in rows) == 9, 'normal observations')
        traces = load(base + 'methods/input.json')
        require(len(traces) == 12 and all(set(t) == {'context', 'samples'} for t in traces), 'input fields')
        common_hash = sha(ROOT / base / 'methods/input.json')
        results = []
        for i, arm in enumerate(('lcma', 'rich', 'rich', 'lcma'), 1):
            e = load(base + f'methods/E{i:02d}.json')
            require(e['arm'] == arm and e['input_sha256'] == common_hash, 'equal-information seal')
            require(len(e['results']) == 12, 'saved verdict count')
            require(sum(x['verdict'] == 'DETECTED' for x in e['results']) == 3, 'detected count')
            require(all(x['verdict'] == ('DETECTED' if r['native_outcome'] == 'VIOLATED' else 'INVARIANT')
                        for r, x in zip(rows, e['results'])), 'saved outcome correspondence')
            results.append(e['results'])
        require(all(r == results[0] for r in results), 'saved diagnostic parity')
        comparison = load(base + 'methods/COMPARISON.json')
        require(comparison['lcma_over_rich_pure_evaluator_time_ratio'] == expected_ratios[rank], 'timing ratio')
        for arm in ('lcma', 'rich'):
            stats = comparison['arms'][arm]
            require(stats['detected_violations'] == 3 and stats['false_alarms'] == 0, 'comparison counts')
        require(comparison['native_processes'] == 12 and comparison['method_processes'] == 4, 'process counts')
        checked.append({'rank':rank, 'observations':12, 'detection':'3/3 vs 3/3',
                        'normal_false_positives':'0/9 vs 0/9', 'saved_time_ratio':expected_ratios[rank]})
    click = load('retained/heldout/frame02/cases/click_412/successor_01/BINDING_ADJUDICATION.json')
    require(click['decision'] == 'CONTRACT_BINDING_HOLD' and not click['native_execution_released'], 'Click HOLD')
    ledger = load('retained/heldout/frame02/H2_CANDIDATE_LEDGER.json')
    trio = next(p for p in ledger['projects'] if p['repository'] == 'python-trio/trio')
    require(any(c['decision'] == 'PROVENANCE_HOLD_NO_AUTHORITATIVE_FIX_FIRST_PARENT'
                for c in trio['candidates']), 'Trio HOLD')
    for mode in ('normal', 'optimized'):
        qa = load(f'retained/review/g4_preflight_02/qa_{mode}_01/work/QA.json')
        require(qa['passed_checks'] == 803 and qa['failed_checks'] == 2 and not qa['passed'], 'retained negatives')
        require(all('depth_1500' in f['name'] for f in qa['failures']), 'negative identity')
    print(json.dumps({'archive_integrity':'PASS', 'retained_files_checked':len(manifests),
        'saved_evidence':checked, 'Click':'CONTRACT_BINDING_HOLD',
        'Trio':'PROVENANCE_HOLD_NO_AUTHORITATIVE_FIX_FIRST_PARENT',
        'new_study_executions':0, 'scope':'saved-record verification, not native reproduction'}, indent=2))


if __name__ == '__main__':
    main()
