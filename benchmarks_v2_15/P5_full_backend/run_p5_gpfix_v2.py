from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import p5_fe_history
from p5_quadrature_backend_erratum_v2 import (
    HOST_REVISION,
    IMPLEMENTATION_REVISION,
    P5QuadratureAwareFEHost,
)


p5_fe_history.P5TransactionalFEHost = P5QuadratureAwareFEHost

import p5_case_executor
import run_p5 as frozen


p5_case_executor.IMPLEMENTATION_VERSION = IMPLEMENTATION_REVISION
p5_case_executor.HOST_VERSION = HOST_REVISION


def main(argv=None) -> int:
    return frozen.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
