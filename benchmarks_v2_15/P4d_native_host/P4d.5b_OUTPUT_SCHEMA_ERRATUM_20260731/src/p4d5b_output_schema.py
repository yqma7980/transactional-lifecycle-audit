from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ERRATUM_VERSION = "P4d.5b"
OUTPUT_SCHEMA_CONTRACT_VERSION = "P4D-ACCEPTED-OUTPUT-CSV-1.1"
OUTPUT_FIELDS = (
    "accepted_index", "accepted_load_factor", "accepted_version",
    "selected_candidate_id", "primary_vector_hash",
    "committed_gamma_p_hash", "committed_alpha_hash", "residual_norm",
    "top_reaction", "bottom_reaction", "max_alpha",
    "plastic_point_count", "mesh_hash", "material_hash",
    "residual_version", "tangent_relation", "source_event",
    "source_load_factor",
)

def normalized_csv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed=set(OUTPUT_FIELDS)
    normalized=[]
    for index,row in enumerate(rows):
        extra=set(row)-allowed
        if extra:
            raise ValueError(f"row {index} contains undeclared output fields: {sorted(extra)}")
        normalized.append({field: row.get(field) for field in OUTPUT_FIELDS})
    return normalized

def write_corrected_output(store, directory: Path) -> dict[str,str]:
    from p4d_canonical import canonical_hash, file_sha256
    from p4d_io import OUTPUT_SCHEMA_VERSION, write_json_new
    if directory.exists():
        raise FileExistsError(f"refusing to overwrite accepted output directory {directory}")
    rows=normalized_csv_rows(store.rows)
    directory.mkdir(parents=True)
    csv_path=directory/"accepted_output.csv"
    json_path=directory/"accepted_output_provenance.json"
    with csv_path.open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(OUTPUT_FIELDS),extrasaction="raise")
        writer.writeheader(); writer.writerows(rows)
    write_json_new(json_path,{
        "schema_version":OUTPUT_SCHEMA_VERSION,
        "output_schema_contract_version":OUTPUT_SCHEMA_CONTRACT_VERSION,
        "implementation_erratum":ERRATUM_VERSION,
        "csv_fieldnames":list(OUTPUT_FIELDS),
        "row_count":len(store.rows),
        "invalid_injection_count":store.invalid_injection_count,
        "rejected_candidate_reachable":store.rejected_candidate_reachable(),
        "rows_sha256":canonical_hash(store.rows),
    })
    return {"csv_sha256":file_sha256(csv_path),"json_sha256":file_sha256(json_path)}

def augment_case_result(value: dict[str,Any]) -> dict[str,Any]:
    result=dict(value)
    result["base_implementation_version"]=value.get("implementation_version")
    result["implementation_erratum"]=ERRATUM_VERSION
    result["output_schema_contract_version"]=OUTPUT_SCHEMA_CONTRACT_VERSION
    return result

@dataclass
class InstalledErratum:
    output_class: type
    original_output_write: Any
    case_module: Any
    original_case_write_json: Any
    def restore(self) -> None:
        self.output_class.write=self.original_output_write
        self.case_module.write_json_new=self.original_case_write_json

def install_erratum(p4d2_root: Path) -> InstalledErratum:
    import sys
    for path in (p4d2_root/"src",p4d2_root/"oracle"):
        if str(path) not in sys.path: sys.path.insert(0,str(path))
    import p4d_io
    import p4d_cases
    output_class=p4d_io.AcceptedOutputStore
    original_output=output_class.write
    original_case_json=p4d_cases.write_json_new
    def corrected(self,directory): return write_corrected_output(self,Path(directory))
    def write_case_json(path,value):
        payload=augment_case_result(value) if Path(path).name=="case_result.json" else value
        return original_case_json(path,payload)
    output_class.write=corrected
    p4d_cases.write_json_new=write_case_json
    return InstalledErratum(output_class,original_output,p4d_cases,original_case_json)
