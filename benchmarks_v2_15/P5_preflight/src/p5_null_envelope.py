from __future__ import annotations

import csv
import itertools
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MACHINE_EPSILON = 2.220446049250313e-16
ABSOLUTE_FLOOR_MULTIPLIER = 1024
MARGIN_FACTOR = 10.0


@dataclass(frozen=True)
class MetricScale:
    metric_id: str
    scale: float
    relation: str


def load_metric_scales(path: Path) -> dict[str, MetricScale]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    result: dict[str, MetricScale] = {}
    for row in rows:
        if row["comparison_relation"] == "scaled_numeric":
            result[row["metric_id"]] = MetricScale(row["metric_id"], float(row["declared_scale"]), "scaled_numeric")
    if set(result) != {"M_R", "M_J", "M_X", "M_GP", "M_ALPHA", "M_REACTION", "M_OUTPUT_W", "M_OUTPUT_R"}:
        raise ValueError("metric scale registry mismatch")
    if any(item.scale <= 0.0 or not math.isfinite(item.scale) for item in result.values()):
        raise ValueError("metric scales must be positive and finite")
    return result


def _flatten(value: Any) -> list[float]:
    if isinstance(value, (list, tuple)):
        flattened: list[float] = []
        for item in value:
            flattened.extend(_flatten(item))
        return flattened
    return [float(value)]


def scaled_distance(left: Any, right: Any, scale: float) -> float:
    a = _flatten(left)
    b = _flatten(right)
    if len(a) != len(b) or not a:
        raise ValueError("metric packet shapes differ or are empty")
    if not all(math.isfinite(item) for item in a + b):
        raise ValueError("metric packet contains non-finite values")
    numerator = max(abs(x - y) for x, y in zip(a, b, strict=True))
    denominator = max(scale, max(abs(item) for item in a), max(abs(item) for item in b))
    return numerator / denominator


def complete_pairwise_envelope(records: Sequence[Mapping[str, Any]], scales: Mapping[str, MetricScale]) -> dict[str, float]:
    if len(records) < 2:
        raise ValueError("at least two fresh-process records are required")
    envelopes = {metric_id: 0.0 for metric_id in scales}
    for left, right in itertools.combinations(records, 2):
        for metric_id, metric in scales.items():
            envelopes[metric_id] = max(envelopes[metric_id], scaled_distance(left[metric_id], right[metric_id], metric.scale))
    return envelopes


def thresholds(envelopes: Mapping[str, float]) -> dict[str, float]:
    floor = ABSOLUTE_FLOOR_MULTIPLIER * MACHINE_EPSILON
    return {metric_id: max(floor, MARGIN_FACTOR * float(value)) for metric_id, value in envelopes.items()}


def confirm_record(reference: Mapping[str, Any], confirmation: Mapping[str, Any], scales: Mapping[str, MetricScale], frozen_thresholds: Mapping[str, float]) -> dict[str, float]:
    distances = {
        metric_id: scaled_distance(reference[metric_id], confirmation[metric_id], metric.scale)
        for metric_id, metric in scales.items()
    }
    if any(distances[key] > frozen_thresholds[key] for key in distances):
        raise ValueError("null confirmation exceeds a frozen threshold")
    return distances


def _balanced(values: list[float]) -> float:
    work = list(values)
    while len(work) > 1:
        paired = [work[index] + work[index + 1] for index in range(0, len(work) - 1, 2)]
        if len(work) % 2:
            paired.append(work[-1])
        work = paired
    return work[0]


def reduce_values(values: Iterable[float], path_id: str) -> float:
    data = [float(item) for item in values]
    if not data:
        raise ValueError("empty reduction")
    if path_id == "ARITH_A_REFERENCE":
        total = 0.0
        for item in data:
            total += item
        return total
    if path_id == "ARITH_B_CALIBRATION":
        blocks = [data[index:index + 8] for index in range(0, len(data), 8)]
        return sum(sum(reversed(block)) for block in blocks)
    if path_id == "ARITH_C_CONFIRMATION":
        return _balanced(data)
    if path_id == "ARITH_D_P6_BENIGN":
        return _balanced(data[1::2] + data[0::2])
    raise ValueError(f"unknown arithmetic path {path_id}")
