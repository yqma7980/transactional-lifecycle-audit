"""Append-only byte and reparse inventory for the four historical evidence anchors."""
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from g4_config import ROOT, OLD79, OLD94, PRIOR, R94_REPORT, STAMP
from kit_io import read_json, sha256, write_json_new

ANCHORS = (OLD79, OLD94, PRIOR, R94_REPORT)


def inventory():
    files, links = {}, {}
    for root in ANCHORS:
        if not root.is_dir():
            raise ValueError('Missing historical anchor: ' + str(root))
        for directory, dirs, names in os.walk(root, followlinks=False):
            for name in list(dirs) + names:
                p = Path(directory, name)
                if p.is_junction() or p.is_symlink():
                    links[str(p)] = os.readlink(p)
                    if name in dirs:
                        dirs.remove(name)
                elif p.is_file():
                    files[str(p)] = dict(bytes=p.stat().st_size, sha256=sha256(p))
    return dict(files=files, links=links)


def main(mode):
    before = ROOT / 'governance/HISTORICAL_BYTES_BEFORE.json'
    now = inventory()
    if mode == 'before':
        if any((p / 'runs' / STAMP).exists() for p in (OLD79, OLD94)):
            raise ValueError('Snapshot must precede the first new native process')
        write_json_new(before, dict(utc=datetime.now(timezone.utc).isoformat(), **now))
        print('Historical bytes sealed:', len(now['files']), 'links:', len(now['links']), flush=True)
        return
    old = read_json(before)
    changed = [p for p, v in old['files'].items() if now['files'].get(p) != v]
    new = sorted(set(now['files']) - set(old['files']))
    allowed = [p / 'runs' / STAMP for p in (OLD79, OLD94)]
    unexpected = [p for p in new if not any(Path(p).is_relative_to(a) for a in allowed)]
    result = dict(utc=datetime.now(timezone.utc).isoformat(),
        before_sha256=sha256(before), historical_files=len(old['files']),
        changed_or_missing=changed, unexpected_added=unexpected,
        authorized_added_files=new, reparse_entries_unchanged=now['links'] == old['links'],
        passed=not changed and not unexpected and now['links'] == old['links'])
    write_json_new(ROOT / 'qa/HISTORICAL_BYTES_AFTER.json', result)
    print(result['passed'], 'old files:', result['historical_files'], 'new native files:', len(new), flush=True)
    if not result['passed']:
        raise ValueError('Historical preservation failed')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('mode', choices=['before', 'after'])
    main(p.parse_args().mode)
