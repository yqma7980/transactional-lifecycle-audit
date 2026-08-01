from __future__ import annotations

import math

import numpy as np


AMPLITUDE = 1.0e-3
SHEAR_MODULUS = 10.0


def exact_solution(x, y):
    return AMPLITUDE * np.sin(math.pi * x) * np.sin(math.pi * y)


def exact_gradient(x, y):
    return np.stack(
        (
            AMPLITUDE * math.pi * np.cos(math.pi * x) * np.sin(math.pi * y),
            AMPLITUDE * math.pi * np.sin(math.pi * x) * np.cos(math.pi * y),
        ),
        axis=0,
    )


def body_force(x, y):
    return 2.0 * SHEAR_MODULUS * math.pi**2 * exact_solution(x, y)
