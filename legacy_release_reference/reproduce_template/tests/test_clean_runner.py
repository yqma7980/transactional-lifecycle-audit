from __future__ import annotations
import hashlib, importlib.util, json
from pathlib import Path
import subprocess, sys, unittest
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("cr_d3_runner",ROOT/"run_clean_rerun.py")
MODULE=importlib.util.module_from_spec(SPEC);assert SPEC.loader is not None;SPEC.loader.exec_module(MODULE)

class CleanRunnerD3Tests(unittest.TestCase):
 def test_snapshots(self):
  x=MODULE.verify_source_snapshots();self.assertEqual(x["current"]["file_count"],269);self.assertEqual(x["historical_l1_mp"]["file_count"],28);self.assertEqual(x["historical_l1_mp"]["implementation_hash"],"35c44ca1df498ac517c3c9a9b8f691ee0ce8a4293f52b8a0262afce8438a62a3")
 def test_matrix_dependency_envelope(self):
  rows=MODULE.load_matrix();expected=json.loads((ROOT/"CR_D3_expected_reference_manifest.json").read_text())["jobs"]
  self.assertEqual(len(rows),59);self.assertEqual({r["job_id"] for r in rows},set(expected));self.assertEqual(sum(r["layer"]=="L4" for r in rows),20);self.assertEqual(sum(r["layer"]=="PERF" for r in rows),6)
  for cid in {r["case_id"] for r in rows if r["layer"]=="L4"}:self.assertEqual({r["run_id"] for r in rows if r["case_id"]==cid},{"run_1","run_2"})
 def test_expected_l4_raw_aggregate(self):
  rows=MODULE.load_matrix();expected=json.loads((ROOT/"CR_D3_expected_reference_manifest.json").read_text())["jobs"];items=[]
  for row in rows:
   if row["layer"]!="L4":continue
   for name,digest in expected[row["job_id"]]["files"].items():items.append((f"{row['case_id']}/{row['run_id']}/{name}",digest))
  items.sort();self.assertEqual(len(items),100)
  aggregate=hashlib.sha256("\n".join(f"{path}|{digest}" for path,digest in items).encode()).hexdigest()
  self.assertEqual(aggregate,"ff25b0622dd8ce74a6a5d8d3f712df593e732a20918c4259c7fc0afb4539e78d")
 def test_l4_canonical_paths_precede_l5_xp(self):
  rows=MODULE.load_matrix();xp=next(i for i,r in enumerate(rows) if r["job_id"]=="CR-L5-D2-XP-01");l4=[(i,r) for i,r in enumerate(rows) if r["layer"]=="L4"]
  self.assertEqual(len(l4),20);self.assertTrue(all(i<xp for i,_ in l4));self.assertTrue(all(r["output_root_relative"].endswith("results/L4_D1_two_phase_displacement") for _,r in l4))
 def test_source_profile_dispatch(self):
  rows={r["job_id"]:r for r in MODULE.load_matrix()};mp,mpcwd,_=MODULE.build_command(rows["CR-L1-MP"]);e1,e1cwd,_=MODULE.build_command(rows["CR-L1-E1"])
  self.assertEqual(Path(mp[1]),MODULE.HISTORICAL_L1_MP/"run_l1_mp.py");self.assertEqual(mpcwd,MODULE.HISTORICAL_L1_MP);self.assertTrue(str(e1[1]).startswith(str(MODULE.CURRENT_WORKSPACE)));self.assertNotEqual(e1cwd,MODULE.HISTORICAL_L1_MP)
 def test_single_process_contract(self):
  for row in MODULE.load_matrix():
   if row["layer"]=="PERF":continue
   command,_,env=MODULE.build_command(row);self.assertEqual(command[0],sys.executable);self.assertEqual(env["OMP_NUM_THREADS"],"1");self.assertNotIn("abaqus"," ".join(command).lower());self.assertNotIn("comsol"," ".join(command).lower())
 def test_dual_authorization_refusal(self):
  p=subprocess.run([sys.executable,str(ROOT/"run_clean_rerun.py")],cwd=str(ROOT),capture_output=True,text=True,check=False);self.assertNotEqual(p.returncode,0)
  for name in ["outputs","logs","final","clean_failure.json"]:self.assertFalse((ROOT/name).exists())
 def test_expected_reference_no_absolute_paths(self):
  t=(ROOT/"CR_D3_expected_reference_manifest.json").read_text();self.assertNotIn("F:\\\\",t);self.assertNotIn("D:\\\\",t)
if __name__=="__main__":unittest.main()
