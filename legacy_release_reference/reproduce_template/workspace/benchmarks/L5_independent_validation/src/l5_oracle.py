"""Independent entropy and fixed Gauss-Legendre reference for L5-D1."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
from typing import Callable

from .l5_state import IndependentModel


SHOCK_SATURATION = 1.0 / math.sqrt(2.0)
SHOCK_SPEED = (1.0 + math.sqrt(2.0)) / 2.0
BREAKTHROUGH_TIME = 1.0 / SHOCK_SPEED

_GL8_X = (
    -0.9602898564975363, -0.7966664774136267,
    -0.5255324099163290, -0.1834346424956498,
     0.1834346424956498,  0.5255324099163290,
     0.7966664774136267,  0.9602898564975363,
)
_GL8_W = (
    0.1012285362903763, 0.2223810344533745,
    0.3137066458778873, 0.3626837833783620,
    0.3626837833783620, 0.3137066458778873,
    0.2223810344533745, 0.1012285362903763,
)


@dataclass(frozen=True)
class IndependentOracle:
    time: float
    cell_count: int
    saturation_n: tuple[float, ...]
    pressure: tuple[float, ...]
    displacement: float
    front_location: float
    maximum_root_residual: float
    phase_mass_identity_error: float


def fractional_flow(saturation_n: float) -> float:
    numerator=saturation_n*saturation_n
    return numerator/(numerator+(1.0-saturation_n)**2)


def fractional_flow_derivative(saturation_n: float) -> float:
    denominator=saturation_n**2+(1.0-saturation_n)**2
    return 2.0*saturation_n*(1.0-saturation_n)/denominator**2


def entropy_value(x: float, time: float) -> tuple[float,float]:
    if time<=0.0:
        return 0.0,0.0
    similarity=x/time
    if similarity>=SHOCK_SPEED:
        return 0.0,0.0
    if similarity<=0.0:
        return 1.0,0.0
    lo=SHOCK_SATURATION
    hi=1.0
    for _ in range(110):
        middle=(lo+hi)/2.0
        if fractional_flow_derivative(middle)>similarity:
            lo=middle
        else:
            hi=middle
    value=(lo+hi)/2.0
    return value,abs(fractional_flow_derivative(value)-similarity)


def _gauss8(function: Callable[[float],float], left: float, right: float) -> float:
    if right<=left:
        return 0.0
    middle=(left+right)/2.0
    radius=(right-left)/2.0
    return radius*math.fsum(
        weight*function(middle+radius*node)
        for node,weight in zip(_GL8_X,_GL8_W)
    )


def _split_integral(function: Callable[[float],float], left: float, right: float, time: float) -> float:
    shock=SHOCK_SPEED*time
    if left<shock<right:
        return _gauss8(function,left,shock)+_gauss8(function,shock,right)
    return _gauss8(function,left,right)


@lru_cache(maxsize=64)
def independent_oracle(cell_count: int, time: float) -> IndependentOracle:
    if cell_count<4:
        raise ValueError("cell_count must be at least four")
    if not 0.0<time<BREAKTHROUGH_TIME:
        raise ValueError("reference is frozen to positive pre-breakthrough times")
    model=IndependentModel()
    dx=model.length/cell_count
    residuals=[]

    def saturation(x: float) -> float:
        value,residual=entropy_value(x,time)
        residuals.append(residual)
        return value

    def resistance(x: float) -> float:
        value,residual=entropy_value(x,time)
        residuals.append(residual)
        return model.total_flux/(model.permeability*model.mobility_total(value))

    sat=[]
    cell_resistance=[]
    for index in range(cell_count):
        left=index*dx
        right=(index+1)*dx
        sat.append(_split_integral(saturation,left,right,time)/dx)
        cell_resistance.append(_split_integral(resistance,left,right,time))

    pressure=[0.0]*cell_count
    tail=model.pressure_right
    for index in range(cell_count-1,-1,-1):
        centre=(index+0.5)*dx
        right=(index+1.0)*dx
        pressure[index]=tail+_split_integral(resistance,centre,right,time)
        tail+=cell_resistance[index]

    displacement=model.biot_alpha/model.drained_modulus*_split_integral(
        lambda x:x*resistance(x),0.0,model.length,time
    )
    mass=math.fsum(sat)*dx
    return IndependentOracle(
        time=time,
        cell_count=cell_count,
        saturation_n=tuple(sat),
        pressure=tuple(pressure),
        displacement=displacement,
        front_location=SHOCK_SPEED*time,
        maximum_root_residual=max(residuals,default=0.0),
        phase_mass_identity_error=abs(mass-time),
    )
