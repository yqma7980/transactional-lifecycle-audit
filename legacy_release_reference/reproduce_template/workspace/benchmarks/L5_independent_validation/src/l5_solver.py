"""Independent MUSCL-Rusanov SSPRK2 two-phase solver for L5-D1."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .l5_oracle import IndependentOracle
from .l5_state import (
    IndependentCandidate,
    IndependentCommitted,
    IndependentModel,
    IndependentSnapshot,
    binary_fingerprint,
    initial_committed,
    phase_mass_n,
    phase_mass_w,
)


@dataclass(frozen=True)
class IndependentMetrics:
    saturation_l1: float
    saturation_l2: float
    pressure_l2_relative: float
    pressure_linf: float
    displacement_absolute: float
    front_absolute: float
    oracle_root_residual: float
    oracle_mass_identity_error: float


def _minmod(left: float, right: float) -> float:
    if left*right<=0.0:
        return 0.0
    return math.copysign(min(abs(left),abs(right)),left)


def _reconstruction(values: tuple[float,...]) -> tuple[float,...]:
    extended=(1.0,*values,values[-1])
    return tuple(
        _minmod(extended[index]-extended[index-1],extended[index+1]-extended[index])
        for index in range(1,len(values)+1)
    )


def _numerical_flux(model: IndependentModel, left: float, right: float) -> float:
    return model.total_flux*(
        0.5*(model.fractional_flow_n(left)+model.fractional_flow_n(right))
        - (right-left)
    )


def _spatial_operator(
    model: IndependentModel,
    values: tuple[float,...],
) -> tuple[tuple[float,...],float,float]:
    cell_count=len(values)
    dx=model.length/cell_count
    slopes=_reconstruction(values)
    fluxes=[0.0]*(cell_count+1)
    fluxes[0]=model.total_flux
    for interface in range(1,cell_count):
        left=values[interface-1]+0.5*slopes[interface-1]
        right=values[interface]-0.5*slopes[interface]
        fluxes[interface]=_numerical_flux(model,left,right)
    outlet=values[-1]+0.5*slopes[-1]
    fluxes[-1]=model.total_flux*model.fractional_flow_n(outlet)
    rhs=tuple(-(fluxes[index+1]-fluxes[index])/(model.porosity*dx) for index in range(cell_count))
    return rhs,fluxes[0],fluxes[-1]


def pressure_field(model: IndependentModel, saturation_n: Iterable[float]) -> tuple[float,...]:
    values=tuple(saturation_n)
    dx=model.length/len(values)
    resistance=[
        model.total_flux/(model.permeability*model.mobility_total(value))
        for value in values
    ]
    output=[0.0]*len(values)
    accumulator=model.pressure_right
    for index in range(len(values)-1,-1,-1):
        output[index]=accumulator+0.5*dx*resistance[index]
        accumulator+=dx*resistance[index]
    return tuple(output)


def one_way_response(model: IndependentModel, pressure: Iterable[float]) -> float:
    values=tuple(pressure)
    return model.biot_alpha/model.drained_modulus*model.length*math.fsum(values)/len(values)


def locate_front(saturation_n: Iterable[float], length: float=1.0) -> float:
    values=tuple(saturation_n)
    threshold=0.5/math.sqrt(2.0)
    dx=length/len(values)
    for index in range(len(values)-1):
        left=values[index]; right=values[index+1]
        if left>=threshold>right:
            centre=(index+0.5)*dx
            return centre if left==right else centre+(threshold-left)*dx/(right-left)
    return 0.0 if values[0]<threshold else length


def snapshot(model: IndependentModel, state: IndependentCommitted) -> IndependentSnapshot:
    pressure=pressure_field(model,state.saturation_n)
    return IndependentSnapshot(
        time=state.time,
        saturation_n=state.saturation_n,
        pressure=pressure,
        displacement=one_way_response(model,pressure),
        phase_mass_n=phase_mass_n(model,state.saturation_n),
        phase_mass_w=phase_mass_w(model,state.saturation_n),
        front_location=locate_front(state.saturation_n,model.length),
        accepted_version=state.accepted_version,
        committed_hash=state.fingerprint,
    )


def evaluate_candidate(
    model: IndependentModel,
    committed: IndependentCommitted,
    dt: float,
    *,
    attempt_id: str,
    source_override: tuple[float,...] | None=None,
) -> IndependentCandidate:
    if dt<=0.0:
        raise ValueError("dt must be positive")
    source=source_override if source_override is not None else committed.saturation_n
    if len(source)!=len(committed.saturation_n):
        raise ValueError("source/committed size mismatch")
    rhs0,n_in0,n_out0=_spatial_operator(model,source)
    stage1=tuple(value+dt*rate for value,rate in zip(source,rhs0))
    rhs1,n_in1,n_out1=_spatial_operator(model,stage1)
    updated=tuple(
        0.5*old+0.5*(intermediate+dt*rate)
        for old,intermediate,rate in zip(source,stage1,rhs1)
    )
    n_in=0.5*(n_in0+n_in1)
    n_out=0.5*(n_out0+n_out1)
    w_in=model.total_flux-n_in
    w_out=model.total_flux-n_out
    source_n=phase_mass_n(model,source)
    source_w=phase_mass_w(model,source)
    declared_n=phase_mass_n(model,committed.saturation_n)
    declared_w=phase_mass_w(model,committed.saturation_n)
    updated_n=phase_mass_n(model,updated)
    updated_w=phase_mass_w(model,updated)
    expected_n=dt*(n_in-n_out)
    expected_w=dt*(w_in-w_out)
    return IndependentCandidate(
        attempt_id=attempt_id,
        dt=dt,
        time=committed.time+dt,
        saturation_n=updated,
        flux_n_in=n_in,
        flux_n_out=n_out,
        flux_w_in=w_in,
        flux_w_out=w_out,
        cumulative_n_in=committed.cumulative_n_in+dt*n_in,
        cumulative_n_out=committed.cumulative_n_out+dt*n_out,
        cumulative_w_in=committed.cumulative_w_in+dt*w_in,
        cumulative_w_out=committed.cumulative_w_out+dt*w_out,
        internal_n_mass_defect=(updated_n-source_n)-expected_n,
        internal_w_mass_defect=(updated_w-source_w)-expected_w,
        declared_n_mass_defect=(updated_n-declared_n)-expected_n,
        declared_w_mass_defect=(updated_w-declared_w)-expected_w,
        declared_committed_hash=committed.fingerprint,
        source_field_hash=binary_fingerprint(source),
    )


def commit(committed: IndependentCommitted, candidate: IndependentCandidate) -> IndependentCommitted:
    if candidate.declared_committed_hash!=committed.fingerprint:
        raise ValueError("candidate/committed version mismatch")
    return IndependentCommitted(
        time=candidate.time,
        saturation_n=candidate.saturation_n,
        cumulative_n_in=candidate.cumulative_n_in,
        cumulative_n_out=candidate.cumulative_n_out,
        cumulative_w_in=candidate.cumulative_w_in,
        cumulative_w_out=candidate.cumulative_w_out,
        accepted_version=committed.accepted_version+1,
    )


def run_checkpoints(
    model: IndependentModel,
    cell_count: int,
    cfl: float,
    checkpoints: tuple[float,...],
) -> tuple[dict[float,IndependentCommitted],tuple[IndependentCandidate,...]]:
    if tuple(sorted(checkpoints))!=checkpoints or not checkpoints:
        raise ValueError("checkpoints must be nonempty and sorted")
    state=initial_committed(cell_count)
    dx=model.length/cell_count
    base_dt=cfl*dx/2.0
    candidates=[]
    states={}
    for target in checkpoints:
        while state.time<target-1.0e-15:
            dt=min(base_dt,target-state.time)
            candidate=evaluate_candidate(model,state,dt,attempt_id=f"STEP_{len(candidates)+1}")
            state=commit(state,candidate)
            candidates.append(candidate)
        states[target]=state
    return states,tuple(candidates)


def cumulative_defects(model: IndependentModel,state: IndependentCommitted) -> tuple[float,float]:
    current_n=phase_mass_n(model,state.saturation_n)
    current_w=phase_mass_w(model,state.saturation_n)
    n=(current_n-0.0)-(state.cumulative_n_in-state.cumulative_n_out)
    w=(current_w-model.porosity*model.length)-(state.cumulative_w_in-state.cumulative_w_out)
    return n,w


def normalized_defect(defect: float,*scales: float) -> float:
    return abs(defect)/max((1.0,*(abs(value) for value in scales)))


def compare_reference(
    model: IndependentModel,
    observed: IndependentSnapshot,
    reference: IndependentOracle,
) -> IndependentMetrics:
    dx=model.length/len(observed.saturation_n)
    saturation_delta=[a-b for a,b in zip(observed.saturation_n,reference.saturation_n)]
    pressure_delta=[a-b for a,b in zip(observed.pressure,reference.pressure)]
    pressure_norm=math.sqrt(math.fsum(value*value for value in reference.pressure)*dx)
    return IndependentMetrics(
        saturation_l1=math.fsum(abs(value) for value in saturation_delta)*dx,
        saturation_l2=math.sqrt(math.fsum(value*value for value in saturation_delta)*dx),
        pressure_l2_relative=math.sqrt(math.fsum(value*value for value in pressure_delta)*dx)/pressure_norm,
        pressure_linf=max(abs(value) for value in pressure_delta),
        displacement_absolute=abs(observed.displacement-reference.displacement),
        front_absolute=abs(observed.front_location-reference.front_location),
        oracle_root_residual=reference.maximum_root_residual,
        oracle_mass_identity_error=reference.phase_mass_identity_error,
    )


def field_difference(
    model: IndependentModel,
    left: IndependentSnapshot,
    right_saturation: tuple[float,...],
    right_pressure: tuple[float,...],
    right_front: float,
    right_displacement: float,
) -> dict[str,float]:
    dx=model.length/len(left.saturation_n)
    saturation_delta=[a-b for a,b in zip(left.saturation_n,right_saturation)]
    pressure_delta=[a-b for a,b in zip(left.pressure,right_pressure)]
    pressure_norm=math.sqrt(math.fsum(value*value for value in right_pressure)*dx)
    return {
        "saturation_l1":math.fsum(abs(value) for value in saturation_delta)*dx,
        "pressure_l2_relative":math.sqrt(math.fsum(value*value for value in pressure_delta)*dx)/pressure_norm,
        "front_absolute":abs(left.front_location-right_front),
        "displacement_absolute":abs(left.displacement-right_displacement),
    }


def all_finite(values: Iterable[float],limit: float=1.0e100) -> bool:
    return all(math.isfinite(value) and abs(value)<=limit for value in values)
