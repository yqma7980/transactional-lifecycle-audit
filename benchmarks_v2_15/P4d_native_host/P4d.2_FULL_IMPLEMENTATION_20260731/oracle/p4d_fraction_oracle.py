from __future__ import annotations

from fractions import Fraction as F


def derive_fraction_packets() -> dict[str, object]:
    G, tau_y0, H = F(10), F(1), F(2)
    elastic_gamma = (F(1, 20), F(0))
    elastic_tau = tuple(G * value for value in elastic_gamma)
    plastic_gamma = (F(1, 5), F(0))
    plastic_trial_tau = tuple(G * value for value in plastic_gamma)
    plastic_norm = plastic_trial_tau[0]
    delta_lambda = (plastic_norm - tau_y0) / (G + H)
    plastic_gamma_p = (delta_lambda, F(0))
    plastic_tau = (G * (plastic_gamma[0] - delta_lambda), F(0))
    tangent_x = G - G * G / (G + H)
    tangent_y = G - G * G * delta_lambda / plastic_norm
    return {
        "elastic": {
            "gamma": elastic_gamma,
            "tau": elastic_tau,
            "gamma_p": (F(0), F(0)),
            "alpha": F(0),
            "tangent": ((G, F(0)), (F(0), G)),
        },
        "plastic": {
            "gamma": plastic_gamma,
            "trial_tau": plastic_trial_tau,
            "delta_lambda": delta_lambda,
            "tau": plastic_tau,
            "gamma_p": plastic_gamma_p,
            "alpha": delta_lambda,
            "tangent": ((tangent_x, F(0)), (F(0), tangent_y)),
        },
    }


def fraction_text(value):
    if isinstance(value, F):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, dict):
        return {key: fraction_text(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [fraction_text(item) for item in value]
    return value
