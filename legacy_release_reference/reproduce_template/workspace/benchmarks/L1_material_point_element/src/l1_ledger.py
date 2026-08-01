"""Deterministic 40-column lifecycle ledger writer."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def bool_text(value: bool) -> str:
    return "true" if value else "false"


def float_hex(value: float | None) -> str:
    return "NA" if value is None else float(value).hex()


def decimal_text(value: float | None) -> str:
    return "NA" if value is None else format(float(value), ".17e")


class Ledger:
    def __init__(self, columns: list[str]) -> None:
        self.columns = columns
        self.rows: list[dict[str, Any]] = []

    def append(self, **values: Any) -> dict[str, Any]:
        unknown = sorted(set(values) - set(self.columns))
        if unknown:
            raise ValueError(f"Unknown ledger columns: {unknown}")
        row = {name: values.get(name, "NA") for name in self.columns}
        missing = [name for name, value in row.items() if value is None]
        if missing:
            raise ValueError(f"Ledger fields may not be None: {missing}")
        self.rows.append(row)
        return row

    def write(self, path: Path) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(self.rows)
