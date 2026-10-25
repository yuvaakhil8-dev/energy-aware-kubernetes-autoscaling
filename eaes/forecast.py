"""Small, transparent forecasters used by the forecasting EAES ablation."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


class EWMAForecaster:
    def __init__(self, alpha: float = 0.3):
        if not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = float(alpha)
        self.level: Optional[float] = None
        self.n = 0

    def update(self, x: float) -> None:
        x = max(0.0, float(x))
        self.level = x if self.level is None else self.alpha * x + (1 - self.alpha) * self.level
        self.n += 1

    def predict(self, horizon_steps: int = 1) -> float:
        if self.level is None:
            return 0.0
        return max(0.0, self.level)


class HoltForecaster:
    """Holt's linear trend with additive trend and non-negative clipping."""

    def __init__(self, alpha: float = 0.5, beta: float = 0.3):
        if not 0 < alpha <= 1 or not 0 <= beta <= 1:
            raise ValueError("alpha in (0,1], beta in [0,1]")
        self.alpha = float(alpha)
        self.beta = float(beta)
        self.level: Optional[float] = None
        self.trend = 0.0
        self.n = 0

    def update(self, x: float) -> None:
        x = max(0.0, float(x))
        if self.level is None:
            self.level = x
            self.trend = 0.0
        else:
            previous = self.level
            self.level = self.alpha * x + (1 - self.alpha) * (previous + self.trend)
            self.trend = self.beta * (self.level - previous) + (1 - self.beta) * self.trend
        self.n += 1

    def predict(self, horizon_steps: int = 1) -> float:
        if self.level is None:
            return 0.0
        return max(0.0, self.level + max(0, int(horizon_steps)) * self.trend)


def make_forecaster(method: str, cfg: Dict[str, Any] | None = None):
    cfg = cfg or {}
    if method == "ewma":
        return EWMAForecaster(float(cfg.get("alpha", 0.3)))
    if method == "holt":
        return HoltForecaster(float(cfg.get("alpha", 0.5)), float(cfg.get("beta", 0.3)))
    raise ValueError(f"unknown forecast method: {method}")


def evaluate_forecast(
    rates: List[float],
    method: str = "holt",
    cfg: Dict[str, Any] | None = None,
    horizon_steps: int = 1,
    eval_fraction: float = 0.5,
) -> Dict[str, float | int | None]:
    """Online forecast evaluation on the held-out final portion of a trace.

    The model is updated sequentially over the whole trace; errors are counted
    only when the target lies in the final ``eval_fraction`` segment.  This is a
    held-out segment evaluation, not a retrained/rolling-origin experiment.
    """
    if not rates:
        return {"mae": None, "mape_pct": None, "n": 0, "method": method}
    split = int(len(rates) * (1.0 - float(eval_fraction)))
    split = max(0, min(split, len(rates) - 1))
    model = make_forecaster(method, cfg)
    abs_errors: List[float] = []
    pct_errors: List[float] = []
    for i, actual in enumerate(rates):
        if i >= split and i + horizon_steps < len(rates):
            pred = model.predict(horizon_steps)
            target = rates[i + horizon_steps]
            abs_errors.append(abs(pred - target))
            if target > 0:
                pct_errors.append(abs(pred - target) / target * 100.0)
        model.update(actual)
    mae = sum(abs_errors) / len(abs_errors) if abs_errors else None
    mape = sum(pct_errors) / len(pct_errors) if pct_errors else None
    return {
        "mae": mae,
        "mape_pct": mape,
        "n": len(abs_errors),
        "method": method,
        "horizon_steps": int(horizon_steps),
    }
