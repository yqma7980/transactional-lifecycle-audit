"""Independent Decimal oracle for the frozen L6 stationary point."""

from __future__ import annotations

from decimal import Decimal, localcontext


def derive_stationary_oracle() -> dict[str, str | float]:
    with localcontext() as context:
        context.prec = 60
        two = Decimal(2)
        three = Decimal(3)
        x_star = (two / three).sqrt()
        residual = two - (Decimal(4) / three) * x_star
        cost = Decimal("0.5") * residual * residual
        return {
            "x_star_decimal": str(x_star),
            "residual_star_decimal": str(residual),
            "cost_star_decimal": str(cost),
            "x_star": float(x_star),
            "residual_star": float(residual),
            "cost_star": float(cost),
        }


__all__ = ["derive_stationary_oracle"]
