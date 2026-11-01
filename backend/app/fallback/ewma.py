"""Exponentially weighted moving average used as the fallback estimate."""
from typing import Sequence


def ewma(values: Sequence[float], alpha: float) -> float:
    """S(t) = alpha * X(t) + (1 - alpha) * S(t-1), seeded with the oldest value.

    `values` must be ordered oldest -> newest.
    """
    if not values:
        raise ValueError("ewma requires at least one value")
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    s = float(values[0])
    for x in values[1:]:
        s = alpha * float(x) + (1 - alpha) * s
    return s
