from __future__ import annotations

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import p5_fe_history
from p5_quadrature_backend_erratum_v2 import P5QuadratureAwareFEHost


p5_fe_history.P5TransactionalFEHost = P5QuadratureAwareFEHost

import p5_case_executor
from p5_arithmetic_gpfix import build_element_contributions
from p5_fe_history_gatefix import run_p5_history_gateaware


p5_case_executor.build_element_contributions = build_element_contributions
p5_case_executor.run_p5_history = run_p5_history_gateaware
p5_case_executor.IMPLEMENTATION_VERSION = "CMAME-P5.2d-TEST"
p5_case_executor.HOST_VERSION = "P5-GATE-AWARE-TEST-HOST"

from p5_case_executor_gatefix import execute_case_gateaware


THRESHOLDS = {
    metric_id: 2.2737367544323206e-13
    for metric_id in (
        "M_R",
        "M_J",
        "M_X",
        "M_GP",
        "M_ALPHA",
        "M_REACTION",
        "M_OUTPUT_W",
        "M_OUTPUT_R",
    )
}


class P5GateAwareExecutorTests(unittest.TestCase):
    def _execute(self, eta: float, index: int, run_id: str):
        with TemporaryDirectory(prefix="p5-gate-aware-") as temporary:
            result_directory = Path(temporary) / "case"
            result_directory.mkdir()
            result = execute_case_gateaware(
                case_id="P5-SCALE-F05-DEV",
                run_id=run_id,
                result_directory=result_directory,
                environment={"semantic_environment_hash": "TEST"},
                strength_index=index,
                eta=eta,
                thresholds=THRESHOLDS,
            )
            self.assertTrue((result_directory / "case_result.json").is_file())
            self.assertTrue((result_directory / "case_manifest.json").is_file())
            return result

    def test_last_known_quiet_level_retains_full_comparison(self):
        result = self._execute(
            eta=3.0517578125e-05,
            index=11,
            run_id="P5-GATE-LOW",
        )
        self.assertTrue(result["pass_flag"])
        self.assertTrue(result["conventional_quiet"])
        self.assertFalse(result["incomplete_history_present"])
        self.assertTrue(all(result["metric_comparison_available"].values()))
        self.assertEqual(
            result["observed_classification"],
            "SWEEP_OBSERVATION_READY_FOR_SELECTION",
        )

    def test_gate_failure_is_a_nonquiet_selectable_observation(self):
        result = self._execute(
            eta=0.000244140625,
            index=12,
            run_id="P5-GATE-HIGH",
        )
        self.assertTrue(result["pass_flag"])
        self.assertFalse(result["conventional_quiet"])
        self.assertTrue(result["incomplete_history_present"])
        self.assertFalse(result["accepted_output_length_equal"])
        self.assertFalse(
            result["metric_comparison_available"]["M_OUTPUT_W"]
        )
        self.assertIsNone(result["metric_distances"]["M_OUTPUT_W"])
        self.assertEqual(
            result["faulty_history"]["prerequisite_status"],
            "FAILED_NORMAL_MECHANICS_GATE",
        )
        self.assertEqual(
            result["observed_classification"],
            "SWEEP_NONQUIET_OBSERVATION_READY_FOR_SELECTION",
        )


if __name__ == "__main__":
    unittest.main()
