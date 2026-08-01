"""Frozen L5-D1 independent case dispatcher."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .l5_lifecycle import (
    IndependentSafeVariant,
    IndependentUnsafeVariant,
    accepted_output_probe,
    retry_comparison,
)
from .l5_oracle import independent_oracle
from .l5_solver import (
    all_finite,
    compare_reference,
    cumulative_defects,
    field_difference,
    normalized_defect,
    run_checkpoints,
    snapshot,
)
from .l5_state import (
    DESIGN_VERSION,
    HOST_VERSION,
    IndependentCandidate,
    IndependentCommitted,
    IndependentModel,
    binary_fingerprint,
)


METRIC_COLUMNS=(
 "case_id","run_id","row_type","level","profile_id","time","cell_count","cfl","dt",
 "saturation_l1","saturation_l2","pressure_l2_relative","pressure_linf",
 "displacement_absolute","front_location","front_absolute",
 "order_saturation","order_pressure","order_front","order_displacement",
 "step_mass_defect_n","step_mass_defect_w","cumulative_mass_defect_n",
 "cumulative_mass_defect_w","saturation_bounds_ok","note",
)
PROFILE_COLUMNS=(
 "case_id","run_id","profile_id","accepted_version","time","cell_index","x",
 "S_n","S_w","pressure","phase_mass_n","phase_mass_w","front_location",
 "displacement","committed_fingerprint","output_provenance_fingerprint",
)
EVENT_COLUMNS=(
 "case_id","run_id","ordinal","history_id","event","variant","accepted","time","dt",
 "committed_fingerprint","candidate_fingerprint","persistent_fingerprint",
 "candidate_reachable","output_provenance_fingerprint","minimum_saturation_n",
 "maximum_saturation_n","minimum_pressure","maximum_pressure","phase_mass_n",
 "phase_mass_w","front_location","displacement","mass_defect_n","mass_defect_w",
 "finite","note",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_design(root: Path) -> tuple[dict[str,Any],dict[str,dict[str,str]]]:
    base=root/"benchmarks"/"L5_independent_validation"
    freeze=json.loads((base/"L5_D1_execution_freeze.json").read_text(encoding="utf-8"))
    with (base/"L5_D0_case_matrix.csv").open(encoding="utf-8",newline="") as handle:
        rows=list(csv.DictReader(handle))
    matrix={row["case_id"]:row for row in rows}
    if freeze["design_version"]!=DESIGN_VERSION or set(matrix)!=set(freeze["formal_cases"]):
        raise RuntimeError("L5 freeze/matrix mismatch")
    return freeze,matrix


def _blank(columns: tuple[str,...],**values: Any) -> dict[str,Any]:
    row={column:"NA" for column in columns}
    row.update(values)
    return row


def _profile_rows(
    case_id: str,run_id: str,profile_id: str,
    model: IndependentModel,state: IndependentCommitted,
) -> list[dict[str,Any]]:
    view=snapshot(model,state)
    dx=model.length/len(state.saturation_n)
    return [
        {
            "case_id":case_id,"run_id":run_id,"profile_id":profile_id,
            "accepted_version":state.accepted_version,"time":state.time,
            "cell_index":index,"x":(index+0.5)*dx,
            "S_n":saturation,"S_w":1.0-saturation,"pressure":pressure,
            "phase_mass_n":view.phase_mass_n,"phase_mass_w":view.phase_mass_w,
            "front_location":view.front_location,"displacement":view.displacement,
            "committed_fingerprint":state.fingerprint,
            "output_provenance_fingerprint":view.fingerprint,
        }
        for index,(saturation,pressure) in enumerate(zip(view.saturation_n,view.pressure))
    ]


def _state_from_candidate(candidate: IndependentCandidate,version: int) -> IndependentCommitted:
    return IndependentCommitted(
        time=candidate.time,saturation_n=candidate.saturation_n,
        cumulative_n_in=candidate.cumulative_n_in,cumulative_n_out=candidate.cumulative_n_out,
        cumulative_w_in=candidate.cumulative_w_in,cumulative_w_out=candidate.cumulative_w_out,
        accepted_version=version,
    )


def _event_candidate(
    case_id: str,run_id: str,ordinal: int,model: IndependentModel,
    candidate: IndependentCandidate,note: str,
) -> dict[str,Any]:
    state=_state_from_candidate(candidate,ordinal)
    view=snapshot(model,state)
    finite=all_finite((*candidate.finite_values,*view.pressure,view.displacement))
    return {
        "case_id":case_id,"run_id":run_id,"ordinal":ordinal,
        "history_id":"PHYSICAL","event":"AcceptIncrement",
        "variant":"independent_MUSCL_SSPRK2","accepted":True,
        "time":candidate.time,"dt":candidate.dt,
        "committed_fingerprint":state.fingerprint,
        "candidate_fingerprint":candidate.fingerprint,
        "persistent_fingerprint":"NA","candidate_reachable":False,
        "output_provenance_fingerprint":view.fingerprint,
        "minimum_saturation_n":min(candidate.saturation_n),
        "maximum_saturation_n":max(candidate.saturation_n),
        "minimum_pressure":min(view.pressure),"maximum_pressure":max(view.pressure),
        "phase_mass_n":view.phase_mass_n,"phase_mass_w":view.phase_mass_w,
        "front_location":view.front_location,"displacement":view.displacement,
        "mass_defect_n":candidate.declared_n_mass_defect,
        "mass_defect_w":candidate.declared_w_mass_defect,
        "finite":finite,"note":note,
    }


def _orders(values: list[float]) -> tuple[float,float]:
    if len(values)!=3 or any(value<=0.0 for value in values):
        raise RuntimeError("three positive errors required")
    return math.log(values[0]/values[1],2.0),math.log(values[1]/values[2],2.0)


def _base(case_id: str,run_id: str,expected: str) -> dict[str,Any]:
    return {
        "design_version":DESIGN_VERSION,"host_version":HOST_VERSION,
        "case_id":case_id,"run_id":run_id,
        "expected_classification":expected,
        "processes":1,"threads":1,"abaqus_used":False,
        "production_model_used":False,"l4_implementation_imported":False,
        "two_way_flow_mechanics":False,"capillary_pressure":False,
    }


def _reference(case_id,run_id,freeze,expected):
    model=IndependentModel(); times=tuple(freeze["times"]["reference"])
    states,candidates=run_checkpoints(model,800,0.35,times)
    metrics=[]; profiles=[]; events=[]; passed=True
    for level,time in enumerate(times,1):
        state=states[time]; view=snapshot(model,state)
        oracle=independent_oracle(800,time)
        value=compare_reference(model,view,oracle)
        passed &= (
            value.saturation_l1<=freeze["tolerances"]["reference_saturation_l1"]
            and value.front_absolute<=freeze["tolerances"]["reference_front_absolute"]
            and value.pressure_l2_relative<=freeze["tolerances"]["reference_pressure_l2_relative"]
            and value.pressure_linf<=freeze["tolerances"]["reference_pressure_linf"]
            and value.displacement_absolute<=freeze["tolerances"]["one_way_displacement_absolute"]
            and value.oracle_root_residual<=1e-13
            and value.oracle_mass_identity_error<=1e-12
        )
        metrics.append(_blank(METRIC_COLUMNS,case_id=case_id,run_id=run_id,row_type="reference",level=level,profile_id=f"reference_{time}",time=time,cell_count=800,cfl=0.35,dt=0.35/1600.0,saturation_l1=value.saturation_l1,saturation_l2=value.saturation_l2,pressure_l2_relative=value.pressure_l2_relative,pressure_linf=value.pressure_linf,displacement_absolute=value.displacement_absolute,front_location=view.front_location,front_absolute=value.front_absolute,note="independent_entropy_Gauss8"))
        profiles.extend(_profile_rows(case_id,run_id,f"reference_{time}",model,state))
        candidate=min(candidates,key=lambda item:abs(item.time-time))
        events.append(_event_candidate(case_id,run_id,state.accepted_version,model,candidate,"reference_checkpoint"))
    result=_base(case_id,run_id,expected)
    result.update({"observed_classification":expected if passed else "FAIL_REFERENCE_GATE","pass_flag":bool(passed),"all_values_finite":all(row["finite"] for row in events),"metric_rows":len(metrics),"profile_rows":len(profiles),"event_rows":len(events)})
    return result,metrics,profiles,events


def _convergence(case_id,run_id,freeze,expected):
    model=IndependentModel(); target=float(freeze["times"]["convergence"])
    levels=(80,160,320); records=[]; profiles=[]; events=[]
    for level,n in enumerate(levels,1):
        states,candidates=run_checkpoints(model,n,0.35,(target,))
        state=states[target]; view=snapshot(model,state); oracle=independent_oracle(n,target)
        value=compare_reference(model,view,oracle)
        records.append((n,state,value))
        profiles.extend(_profile_rows(case_id,run_id,f"mesh_{n}",model,state))
        events.append(_event_candidate(case_id,run_id,level,model,candidates[-1],"convergence_endpoint"))
    sat_orders=_orders([r[2].saturation_l1 for r in records])
    pressure_orders=_orders([r[2].pressure_l2_relative for r in records])
    front_orders=_orders([r[2].front_absolute for r in records])
    displacement_orders=_orders([r[2].displacement_absolute for r in records])
    observed=min(*sat_orders,*pressure_orders,*front_orders,*displacement_orders)
    errors_decrease=all(
        values[0]>values[1]>values[2]
        for values in (
            [r[2].saturation_l1 for r in records],
            [r[2].pressure_l2_relative for r in records],
            [r[2].front_absolute for r in records],
            [r[2].displacement_absolute for r in records],
        )
    )
    passed=errors_decrease and observed>=freeze["tolerances"]["convergence_order_minimum"]
    metrics=[]
    for level,(n,state,value) in enumerate(records,1):
        metrics.append(_blank(METRIC_COLUMNS,case_id=case_id,run_id=run_id,row_type="convergence",level=level,profile_id=f"mesh_{n}",time=target,cell_count=n,cfl=0.35,dt=0.35/(2*n),saturation_l1=value.saturation_l1,saturation_l2=value.saturation_l2,pressure_l2_relative=value.pressure_l2_relative,pressure_linf=value.pressure_linf,displacement_absolute=value.displacement_absolute,front_location=snapshot(model,state).front_location,front_absolute=value.front_absolute,order_saturation=sat_orders[1] if level==3 else "NA",order_pressure=pressure_orders[1] if level==3 else "NA",order_front=front_orders[1] if level==3 else "NA",order_displacement=displacement_orders[1] if level==3 else "NA",note="independent_mesh_refinement"))
    result=_base(case_id,run_id,expected)
    result.update({"observed_classification":expected if passed else "FAIL_CONVERGENCE_GATE","pass_flag":bool(passed),"all_values_finite":True,"minimum_observed_order":observed,"saturation_orders":sat_orders,"pressure_orders":pressure_orders,"front_orders":front_orders,"displacement_orders":displacement_orders,"metric_rows":len(metrics),"profile_rows":len(profiles),"event_rows":len(events)})
    return result,metrics,profiles,events


def _mass(case_id,run_id,freeze,expected):
    model=IndependentModel(); target=float(freeze["times"]["mass"])
    states,candidates=run_checkpoints(model,256,0.35,(target,))
    state=states[target]; view=snapshot(model,state)
    step_n=max(normalized_defect(c.internal_n_mass_defect) for c in candidates)
    step_w=max(normalized_defect(c.internal_w_mass_defect) for c in candidates)
    cumulative=cumulative_defects(model,state)
    cumulative_n=normalized_defect(cumulative[0]); cumulative_w=normalized_defect(cumulative[1])
    bounds=min(state.saturation_n)>=freeze["tolerances"]["saturation_lower"] and max(state.saturation_n)<=freeze["tolerances"]["saturation_upper"]
    passed=max(step_n,step_w,cumulative_n,cumulative_w)<=freeze["tolerances"]["phase_mass_defect_maximum"] and bounds
    metrics=[_blank(METRIC_COLUMNS,case_id=case_id,run_id=run_id,row_type="phase_balance",level=1,profile_id="mass_endpoint",time=target,cell_count=256,cfl=0.35,dt=0.35/512.0,step_mass_defect_n=step_n,step_mass_defect_w=step_w,cumulative_mass_defect_n=cumulative_n,cumulative_mass_defect_w=cumulative_w,saturation_bounds_ok=bounds,note="both_phase_balance")]
    profiles=_profile_rows(case_id,run_id,"mass_endpoint",model,state)
    events=[_event_candidate(case_id,run_id,index,model,candidate,"mass_accepted") for index,candidate in enumerate(candidates,1)]
    result=_base(case_id,run_id,expected)
    result.update({"observed_classification":expected if passed else "FAIL_PHASE_BALANCE_GATE","pass_flag":bool(passed),"all_values_finite":all(row["finite"] for row in events),"maximum_step_mass_defect_n":step_n,"maximum_step_mass_defect_w":step_w,"cumulative_mass_defect_n":cumulative_n,"cumulative_mass_defect_w":cumulative_w,"saturation_bounds_ok":bounds,"metric_rows":1,"profile_rows":len(profiles),"event_rows":len(events)})
    return result,metrics,profiles,events


def _front(case_id,run_id,freeze,expected):
    model=IndependentModel(); times=tuple(freeze["times"]["front"])
    states,candidates=run_checkpoints(model,800,0.35,times)
    metrics=[]; profiles=[]; events=[]; fronts=[]; passed=True
    for level,time in enumerate(times,1):
        state=states[time]; view=snapshot(model,state); oracle=independent_oracle(800,time)
        error=abs(view.front_location-oracle.front_location)
        passed &= error<=freeze["tolerances"]["reference_front_absolute"]
        fronts.append(view.front_location)
        metrics.append(_blank(METRIC_COLUMNS,case_id=case_id,run_id=run_id,row_type="front",level=level,profile_id=f"front_{time}",time=time,cell_count=800,cfl=0.35,dt=0.35/1600.0,front_location=view.front_location,front_absolute=error,note="front_parity"))
        profiles.extend(_profile_rows(case_id,run_id,f"front_{time}",model,state))
        candidate=min(candidates,key=lambda item:abs(item.time-time))
        events.append(_event_candidate(case_id,run_id,state.accepted_version,model,candidate,"front_checkpoint"))
    increasing=all(b>a for a,b in zip(fronts,fronts[1:]))
    passed &= increasing
    result=_base(case_id,run_id,expected)
    result.update({"observed_classification":expected if passed else "FAIL_FRONT_GATE","pass_flag":bool(passed),"all_values_finite":True,"front_strictly_increasing":increasing,"metric_rows":len(metrics),"profile_rows":len(profiles),"event_rows":len(events)})
    return result,metrics,profiles,events


def _output(case_id,run_id,freeze,expected):
    probe=accepted_output_probe()
    passed=all([probe["candidate_reachable_while_output"],probe["candidate_unreachable_after_reject"],probe["output_exact"],probe["committed_unchanged"],probe["all_values_finite"]])
    metrics=[_blank(METRIC_COLUMNS,case_id=case_id,run_id=run_id,row_type="output_provenance",level=1,profile_id="live_trial_output",time=0.0,cell_count=32,note="accepted_output_ignores_live_trial")]
    events=[]
    for source in probe["events"]:
        row=_blank(EVENT_COLUMNS,case_id=case_id,run_id=run_id,history_id="OUTPUT",variant="independent_safe_transactional",accepted=False,time=0.0,dt=0.005,persistent_fingerprint="NA",minimum_saturation_n=0.0,maximum_saturation_n=0.0,minimum_pressure=0.0,maximum_pressure=1.0,phase_mass_n=0.0,phase_mass_w=1.0,front_location=0.0,displacement=0.125,mass_defect_n=0.0,mass_defect_w=0.0,finite=True,note="output_probe")
        row.update(source); events.append(row)
    result=_base(case_id,run_id,expected)
    result.update({"observed_classification":expected if passed else "FAIL_OUTPUT_PROVENANCE_GATE","pass_flag":bool(passed),"all_values_finite":probe["all_values_finite"],"output_exact":probe["output_exact"],"committed_unchanged":probe["committed_unchanged"],"candidate_unreachable_after_reject":probe["candidate_unreachable_after_reject"],"metric_rows":1,"profile_rows":0,"event_rows":len(events)})
    return result,metrics,[],events


def _retry(case_id,run_id,freeze,expected,unsafe):
    comparison=retry_comparison(IndependentUnsafeVariant if unsafe else IndependentSafeVariant)
    if unsafe:
        passed=all([
            comparison.declared_context_equal,comparison.committed_unchanged_at_reject,
            comparison.rejected_candidate_unreachable,not comparison.observed_fingerprint_equal,
            comparison.saturation_l2_drift>=freeze["tolerances"]["unsafe_saturation_l2_drift_floor"],
            comparison.pressure_l2_drift>=freeze["tolerances"]["unsafe_pressure_l2_drift_floor"],
            comparison.displacement_drift>=freeze["tolerances"]["unsafe_displacement_drift_floor"],
            comparison.declared_phase_mass_defect>=freeze["tolerances"]["unsafe_declared_phase_mass_defect_floor"],
            comparison.all_values_finite,
        ])
    else:
        passed=all([
            comparison.declared_context_equal,comparison.committed_unchanged_at_reject,
            comparison.rejected_candidate_unreachable,comparison.exact_saturation,
            comparison.exact_pressure,comparison.exact_displacement,
            comparison.exact_phase_masses,comparison.exact_committed_fingerprint,
            comparison.exact_output_fingerprint,comparison.observed_fingerprint_equal,
            comparison.saturation_l2_drift==0.0,comparison.pressure_l2_drift==0.0,
            comparison.displacement_drift==0.0,
            comparison.declared_phase_mass_defect<=freeze["tolerances"]["phase_mass_defect_maximum"],
            comparison.all_values_finite,
        ])
    metrics=[_blank(METRIC_COLUMNS,case_id=case_id,run_id=run_id,row_type="unsafe_retry" if unsafe else "safe_retry",level=1,profile_id="retry_comparison",time=0.0025,cell_count=32,dt=0.0025,saturation_l2=comparison.saturation_l2_drift,pressure_l2_relative=comparison.pressure_l2_drift,displacement_absolute=comparison.displacement_drift,cumulative_mass_defect_n=comparison.declared_phase_mass_defect,note="seeded_negative_control" if unsafe else "exact_safe_retry")]
    events=[]
    for source in comparison.events:
        row=_blank(EVENT_COLUMNS,case_id=case_id,run_id=run_id,variant=comparison.variant,time=0.0,dt=0.0,candidate_reachable=False,output_provenance_fingerprint=source.get("output","NA"),minimum_saturation_n="NA",maximum_saturation_n="NA",minimum_pressure="NA",maximum_pressure="NA",phase_mass_n="NA",phase_mass_w="NA",front_location="NA",displacement="NA",mass_defect_n="NA",mass_defect_w="NA",finite=True,note="retry_event")
        row.update(source); row["history_id"]=source.get("history","NA"); row["candidate_fingerprint"]=source.get("candidate","NA"); row["persistent_fingerprint"]=source.get("persistent","NA"); row["committed_fingerprint"]=source.get("committed","NA")
        events.append(row)
    profiles=[]
    model=IndependentModel()
    profiles.extend(_profile_rows(case_id,run_id,"direct",model,_committed_from_snapshot(comparison.direct)))
    profiles.extend(_profile_rows(case_id,run_id,"retry",model,_committed_from_snapshot(comparison.retry)))
    result=_base(case_id,run_id,expected)
    result.update({"observed_classification":expected if passed else "FAIL_RETRY_GATE","pass_flag":bool(passed),"all_values_finite":comparison.all_values_finite,"declared_context_equal":comparison.declared_context_equal,"committed_unchanged_at_reject":comparison.committed_unchanged_at_reject,"rejected_candidate_unreachable":comparison.rejected_candidate_unreachable,"exact_saturation":comparison.exact_saturation,"exact_pressure":comparison.exact_pressure,"exact_displacement":comparison.exact_displacement,"exact_phase_masses":comparison.exact_phase_masses,"exact_committed_fingerprint":comparison.exact_committed_fingerprint,"exact_output_fingerprint":comparison.exact_output_fingerprint,"observed_fingerprint_equal":comparison.observed_fingerprint_equal,"saturation_l2_drift":comparison.saturation_l2_drift,"pressure_l2_drift":comparison.pressure_l2_drift,"displacement_drift":comparison.displacement_drift,"declared_phase_mass_defect":comparison.declared_phase_mass_defect,"metric_rows":1,"profile_rows":len(profiles),"event_rows":len(events)})
    return result,metrics,profiles,events


def _committed_from_snapshot(view):
    return IndependentCommitted(time=view.time,saturation_n=view.saturation_n,cumulative_n_in=0.0,cumulative_n_out=0.0,cumulative_w_in=0.0,cumulative_w_out=0.0,accepted_version=view.accepted_version)


def _verify_l4(root: Path,expected: str) -> tuple[Path,str]:
    raw=root/"benchmarks"/"L4_two_phase_displacement"/"results"/"L4_D1_two_phase_displacement"
    final=raw/"final"
    files=sorted((p for p in raw.rglob("*") if p.is_file() and final not in p.parents),key=lambda p:p.relative_to(raw).as_posix())
    payload="\n".join(f"{p.relative_to(raw).as_posix()}|{_sha(p)}" for p in files)
    digest=hashlib.sha256(payload.encode("utf-8")).hexdigest()
    if digest!=expected:
        raise RuntimeError("protected L4 raw aggregate mismatch")
    return raw,digest


def _cross(root,case_id,run_id,freeze,expected):
    model=IndependentModel(); times=tuple(freeze["times"]["cross"])
    l4raw,digest=_verify_l4(root,freeze["independence"]["l4_raw_aggregate_sha256"])
    states,candidates=run_checkpoints(model,800,0.35,times)
    with (l4raw/"L4-REF-01"/"run_1"/"accepted_profile.csv").open(encoding="utf-8",newline="") as handle:
        source=list(csv.DictReader(handle))
    grouped={}
    for row in source:
        grouped.setdefault(float(row["time"]),[]).append(row)
    metrics=[]; profiles=[]; events=[]; passed=True
    maximum={"saturation_l1":0.0,"pressure_l2_relative":0.0,"front_absolute":0.0,"displacement_absolute":0.0}
    for level,time in enumerate(times,1):
        rows=sorted(grouped[time],key=lambda row:int(row["cell_index"]))
        l4_s=tuple(float(row["S_n"]) for row in rows)
        l4_p=tuple(float(row["pressure"]) for row in rows)
        l4_front=float(rows[0]["front_location"])
        l4_displacement=float(rows[0]["displacement"])
        state=states[time]; view=snapshot(model,state)
        difference=field_difference(model,view,l4_s,l4_p,l4_front,l4_displacement)
        for key in maximum: maximum[key]=max(maximum[key],difference[key])
        passed &= (
            difference["saturation_l1"]<=freeze["tolerances"]["cross_saturation_l1"]
            and difference["pressure_l2_relative"]<=freeze["tolerances"]["cross_pressure_l2_relative"]
            and difference["front_absolute"]<=freeze["tolerances"]["cross_front_absolute"]
            and difference["displacement_absolute"]<=freeze["tolerances"]["cross_displacement_absolute"]
        )
        metrics.append(_blank(METRIC_COLUMNS,case_id=case_id,run_id=run_id,row_type="cross_implementation",level=level,profile_id=f"cross_{time}",time=time,cell_count=800,cfl=0.35,dt=0.35/1600.0,saturation_l1=difference["saturation_l1"],pressure_l2_relative=difference["pressure_l2_relative"],displacement_absolute=difference["displacement_absolute"],front_location=view.front_location,front_absolute=difference["front_absolute"],note="independent_L5_vs_hash_verified_L4"))
        profiles.extend(_profile_rows(case_id,run_id,f"cross_{time}",model,state))
        candidate=min(candidates,key=lambda item:abs(item.time-time))
        events.append(_event_candidate(case_id,run_id,state.accepted_version,model,candidate,"cross_checkpoint"))
    result=_base(case_id,run_id,expected)
    result.update({"observed_classification":expected if passed else "FAIL_CROSS_IMPLEMENTATION_GATE","pass_flag":bool(passed),"all_values_finite":True,"l4_raw_aggregate_sha256":digest,"maximum_cross_saturation_l1":maximum["saturation_l1"],"maximum_cross_pressure_l2_relative":maximum["pressure_l2_relative"],"maximum_cross_front_absolute":maximum["front_absolute"],"maximum_cross_displacement_absolute":maximum["displacement_absolute"],"metric_rows":len(metrics),"profile_rows":len(profiles),"event_rows":len(events)})
    return result,metrics,profiles,events


def _finite(value: Any,limit: float) -> bool:
    if isinstance(value,bool) or value is None or isinstance(value,str): return True
    if isinstance(value,(int,float)):
        return math.isfinite(float(value)) and abs(float(value))<=limit
    if isinstance(value,dict): return all(_finite(v,limit) for v in value.values())
    if isinstance(value,(list,tuple)): return all(_finite(v,limit) for v in value)
    return True


def execute_case(root: Path,case_id: str,run_id: str) -> dict[str,Any]:
    freeze,matrix=load_design(root)
    if case_id not in matrix: raise KeyError(case_id)
    expected=matrix[case_id]["expected_classification"]
    if case_id=="L5-IV-REF-01": values=_reference(case_id,run_id,freeze,expected)
    elif case_id=="L5-IV-CV-01": values=_convergence(case_id,run_id,freeze,expected)
    elif case_id=="L5-IV-MB-01": values=_mass(case_id,run_id,freeze,expected)
    elif case_id=="L5-IV-FR-01": values=_front(case_id,run_id,freeze,expected)
    elif case_id=="L5-IV-OP-01": values=_output(case_id,run_id,freeze,expected)
    elif case_id=="L5-IV-RT-01": values=_retry(case_id,run_id,freeze,expected,False)
    elif case_id=="L5-IV-RT-02": values=_retry(case_id,run_id,freeze,expected,True)
    elif case_id=="L5-IV-XP-01": values=_cross(root,case_id,run_id,freeze,expected)
    else: raise AssertionError(case_id)
    result,metrics,profiles,events=values
    finite=_finite((metrics,profiles,events),freeze["tolerances"]["finite_absolute_limit"])
    result["all_values_finite"]=bool(result.get("all_values_finite",True) and finite)
    if not result["all_values_finite"]:
        result["pass_flag"]=False; result["observed_classification"]="FAIL_NONFINITE"
    result["output_contract_hash"]=binary_fingerprint((metrics,profiles,events))
    return {"case_result":result,"metric_comparison":metrics,"accepted_profile":profiles,"lifecycle_event_log":events}
