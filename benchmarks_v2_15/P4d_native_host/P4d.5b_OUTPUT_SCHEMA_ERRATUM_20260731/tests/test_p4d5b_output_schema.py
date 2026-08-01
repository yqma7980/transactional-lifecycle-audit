from __future__ import annotations
import csv,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT.parent; P4D2=BASE/"P4d.2_FULL_IMPLEMENTATION_20260731"
sys.path[:0]=[str(ROOT/"src"),str(P4D2/"src"),str(P4D2/"oracle")]
from p4d5b_output_schema import OUTPUT_FIELDS,augment_case_result,normalized_csv_rows,write_corrected_output
class Store:
 def __init__(self,rows): self.rows=rows; self.invalid_injection_count=1
 def rejected_candidate_reachable(self): return True
def normal():
 return {"accepted_index":1,"accepted_load_factor":0.04,"accepted_version":1,"selected_candidate_id":"a","primary_vector_hash":"p","committed_gamma_p_hash":"g","committed_alpha_hash":"q","residual_norm":0.0,"top_reaction":1.0,"bottom_reaction":-1.0,"max_alpha":0.0,"plastic_point_count":0,"mesh_hash":"m","material_hash":"k","residual_version":"R","tangent_relation":"EXACT_CURRENT","source_event":"AcceptCommit"}
class SchemaTests(unittest.TestCase):
 def test_frozen_field_count(self): self.assertEqual(len(OUTPUT_FIELDS),18); self.assertEqual(OUTPUT_FIELDS[-1],"source_load_factor")
 def test_normalization_preserves_rows_without_mutation(self):
  a=normal(); b=dict(a); b.update({"accepted_index":None,"accepted_load_factor":0.2,"source_event":"FailedAttemptTrial","source_load_factor":0.08}); before=[dict(a),dict(b)]; rows=normalized_csv_rows([a,b]); self.assertEqual([a,b],before); self.assertIsNone(rows[0]["source_load_factor"]); self.assertEqual(rows[1]["source_load_factor"],0.08)
 def test_unknown_field_rejected(self):
  a=normal(); a["unexpected"]=1
  with self.assertRaises(ValueError): normalized_csv_rows([a])
 def test_corrected_writer_and_provenance(self):
  a=normal(); b=dict(a); b.update({"accepted_index":None,"accepted_load_factor":0.2,"source_event":"FailedAttemptTrial","source_load_factor":0.08}); store=Store([a,b])
  with tempfile.TemporaryDirectory() as td:
   out=Path(td)/"accepted_output"; write_corrected_output(store,out)
   with (out/"accepted_output.csv").open(encoding="utf-8",newline="") as f: reader=csv.DictReader(f); rows=list(reader); self.assertEqual(tuple(reader.fieldnames),OUTPUT_FIELDS)
   self.assertEqual(rows[0]["source_load_factor"],""); self.assertEqual(rows[1]["source_load_factor"],"0.08")
   meta=json.loads((out/"accepted_output_provenance.json").read_text("utf-8")); self.assertEqual(meta["row_count"],2); self.assertEqual(meta["output_schema_contract_version"],"P4D-ACCEPTED-OUTPUT-CSV-1.1"); self.assertTrue(meta["rejected_candidate_reachable"])
   with self.assertRaises(FileExistsError): write_corrected_output(store,out)
 def test_case_result_metadata(self):
  x=augment_case_result({"implementation_version":"P4d.2","pass_flag":True}); self.assertEqual(x["base_implementation_version"],"P4d.2"); self.assertEqual(x["implementation_erratum"],"P4d.5b"); self.assertEqual(x["output_schema_contract_version"],"P4D-ACCEPTED-OUTPUT-CSV-1.1")
if __name__=="__main__": unittest.main()
