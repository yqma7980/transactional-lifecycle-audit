"""Explicit extension identities; historical producers remain byte-identical."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
STAMP = 'G4_20260907_174304'
PYTHON = r'LOCAL_USER/AppData\Local\Programs\Python\Python312\python.exe'
OLD79 = WORKSPACE / 'M-2026-003_S10_BATCH02_G2G3_20260906_220323'
OLD94 = WORKSPACE / 'M-2026-003_S10_G2G3_COMPLETION_20260907_124427'
PRIOR = WORKSPACE / 'M-2026-003_S10_G2G3_RECOVERY_20260907_052246'
R94_REPORT = WORKSPACE / 'M-2026-003_S10_R094_G3_20260907_163900'
ORDERS = [
    ['before-trigger', 'after-control', 'after-trigger', 'before-control'],
    ['after-trigger', 'before-control', 'before-trigger', 'after-control'],
    ['before-control', 'after-trigger', 'after-control', 'before-trigger'],
]


def config(rank):
    if type(rank) is not int or rank not in (79, 94):
        raise ValueError('Only the two admitted existing projects may enter G4')
    anchor = OLD79 if rank == 79 else OLD94
    if rank == 79:
        adapter = anchor / 'harness/native_v2'
        lock = anchor / 'envs/r079/runtime_repair_02/CASE_ENVIRONMENT_LOCK.json'
        frozen = anchor / 'governance/frozen_protocols/r079'
        old_pilot = anchor / 'integration/r079_pilot_02'
        coordinator = anchor / 'harness/run_r079_pilot_v2.py'
    else:
        adapter = anchor / 'protocols/celery/r094_native_v4'
        lock = anchor / 'envs/r094/runtime_04/module_inventory_02/CASE_ENVIRONMENT_LOCK.json'
        frozen = PRIOR / 'governance/frozen_protocols/r094'
        old_pilot = anchor / 'integration/r094_pilot_01'
        coordinator = anchor / 'harness/run_r94_pilot_v3.py'
    return dict(rank=rank, anchor=anchor, adapter=adapter, lock=lock,
        native_runner=anchor / 'harness/bounded_runner_v4.py',
        frozen=frozen, old_pilot=old_pilot, coordinator=coordinator,
        out=ROOT / ('g4/r%03d' % rank), runs=anchor / 'runs' / STAMP,
        sequence_start=0 if rank == 79 else 1)
