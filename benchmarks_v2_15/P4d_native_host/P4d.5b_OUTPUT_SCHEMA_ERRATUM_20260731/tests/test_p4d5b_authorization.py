from __future__ import annotations
import ast,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))
from p4d5b_protocol import case_authorized,pair_authorized,require_case_and_run,verify_protected_inputs,verify_retry_prerequisite
class AuthTests(unittest.TestCase):
 def test_case_double_lock(self):
  self.assertFalse(case_authorized(False,{"P4D5B_EXECUTION_AUTHORIZED":"YES"})); self.assertFalse(case_authorized(True,{})); self.assertTrue(case_authorized(True,{"P4D5B_EXECUTION_AUTHORIZED":"YES"}))
 def test_pair_double_lock(self):
  self.assertFalse(pair_authorized(False,{"P4D5B_PAIR_EXECUTION_AUTHORIZED":"YES"})); self.assertFalse(pair_authorized(True,{})); self.assertTrue(pair_authorized(True,{"P4D5B_PAIR_EXECUTION_AUTHORIZED":"YES"}))
 def test_only_output_case_and_two_runs(self):
  require_case_and_run("P4D-NC-OUTPUT-01","run_1"); require_case_and_run("P4D-NC-OUTPUT-01","run_2")
  with self.assertRaises(SystemExit): require_case_and_run("P4D-SAFE-RT-01","run_1")
  with self.assertRaises(SystemExit): require_case_and_run("P4D-NC-OUTPUT-01","run_3")
 def test_protected_hashes_and_prerequisite(self): self.assertGreaterEqual(len(verify_protected_inputs()),10); self.assertEqual(verify_retry_prerequisite(),"PASS_TWO_FRESH_PROCESS_FULL_FILE_QA")
 def test_runner_ast_and_locks(self):
  for name in ("run_p4d5b.py","run_p4d5b_pair.py"):
   text=(ROOT/name).read_text("utf-8"); ast.parse(text); self.assertIn('if __name__=="__main__"',text)
  pair_text=(ROOT/"run_p4d5b_pair.py").read_text("utf-8")
  self.assertIn("P4D5B_EXECUTION_AUTHORIZED",pair_text); self.assertIn("--network",pair_text); self.assertIn('"none"',pair_text)
 def test_no_formal_output_during_unit_tests(self): self.assertFalse((ROOT/"results").exists()); self.assertFalse((ROOT/"formal_execution_logs").exists())
if __name__=="__main__": unittest.main()
