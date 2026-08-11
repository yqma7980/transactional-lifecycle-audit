from __future__ import annotations

import ast
import json
from pathlib import Path


root = Path(__file__).resolve().parents[1]
python_files = (
    sorted(root.glob("src/**/*.py"))
    + sorted(root.glob("tests/*.py"))
    + [root / "run_p5b_preflight.py"]
)
for path in python_files:
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
json.loads(
    (root / "schemas" / "p5b_case_result.schema.json").read_text(
        encoding="utf-8"
    )
)
print(f"AST_PASS={len(python_files)}")
print("JSON_SCHEMA_PARSE_PASS=1")
