from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

import p5_fe_history
from p5_quadrature_backend_erratum_v2 import P5QuadratureAwareFEHost


p5_fe_history.P5TransactionalFEHost = P5QuadratureAwareFEHost

import p5_case_executor
from p5_arithmetic_gpfix import build_element_contributions
from p5_fe_history_gatefix import run_p5_history_gateaware


p5_case_executor.build_element_contributions = build_element_contributions
p5_case_executor.run_p5_history = run_p5_history_gateaware
p5_case_executor.IMPLEMENTATION_VERSION = (
    "CMAME-P5.2d-FE-GP-GATE-AWARE-SWEEP"
)
p5_case_executor.HOST_VERSION = (
    "P4D-DOLFINX-PETSC-HOST-1.0+P5-AUDIT-ADAPTER-1.0d"
)

from p5_case_executor_gatefix import execute_case_gateaware
import run_p5 as frozen


p5_case_executor.execute_case = execute_case_gateaware


def main(argv=None) -> int:
    return frozen.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
