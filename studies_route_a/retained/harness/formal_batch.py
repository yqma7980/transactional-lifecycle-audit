"""Serial native and fresh-method dispatch under a separately bounded outer job."""
import sys
import time
import traceback
from datetime import datetime, timezone
sys.dont_write_bytecode = True
from g4_config import ROOT, PYTHON
from kit_io import read_json, write_json_new
from g4_native import verify, require
from bounded_runner_v4 import capture


def main():
    verify(read_json(ROOT / 'governance/G4_FORMAL_SEAL.json')['files_sha256'])
    started = time.monotonic()
    records = []
    try:
        for rank in (79, 94):
            for mode in ('run', 'recheck', 'methods'):
                remaining = 1800 - (time.monotonic() - started)
                require(remaining > 10, 'Combined formal dispatch budget exhausted')
                if mode == 'methods':
                    argv = [PYTHON, '-B', str(ROOT / 'harness/g4_methods.py'), str(rank)]
                else:
                    argv = [PYTHON, '-B', str(ROOT / 'harness/g4_native.py'), mode, str(rank)]
                path = ROOT / 'qa' / ('formal_r%03d_%s_01' % (rank, mode))
                record = capture(argv, path, cwd='work', timeout_seconds=min(900, remaining),
                    max_log_bytes=16777216)
                records.append(dict(rank=rank, mode=mode, process_record=str(path / 'process.json'),
                    status=record['status'], exit_code=record['exit_code']))
                print(rank, mode, record['status'], record['exit_code'], flush=True)
                require(record['status'] == 'COMPLETED' and record['exit_code'] == 0 and not record['cleanup_errors'],
                    'Formal stage failed; no silent retry')
        write_json_new(ROOT / 'g4/BATCH_RESULT.json', dict(passed=True, records=records,
            elapsed_seconds=time.monotonic()-started, independent_humans=0, production=False))
    except BaseException:
        write_json_new(ROOT / 'g4/BATCH_FAILURE.json', dict(utc=datetime.now(timezone.utc).isoformat(),
            passed=False, records=records, traceback=traceback.format_exc(),
            later_stages='NOT_RUN', silent_retries=0))
        raise


if __name__ == '__main__':
    main()
