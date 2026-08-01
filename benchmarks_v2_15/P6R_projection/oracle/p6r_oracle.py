from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def load_post_detection_expectations(study_root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    """Load expectations only after detector outputs have been frozen."""
    path = study_root / "P6R_method_case_expectations.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {(row["case_id"], row["method_id"]): row for row in rows}


def compare_anomaly_flag(observed: bool | None, expected_text: str) -> bool:
    expected = {"YES": True, "NO": False, "NA": None}[expected_text]
    return observed is expected

