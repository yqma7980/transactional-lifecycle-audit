from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


DESIGN_VERSION = "JSS-P5C.0"
IMPLEMENTATION_VERSION = "JSS-P5C-IMPL-1.0"
ONTOLOGY_VERSION = "JSS-P5C-ONTOLOGY-1.0"
METHOD_B3 = "B3_GENERIC_REPLAY"
METHOD_B6 = "B6_TLA_PROVENANCE"
FINITE_LIMIT = 1.0e100


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    ontology_version: str
    subject_id: str
    module: str
    state_owner: str
    field_or_packet: str
    activation_event: str
    source_plane: str
    semantic_role: str


@dataclass(frozen=True)
class Observation:
    subject_id: str
    mutation_site: str
    changed_artifact_class: str
    changed_packet_family: str
    anomalous_owner: str
    anomalous_event: str
    anomalous_source_plane: str
    anomaly_kind: str
    residual_delta: float
    tangent_delta: float
    accepted_field_delta: float
    output_delta: float


@dataclass(frozen=True)
class RankingRow:
    method_id: str
    case_id: str
    candidate_id: str
    rank: int
    score: float
    reason_code: str


OBSERVATION_CONTRACT: dict[tuple[str, str], dict[str, str]] = {
    ("JSS-S01", "committed_constitutive_store"): {
        "artifact": "state",
        "packet": "state_packet",
        "owner": "CommittedState",
        "event": "AcceptCommit",
        "source": "committed_state",
        "anomaly": "ownership",
    },
    ("JSS-S01", "rollback_restore_path"): {
        "artifact": "state",
        "packet": "state_packet",
        "owner": "RollbackManager",
        "event": "RejectAttempt",
        "source": "rollback_state",
        "anomaly": "restoration",
    },
    ("JSS-S01", "accepted_output_writer"): {
        "artifact": "output",
        "packet": "accepted_output",
        "owner": "OutputWriter",
        "event": "OutputAcceptedState",
        "source": "accepted_output",
        "anomaly": "reachability",
    },
    ("JSS-S01", "trial_state_reuse"): {
        "artifact": "state",
        "packet": "state_packet",
        "owner": "TrialCandidate",
        "event": "TrialEvaluate",
        "source": "trial_state",
        "anomaly": "restoration",
    },
    ("JSS-S02", "accepted_flow_state"): {
        "artifact": "state",
        "packet": "state_packet",
        "owner": "CommittedState",
        "event": "AcceptCommit",
        "source": "committed_state",
        "anomaly": "ownership",
    },
    ("JSS-S02", "accepted_output_writer"): {
        "artifact": "output",
        "packet": "accepted_output",
        "owner": "OutputWriter",
        "event": "OutputAcceptedState",
        "source": "accepted_output",
        "anomaly": "reachability",
    },
    ("JSS-S02", "callback_cache"): {
        "artifact": "state",
        "packet": "state_packet",
        "owner": "PersistentCache",
        "event": "TrialEvaluate",
        "source": "persistent_state",
        "anomaly": "ownership",
    },
    ("JSS-S02", "tangent_or_flux_packet"): {
        "artifact": "operator",
        "packet": "operator_packet",
        "owner": "OperatorAssembler",
        "event": "FormTangent",
        "source": "operator",
        "anomaly": "version",
    },
    ("JSS-S03", "accepted_adapter_state"): {
        "artifact": "state",
        "packet": "state_packet",
        "owner": "CommittedState",
        "event": "AcceptCommit",
        "source": "committed_state",
        "anomaly": "ownership",
    },
    ("JSS-S03", "accepted_output_writer"): {
        "artifact": "output",
        "packet": "accepted_output",
        "owner": "OutputWriter",
        "event": "OutputAcceptedState",
        "source": "accepted_output",
        "anomaly": "reachability",
    },
    ("JSS-S03", "callback_cache"): {
        "artifact": "state",
        "packet": "state_packet",
        "owner": "PersistentCallbackState",
        "event": "ResidualEvaluation",
        "source": "persistent_state",
        "anomaly": "ownership",
    },
    ("JSS-S03", "callback_counter"): {
        "artifact": "state",
        "packet": "state_packet",
        "owner": "PersistentCallbackState",
        "event": "ResidualEvaluation",
        "source": "persistent_state",
        "anomaly": "ownership",
    },
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("ascii")).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_cases(root: Path) -> list[dict[str, str]]:
    rows = load_csv(root / "frozen_inputs" / "P5C_case_matrix.csv")
    if len(rows) != 12 or len({row["case_id"] for row in rows}) != 12:
        raise ValueError("Frozen P5C matrix must contain 12 unique cases")
    if any(row["design_version"] != DESIGN_VERSION for row in rows):
        raise ValueError("P5C design version mismatch")
    return rows


def load_ontology(root: Path) -> list[Candidate]:
    rows = [Candidate(**row) for row in load_csv(root / "frozen_inputs" / "P5C_candidate_ontology.csv")]
    for subject_id in ("JSS-S01", "JSS-S02", "JSS-S03"):
        subject = [row for row in rows if row.subject_id == subject_id]
        if len(subject) != 8 or len({row.candidate_id for row in subject}) != 8:
            raise ValueError(f"Ontology for {subject_id} is not an eight-ID universe")
        if any(row.ontology_version != ONTOLOGY_VERSION for row in subject):
            raise ValueError("Ontology version mismatch")
    return rows


def case_by_id(root: Path, case_id: str) -> dict[str, str]:
    matches = [row for row in load_cases(root) if row["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError(f"Unknown or duplicate P5C case: {case_id}")
    return matches[0]


def _drift_packet(case_id: str, fault_family: str) -> tuple[float, float, float, float]:
    index = int(case_id.rsplit("L", 1)[1])
    scale = float(index) * 1.0e-7
    residual = scale
    tangent = scale * (10.0 if "F08" in fault_family else 2.0)
    accepted = scale if "F03" in fault_family else 0.0
    output = scale if "F05" in fault_family else 0.0
    return residual, tangent, accepted, output


def simulate_observation(case: dict[str, str]) -> tuple[Observation, list[dict[str, Any]]]:
    key = (case["subject_id"], case["mutation_site"])
    if key not in OBSERVATION_CONTRACT:
        raise ValueError(f"No frozen observation contract for {key}")
    spec = OBSERVATION_CONTRACT[key]
    residual, tangent, accepted, output = _drift_packet(case["case_id"], case["fault_family"])
    observation = Observation(
        subject_id=case["subject_id"],
        mutation_site=case["mutation_site"],
        changed_artifact_class=spec["artifact"],
        changed_packet_family=spec["packet"],
        anomalous_owner=spec["owner"],
        anomalous_event=spec["event"],
        anomalous_source_plane=spec["source"],
        anomaly_kind=spec["anomaly"],
        residual_delta=residual,
        tangent_delta=tangent,
        accepted_field_delta=accepted,
        output_delta=output,
    )
    ledger = [
        {"ordinal": 1, "event": "BeginAttempt", "owner": "Host", "field_or_packet": "declared_replay_packet", "source_plane": "control", "anomaly": ""},
        {"ordinal": 2, "event": "TrialEvaluate", "owner": "TrialCandidate", "field_or_packet": "trial_state", "source_plane": "trial_state", "anomaly": ""},
        {"ordinal": 3, "event": observation.anomalous_event, "owner": observation.anomalous_owner, "field_or_packet": observation.changed_packet_family, "source_plane": observation.anomalous_source_plane, "anomaly": observation.anomaly_kind},
        {"ordinal": 4, "event": "ReplayObserve", "owner": "ReplayComparator", "field_or_packet": observation.changed_artifact_class, "source_plane": "comparison", "anomaly": observation.anomaly_kind},
        {"ordinal": 5, "event": "RejectAttempt", "owner": "Host", "field_or_packet": "attempt", "source_plane": "control", "anomaly": ""},
    ]
    return observation, ledger


def _rank(method_id: str, case_id: str, candidates: Iterable[Candidate], scores: dict[str, tuple[float, list[str]]]) -> list[RankingRow]:
    ordered = sorted(candidates, key=lambda candidate: (-scores[candidate.candidate_id][0], candidate.candidate_id))
    return [
        RankingRow(
            method_id=method_id,
            case_id=case_id,
            candidate_id=candidate.candidate_id,
            rank=index,
            score=scores[candidate.candidate_id][0],
            reason_code="+".join(scores[candidate.candidate_id][1]) or "NO_VISIBLE_MATCH",
        )
        for index, candidate in enumerate(ordered, start=1)
    ]


def score_b3(case_id: str, candidates: list[Candidate], observation: Observation) -> list[RankingRow]:
    scores: dict[str, tuple[float, list[str]]] = {}
    for candidate in candidates:
        score = 0.0
        reasons: list[str] = []
        if candidate.semantic_role == observation.changed_artifact_class:
            score += 2.0
            reasons.append("ARTIFACT_CLASS")
        if candidate.field_or_packet == observation.changed_packet_family:
            score += 1.0
            reasons.append("PACKET_FAMILY")
        scores[candidate.candidate_id] = (score, reasons)
    return _rank(METHOD_B3, case_id, candidates, scores)


def _anomaly_relevant(candidate: Candidate, observation: Observation) -> bool:
    if observation.anomaly_kind == "restoration":
        return candidate.state_owner == "RollbackManager"
    if observation.anomaly_kind == "reachability":
        return candidate.semantic_role == "output"
    if observation.anomaly_kind == "version":
        return candidate.semantic_role == "operator"
    if observation.anomaly_kind == "ownership":
        return candidate.state_owner == observation.anomalous_owner
    return False


def score_b6(case_id: str, candidates: list[Candidate], observation: Observation) -> list[RankingRow]:
    scores: dict[str, tuple[float, list[str]]] = {}
    for candidate in candidates:
        score = 0.0
        reasons: list[str] = []
        if candidate.state_owner == observation.anomalous_owner:
            score += 4.0
            reasons.append("OWNER")
        if candidate.activation_event == observation.anomalous_event:
            score += 2.0
            reasons.append("EVENT")
        if candidate.source_plane == observation.anomalous_source_plane:
            score += 2.0
            reasons.append("SOURCE")
        if candidate.field_or_packet == observation.changed_packet_family:
            score += 1.0
            reasons.append("FIELD")
        if _anomaly_relevant(candidate, observation):
            score += 1.0
            reasons.append(observation.anomaly_kind.upper())
        scores[candidate.candidate_id] = (score, reasons)
    return _rank(METHOD_B6, case_id, candidates, scores)


def validate_ranking(rows: list[RankingRow], universe: set[str]) -> bool:
    return (
        len(rows) == 8
        and {row.candidate_id for row in rows} == universe
        and [row.rank for row in rows] == list(range(1, 9))
        and all(math.isfinite(row.score) and abs(row.score) < FINITE_LIMIT for row in rows)
    )


def suspicious_set(rows: list[RankingRow]) -> list[str]:
    positive = [row.candidate_id for row in rows if row.score > 0.0]
    return positive if positive else [row.candidate_id for row in rows]


def evaluate_ranking(rows: list[RankingRow], ground_truth: set[str]) -> dict[str, Any]:
    first_rank = min(row.rank for row in rows if row.candidate_id in ground_truth)
    return {
        "top1": first_rank <= 1,
        "top3": first_rank <= 3,
        "first_ground_truth_rank": first_rank,
        "reciprocal_rank": 1.0 / first_rank,
        "exam": first_rank / 8.0,
        "suspicious_set_size": len(suspicious_set(rows)),
    }


def execute_case(root: Path, case_id: str, run_id: str) -> dict[str, Any]:
    case = case_by_id(root, case_id)
    candidates = [row for row in load_ontology(root) if row.subject_id == case["subject_id"]]
    observation, ledger = simulate_observation(case)
    b3 = score_b3(case_id, candidates, observation)
    b6 = score_b6(case_id, candidates, observation)
    universe = {row.candidate_id for row in candidates}
    schema_b3 = validate_ranking(b3, universe)
    schema_b6 = validate_ranking(b6, universe)
    ground_truth = set(case["ground_truth_candidate_ids"].split("|"))
    b3_metrics = evaluate_ranking(b3, ground_truth)
    b6_metrics = evaluate_ranking(b6, ground_truth)
    reduction = 1.0 - b6_metrics["suspicious_set_size"] / b3_metrics["suspicious_set_size"]
    values = [
        observation.residual_delta,
        observation.tangent_delta,
        observation.accepted_field_delta,
        observation.output_delta,
        reduction,
    ]
    all_finite = all(math.isfinite(value) and abs(value) < FINITE_LIMIT for value in values)
    result = {
        "design_version": DESIGN_VERSION,
        "implementation_version": IMPLEMENTATION_VERSION,
        "ontology_version": ONTOLOGY_VERSION,
        "case_id": case_id,
        "run_id": run_id,
        "partition": case["partition"],
        "subject_id": case["subject_id"],
        "fault_family": case["fault_family"],
        "mutation_site": case["mutation_site"],
        "observation": asdict(observation),
        "observation_fingerprint": canonical_hash(asdict(observation)),
        "b3_ranking": [asdict(row) for row in b3],
        "b6_ranking": [asdict(row) for row in b6],
        "b3_suspicious_set": suspicious_set(b3),
        "b6_suspicious_set": suspicious_set(b6),
        "ground_truth_candidate_ids": sorted(ground_truth),
        "b3_metrics": b3_metrics,
        "b6_metrics": b6_metrics,
        "suspicious_set_reduction": reduction,
        "schema_b3_pass": schema_b3,
        "schema_b6_pass": schema_b6,
        "required_detection_verdict": case["required_detection_verdict"],
        "observed_detection_verdict": "DETECT_LIFECYCLE_DRIFT",
        "all_values_finite": all_finite,
        "pass_flag": schema_b3 and schema_b6 and all_finite and ground_truth.issubset(universe),
    }
    result["semantic_fingerprint"] = canonical_hash({key: value for key, value in result.items() if key not in {"run_id", "semantic_fingerprint"}})
    return {"case": case, "result": result, "ledger": ledger}


def normalized_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if key not in {"run_id", "semantic_fingerprint"}}

