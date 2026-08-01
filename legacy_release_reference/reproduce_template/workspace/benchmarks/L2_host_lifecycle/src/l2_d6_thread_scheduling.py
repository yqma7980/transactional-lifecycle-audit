"""L2-D6.0 thread-scheduling support-envelope benchmark.

The frozen D1 host is serial. This module audits that support boundary without
creating synthetic concurrency. Importing it performs no execution or writes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
import ast
import csv
import hashlib
import json
import math
from typing import Any

from .l2_host import HostControls, NewtonHost
from .l2_state import CommittedState, ElementData, MaterialData, canonical_hash
from .l2_variants import SafeTransactional


DESIGN_VERSION = "L2-D6.0"
HOST_VERSION = "L2-HOST-D6.0"
IMPLEMENTATION_STATUS = "IMPLEMENTED_NOT_EXECUTED"
FREEZE_SHA256 = "5495de0f6756d85bb6f870ae457c354b41e6983839e5ee3fe63ef0a77443bb2c"
CASE_MATRIX_SHA256 = "9a3b4d0c532fc95576509b63118df15896bec8a252dbaf8f68e441623056e40a"
EXPECTED_GATE = "PASS_SCHEDULING_ENVELOPE_OR_NOT_SUPPORTED"
EXPECTED_OUTCOME = "NOT_SUPPORTED_NO_PARALLEL_EXECUTION_PATH"
AUTHORIZED_CASES = ("L2-TH-01",)

EVENT_COLUMNS = (
    "case_id", "run_id", "ordinal", "event", "host_source_sha256",
    "host_declared_single_threaded", "thread_count_metadata_present",
    "parallel_backend_markers", "alternate_setting_supported",
    "synthetic_concurrency_executed", "force", "displacement", "reaction",
    "stress", "epsilon_p", "kappa", "accepted_version",
    "committed_state_fingerprint", "physical_checkpoint_fingerprint",
    "all_values_finite", "note",
)

COMPARISON_COLUMNS = (
    "case_id", "run_id", "host_source_hash_matches", "host_declared_single_threaded",
    "thread_count_is_metadata_only", "parallel_backend_absent",
    "alternate_setting_supported", "synthetic_concurrency_executed",
    "serial_reference_analytical_match", "serial_reference_committed_hash_exact",
    "serial_reference_physical_hash_exact", "all_values_finite",
    "primary_gate_classification", "observed_outcome", "pass_flag",
)


@dataclass(frozen=True)
class SchedulingCapability:
    host_source_sha256: str
    host_declared_single_threaded: bool
    thread_count_metadata_present: bool
    parallel_backend_markers: tuple[str, ...]
    alternate_setting_supported: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SerialReference:
    force: float
    displacement: float
    reaction: float
    stress: float
    epsilon_p: float
    kappa: float
    accepted_version: int
    committed_state_fingerprint: str
    physical_checkpoint_fingerprint: str

    @property
    def finite_values(self) -> tuple[float, ...]:
        return (self.force, self.displacement, self.reaction, self.stress, self.epsilon_p, self.kappa)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SchedulingComparison:
    host_source_hash_matches: bool
    host_declared_single_threaded: bool
    thread_count_is_metadata_only: bool
    parallel_backend_absent: bool
    alternate_setting_supported: bool
    synthetic_concurrency_executed: bool
    serial_reference_analytical_match: bool
    serial_reference_committed_hash_exact: bool
    serial_reference_physical_hash_exact: bool
    all_values_finite: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SchedulingCaseResult:
    design_version: str
    host_version: str
    implementation_status: str
    case_id: str
    run_id: str
    expected_gate_classification: str
    expected_observed_outcome: str
    primary_gate_classification: str
    observed_outcome: str
    pass_flag: bool
    capability: SchedulingCapability
    serial_reference: SerialReference
    comparison: SchedulingComparison
    events: tuple[dict[str, Any], ...]
    claim_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_frozen_design(root: Path) -> tuple[dict[str, Any], tuple[dict[str, str], ...]]:
    freeze_path = root / "L2_D6_execution_freeze.json"
    matrix_path = root / "L2_D6_thread_scheduling_case_matrix.csv"
    if _sha256(freeze_path) != FREEZE_SHA256:
        raise ValueError("L2-D6 freeze hash mismatch")
    if _sha256(matrix_path) != CASE_MATRIX_SHA256:
        raise ValueError("L2-D6 matrix hash mismatch")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    with matrix_path.open("r", encoding="utf-8", newline="") as handle:
        matrix = tuple(csv.DictReader(handle))
    if freeze.get("design_version") != DESIGN_VERSION or freeze.get("design_status") != "FROZEN_NOT_IMPLEMENTED":
        raise ValueError("L2-D6 frozen identity mismatch")
    if freeze.get("execution_authorized") is not False or freeze.get("results_exist") is not False:
        raise ValueError("L2-D6 execution boundary mismatch")
    if len(matrix) != 1 or matrix[0].get("case_id") != "L2-TH-01":
        raise ValueError("L2-D6 case matrix mismatch")
    return freeze, matrix


def inspect_scheduling_capability(root: Path, freeze: dict[str, Any]) -> SchedulingCapability:
    host_path = root / "src" / "l2_host.py"
    source = host_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    markers: set[str] = set()
    forbidden_modules = {"threading", "concurrent", "multiprocessing", "joblib"}
    forbidden_calls = {"Thread", "ThreadPoolExecutor", "ProcessPoolExecutor", "Process", "Pool"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in forbidden_modules:
                    markers.add(f"import:{alias.name}")
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in forbidden_modules:
            markers.add(f"from:{node.module}")
        elif isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in forbidden_calls:
                markers.add(f"call:{name}")
    expected_hash = freeze["preimplementation_support_audit"]["source_hashes"]["src/l2_host.py"]
    if _sha256(host_path) != expected_hash:
        raise ValueError("D1 host source changed after D6 freeze")
    declared = "Deterministic single-threaded Newton host for L2-D1." in source
    metadata = "thread_count: int = 1" in source and '"thread_count": self.controls.thread_count' in source
    return SchedulingCapability(
        host_source_sha256=_sha256(host_path),
        host_declared_single_threaded=declared,
        thread_count_metadata_present=metadata,
        parallel_backend_markers=tuple(sorted(markers)),
        alternate_setting_supported=bool(markers),
    )


def _configuration_hash() -> str:
    return canonical_hash({
        "design_version": DESIGN_VERSION,
        "host_version": HOST_VERSION,
        "material": MaterialData(),
        "element": ElementData(),
        "mode": "serial_health_reference_only",
    })


def _serial_reference(case_id: str, run_id: str) -> SerialReference:
    variant = SafeTransactional(MaterialData())
    host = NewtonHost(
        run_id=run_id,
        case_id=case_id,
        history_id="serial_health_reference",
        variant=variant,
        configuration_hash=_configuration_hash(),
        controls=HostControls(thread_count=1),
    )
    checkpoint = host.solve_increment(target_force=1.1, attempt_id="SERIAL_REFERENCE")
    return SerialReference(
        force=checkpoint.force,
        displacement=checkpoint.displacement,
        reaction=checkpoint.reaction,
        stress=checkpoint.stress,
        epsilon_p=checkpoint.epsilon_p,
        kappa=checkpoint.kappa,
        accepted_version=checkpoint.accepted_version,
        committed_state_fingerprint=checkpoint.committed_state_hash,
        physical_checkpoint_fingerprint=checkpoint.physical_hash,
    )


def _analytical_match(value: SerialReference, atol: float, rtol: float) -> bool:
    expected = {
        "force": Fraction(11, 10), "displacement": Fraction(21, 1000),
        "reaction": Fraction(11, 10), "stress": Fraction(11, 10),
        "epsilon_p": Fraction(1, 100), "kappa": Fraction(1, 100),
    }
    return all(math.isclose(getattr(value, key), float(target), abs_tol=atol, rel_tol=rtol) for key, target in expected.items())


def classify_scheduling_case(comparison: SchedulingComparison) -> tuple[str, str, bool]:
    unsupported_pass = all((
        comparison.host_source_hash_matches,
        comparison.host_declared_single_threaded,
        comparison.thread_count_is_metadata_only,
        comparison.parallel_backend_absent,
        not comparison.alternate_setting_supported,
        not comparison.synthetic_concurrency_executed,
        comparison.serial_reference_analytical_match,
        comparison.serial_reference_committed_hash_exact,
        comparison.serial_reference_physical_hash_exact,
        comparison.all_values_finite,
    ))
    if unsupported_pass:
        return EXPECTED_GATE, EXPECTED_OUTCOME, True
    return "FAIL_SCHEDULING_SUPPORT_ENVELOPE", "SUPPORT_AUDIT_INCONSISTENT", False


def execute_thread_scheduling_case(root: Path, case_id: str, run_id: str) -> SchedulingCaseResult:
    if case_id not in AUTHORIZED_CASES:
        raise ValueError(f"Unauthorized L2-D6 case: {case_id}")
    freeze, _ = load_frozen_design(root)
    capability = inspect_scheduling_capability(root, freeze)
    if capability.alternate_setting_supported:
        raise RuntimeError("Parallel support appeared after freeze; refreeze before parity execution")
    reference = _serial_reference(case_id, run_id)
    tolerances = freeze["tolerances"]
    finite_limit = float(tolerances["finite_absolute_limit"])
    comparison = SchedulingComparison(
        host_source_hash_matches=capability.host_source_sha256 == freeze["preimplementation_support_audit"]["source_hashes"]["src/l2_host.py"],
        host_declared_single_threaded=capability.host_declared_single_threaded,
        thread_count_is_metadata_only=capability.thread_count_metadata_present and not capability.parallel_backend_markers,
        parallel_backend_absent=not capability.parallel_backend_markers,
        alternate_setting_supported=capability.alternate_setting_supported,
        synthetic_concurrency_executed=False,
        serial_reference_analytical_match=_analytical_match(reference, float(tolerances["analytical_absolute"]), float(tolerances["analytical_relative"])),
        serial_reference_committed_hash_exact=reference.committed_state_fingerprint == freeze["formal_case_protocol"]["reference_runtime_committed_hash"],
        serial_reference_physical_hash_exact=reference.physical_checkpoint_fingerprint == freeze["formal_case_protocol"]["reference_runtime_physical_hash"],
        all_values_finite=all(math.isfinite(v) and abs(v) <= finite_limit for v in reference.finite_values),
    )
    gate, outcome, passed = classify_scheduling_case(comparison)
    base = {
        "case_id": case_id, "run_id": run_id,
        "host_source_sha256": capability.host_source_sha256,
        "host_declared_single_threaded": capability.host_declared_single_threaded,
        "thread_count_metadata_present": capability.thread_count_metadata_present,
        "parallel_backend_markers": ";".join(capability.parallel_backend_markers) or "NONE",
        "alternate_setting_supported": capability.alternate_setting_supported,
        "synthetic_concurrency_executed": False,
    }
    blank = {"force": None, "displacement": None, "reaction": None, "stress": None, "epsilon_p": None, "kappa": None, "accepted_version": None, "committed_state_fingerprint": "NA", "physical_checkpoint_fingerprint": "NA"}
    observed = {**reference.to_dict()}
    events = (
        {**base, **blank, "ordinal": 1, "event": "InspectSchedulingCapability", "all_values_finite": True, "note": "source_and_AST_support_probe"},
        {**base, **blank, "ordinal": 2, "event": "DeclineSyntheticAlternate", "all_values_finite": True, "note": "no_supported_parallel_execution_path"},
        {**base, **observed, "ordinal": 3, "event": "SerialReferenceAccepted", "all_values_finite": comparison.all_values_finite, "note": "host_health_control_not_thread_parity"},
        {**base, **observed, "ordinal": 4, "event": "ClassifySupportEnvelope", "all_values_finite": comparison.all_values_finite, "note": outcome},
    )
    return SchedulingCaseResult(
        design_version=DESIGN_VERSION,
        host_version=HOST_VERSION,
        implementation_status=IMPLEMENTATION_STATUS,
        case_id=case_id,
        run_id=run_id,
        expected_gate_classification=EXPECTED_GATE,
        expected_observed_outcome=EXPECTED_OUTCOME,
        primary_gate_classification=gate,
        observed_outcome=outcome,
        pass_flag=passed,
        capability=capability,
        serial_reference=reference,
        comparison=comparison,
        events=events,
        claim_boundary="NOT_SUPPORTED is not thread-safety, scheduling-invariance or performance validation.",
    )


__all__ = [
    "AUTHORIZED_CASES", "CASE_MATRIX_SHA256", "COMPARISON_COLUMNS", "DESIGN_VERSION",
    "EVENT_COLUMNS", "EXPECTED_GATE", "EXPECTED_OUTCOME", "FREEZE_SHA256", "HOST_VERSION",
    "SchedulingCapability", "SchedulingCaseResult", "SchedulingComparison", "SerialReference",
    "classify_scheduling_case", "execute_thread_scheduling_case", "inspect_scheduling_capability",
    "load_frozen_design",
]
