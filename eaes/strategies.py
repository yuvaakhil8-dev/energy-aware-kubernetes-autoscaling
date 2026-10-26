"""Five explicitly separated autoscaling strategies.

No strategy calls itself Kubernetes HPA.  ``HPAFormulaStrategy`` simulates the
documented HPA replica formula; real cluster HPA is a separate Phase 7 concern.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .forecast import make_forecaster


@dataclass
class Decision:
    replicas: int
    action: str
    rule: str
    reason: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "replicas": self.replicas,
            "action": self.action,
            "rule": self.rule,
            "reason": self.reason,
            "details": self.details,
        }


class Strategy:
    name = "base"

    def __init__(self, cfg: Dict[str, Any], simulation: Dict[str, Any], sla: Dict[str, Any]):
        self.cfg = cfg
        self.simulation = simulation
        self.sla = sla
        self.last_scale_time = -1e9
        self.last_direction = "hold"
        self.oscillations = 0
        self.scaling_events = 0
        self.initial_replicas = int(simulation.get("initial_replicas", 1))
        self.max_replicas = int(cfg.get("max_replicas", simulation["max_replicas"]))
        self.min_replicas = int(cfg.get("min_replicas", simulation["min_replicas"]))
        self.oscillation_window_s = float(cfg.get("oscillation_window_s", 120))

    def _record_scale(self, t: float, action: str, current: int, new: int) -> None:
        if action != "hold" and new != current:
            if (
                self.last_scale_time > -1e8
                and (t - self.last_scale_time) < self.oscillation_window_s
                and action != self.last_direction
            ):
                self.oscillations += 1
            self.last_scale_time = t
            self.last_direction = action
            self.scaling_events += 1

    def _cooldown_ok(self, t: float, cooldown_s: float) -> bool:
        return (t - self.last_scale_time) >= cooldown_s

    def observe(self, arrival_rate_rps: float) -> None:
        """Hook for forecasters; no-op for reactive strategies."""

    def decide(self, state: Dict[str, Any]) -> Decision:
        raise NotImplementedError


class StaticStrategy(Strategy):
    name = "static"

    def __init__(self, cfg, simulation, sla):
        super().__init__(cfg, simulation, sla)
        self.fixed = int(cfg["replicas"])
        self.initial_replicas = self.fixed
        self.min_replicas = self.fixed
        self.max_replicas = self.fixed

    def decide(self, state: Dict[str, Any]) -> Decision:
        return Decision(
            replicas=self.fixed,
            action="hold",
            rule="static_fixed_replicas",
            reason="Fixed replica count from configuration",
            details={"configured_replicas": self.fixed},
        )


class CPUThresholdStrategy(Strategy):
    """The legacy 80/30 threshold rule, retained for continuity."""

    name = "cpu_threshold"

    def __init__(self, cfg, simulation, sla):
        super().__init__(cfg, simulation, sla)
        self.scale_up = float(cfg["scale_up"])
        self.scale_down = float(cfg["scale_down"])
        self.hysteresis = float(cfg["hysteresis"])
        self.up_cooldown = float(cfg["up_cooldown_s"])
        self.down_cooldown = float(cfg["down_cooldown_s"])

    def decide(self, state: Dict[str, Any]) -> Decision:
        t = float(state["t"])
        current = int(state["desired_replicas"])
        cpu = float(state.get("cpu_util") or 0.0)
        warmup = bool(state.get("warmup"))
        details = {
            "cpu_util": cpu,
            "scale_up_threshold": self.scale_up,
            "scale_down_threshold": self.scale_down - self.hysteresis,
            "current_replicas": current,
        }
        if cpu > self.scale_up and current < self.max_replicas:
            if not self._cooldown_ok(t, self.up_cooldown):
                return Decision(current, "hold", "up_cooldown", "Scale-up cooldown active", details)
            new = min(self.max_replicas, current + 1)
            self._record_scale(t, "up", current, new)
            return Decision(new, "up", "cpu_above_scale_up", "CPU above scale-up threshold", details)
        if cpu < (self.scale_down - self.hysteresis) and current > self.min_replicas:
            if warmup:
                return Decision(current, "hold", "warmup_no_scaledown", "Scale-down suppressed during warm-up", details)
            if not self._cooldown_ok(t, self.down_cooldown):
                return Decision(current, "hold", "down_cooldown", "Scale-down cooldown active", details)
            new = max(self.min_replicas, current - 1)
            self._record_scale(t, "down", current, new)
            return Decision(new, "down", "cpu_below_scale_down", "CPU below hysteresis-adjusted scale-down threshold", details)
        return Decision(current, "hold", "within_band_or_bounds", "CPU within hysteresis band or replica bounds", details)


class HPAFormulaStrategy(Strategy):
    """Simulated Kubernetes HPA replica formula.

    desired = ceil(current_replicas * current_metric / target_metric)
    A tolerance band and a scale-down stabilization window are applied.
    """

    name = "hpa_formula"

    def __init__(self, cfg, simulation, sla):
        super().__init__(cfg, simulation, sla)
        self.target = float(cfg["target_cpu"])
        self.tolerance = float(cfg["tolerance"])
        self.stabilization_s = float(cfg["scale_down_stabilization_s"])
        self.down_since: Optional[float] = None

    def decide(self, state: Dict[str, Any]) -> Decision:
        t = float(state["t"])
        current = max(1, int(state["desired_replicas"]))
        cpu = state.get("cpu_util")
        details = {
            "current_replicas": current,
            "cpu_util": cpu,
            "target_cpu": self.target,
            "tolerance": self.tolerance,
        }
        if cpu is None or state.get("capacity_rps", 0) <= 0:
            if current < self.max_replicas:
                new = min(self.max_replicas, current + 1)
                self._record_scale(t, "up", current, new)
                return Decision(new, "up", "metric_unavailable_scale_up", "No CPU metric/capacity; add one replica", details)
            return Decision(current, "hold", "metric_unavailable_at_max", "No CPU metric and already at max", details)

        ratio = float(cpu) / self.target
        details["ratio"] = ratio
        if ratio > (1.0 + self.tolerance):
            desired = int(math.ceil(current * ratio))
            desired = max(current + 1, min(self.max_replicas, desired))
            self.down_since = None
            self._record_scale(t, "up", current, desired)
            return Decision(desired, "up", "hpa_formula_above_tolerance", "Formula recommends more replicas", details)
        if ratio < (1.0 - self.tolerance):
            if self.down_since is None:
                self.down_since = t
            elapsed = t - self.down_since
            details["down_stabilization_elapsed_s"] = elapsed
            if elapsed < self.stabilization_s:
                return Decision(current, "hold", "hpa_down_stabilization", "Scale-down stabilization window not elapsed", details)
            desired = int(math.ceil(current * ratio))
            desired = max(self.min_replicas, min(current - 1, desired))
            self._record_scale(t, "down", current, desired)
            return Decision(desired, "down", "hpa_formula_below_tolerance", "Formula recommends fewer replicas after stabilization", details)
        self.down_since = None
        return Decision(current, "hold", "hpa_formula_within_tolerance", "Metric within tolerance band", details)


class EAESStrategy(Strategy):
    """SLA-first, lexicographic controller with no hidden weights.

    Rule order:
      1. If predicted utilization exceeds the SLA-safe target, scale up to the
         smallest replica count that restores the margin.
      2. Otherwise, consider one scale-down only after cooldown, dwell, and
         stabilization; the smaller configuration must remain SLA-safe.
      3. Hold.
    """

    name = "eaes"

    def __init__(self, cfg, simulation, sla):
        super().__init__(cfg, simulation, sla)
        self.ceiling = float(sla["utilization_ceiling"])
        self.margin_threshold = float(cfg.get("margin_threshold", sla["margin_threshold"]))
        self.target_util = max(1e-9, self.ceiling - self.margin_threshold)
        self.cooldown_s = float(cfg["cooldown_s"])
        self.stabilization_s = float(cfg["stabilization_s"])
        self.min_dwell_s = float(cfg["min_dwell_s"])
        self.max_scale_step = int(cfg.get("max_scale_step", 10))
        self.safe_since: Optional[float] = None

    def forecast_rate(self, state: Dict[str, Any]) -> float:
        return max(0.0, float(state.get("arrival_rate_rps") or 0.0))

    def decide(self, state: Dict[str, Any]) -> Decision:
        t = float(state["t"])
        current = max(1, int(state["desired_replicas"]))
        ready = int(state.get("ready_replicas", 0))
        pending = int(state.get("pending_replicas", 0))
        projected = max(1, ready + pending)
        cap = float(state.get("pod_capacity_rps") or 0.0)
        dt = float(state.get("dt_s") or 1.0)
        demand = self.forecast_rate(state)
        backlog = float(state.get("backlog_requests") or 0.0)
        if demand <= 0 and backlog > 0:
            demand = backlog / dt
        predicted_util = demand / (projected * cap) if projected * cap > 0 else 1.0
        margin = self.ceiling - predicted_util
        warmup = bool(state.get("warmup"))
        details = {
            "current_replicas": current,
            "ready_replicas": ready,
            "pending_replicas": pending,
            "projected_replicas": projected,
            "demand_rps": demand,
            "predicted_utilization": predicted_util,
            "sla_margin": margin,
            "target_utilization": self.target_util,
            "backlog_requests": backlog,
        }

        if margin < self.margin_threshold:
            if cap <= 0:
                required = current + 1
            elif demand <= 0:
                required = current + 1
            else:
                required = int(math.ceil(demand / (cap * self.target_util)))
            new = min(self.max_replicas, max(current + 1, required))
            new = min(new, current + self.max_scale_step)
            if new <= current:
                return Decision(current, "hold", "max_replicas_reached", "SLA margin low but maximum replicas reached", details)
            self.safe_since = None
            self._record_scale(t, "up", current, new)
            return Decision(new, "up", "sla_margin_below_threshold", "Scale to smallest count restoring the SLA margin", details)

        if self.safe_since is None:
            self.safe_since = t
        details["safe_elapsed_s"] = t - self.safe_since
        if warmup:
            return Decision(current, "hold", "warmup_no_scaledown", "Scale-down suppressed during warm-up", details)
        if current <= self.min_replicas:
            return Decision(current, "hold", "min_replicas", "Already at minimum replicas", details)
        if backlog > 0:
            return Decision(current, "hold", "backlog_present", "Backlog present; do not reduce capacity", details)
        if not self._cooldown_ok(t, self.cooldown_s):
            return Decision(current, "hold", "cooldown", "Cooldown active", details)
        if (t - self.last_scale_time) < self.min_dwell_s:
            return Decision(current, "hold", "min_dwell", "Minimum dwell time active", details)
        if (t - self.safe_since) < self.stabilization_s:
            return Decision(current, "hold", "stabilization", "SLA-safe stabilization window not elapsed", details)

        smaller = current - 1
        predicted_smaller = demand / (smaller * cap) if smaller * cap > 0 else 1.0
        cpu = float(state.get("cpu_util") or 0.0)
        details["predicted_utilization_smaller"] = predicted_smaller
        details["cpu_util"] = cpu
        if predicted_smaller <= self.target_util and cpu <= self.ceiling:
            self._record_scale(t, "down", current, smaller)
            return Decision(smaller, "down", "safe_scale_down", "Smaller configuration remains SLA-safe", details)
        return Decision(current, "hold", "scale_down_would_breach_sla", "Smaller configuration would breach the SLA margin", details)


class ForecastingEAESStrategy(EAESStrategy):
    """EAES with a transparent Holt forecast over the startup horizon."""

    name = "forecasting_eaes"

    def __init__(self, cfg, simulation, sla):
        super().__init__(cfg, simulation, sla)
        fcfg = cfg.get("forecast", {"method": "holt", "alpha": 0.5, "beta": 0.3})
        self.forecaster = make_forecaster(fcfg.get("method", "holt"), fcfg)
        self.horizon_steps = max(
            1,
            int(math.ceil(float(simulation["startup_delay_s"]) / float(simulation["control_interval_s"]))),
        )
        self.last_forecast = 0.0

    def observe(self, arrival_rate_rps: float) -> None:
        self.forecaster.update(arrival_rate_rps)
        self.last_forecast = self.forecaster.predict(self.horizon_steps)

    def forecast_rate(self, state: Dict[str, Any]) -> float:
        pred = self.forecaster.predict(self.horizon_steps)
        # Before enough observations, fall back to the current rate.
        return max(float(state.get("arrival_rate_rps") or 0.0), pred)


class OracleStrategy(EAESStrategy):
    """Exploratory perfect-foresight upper bound.

    The controller sees the true arrival counts for the next startup-delay
    horizon and sizes for the peak of that window.  It uses the same energy
    model, replica bounds, and SLA margin as EAES.  It is deliberately not part
    of the confirmatory five-strategy comparison: it is not deployable and its
    information set is unattainable online.
    """

    name = "oracle"

    def forecast_rate(self, state: Dict[str, Any]) -> float:
        future = state.get("future_arrival_rates_rps") or []
        current = float(state.get("arrival_rate_rps") or 0.0)
        return max([current] + [float(x) for x in future])


def make_strategy(name: str, configs: Dict[str, Dict[str, Any]]) -> Strategy:
    cfg = configs["strategies"][name]
    simulation = configs["simulation"]
    sla = configs["sla"]
    if name == "static":
        return StaticStrategy(cfg, simulation, sla)
    if name == "cpu_threshold":
        return CPUThresholdStrategy(cfg, simulation, sla)
    if name == "hpa_formula":
        return HPAFormulaStrategy(cfg, simulation, sla)
    if name == "eaes":
        return EAESStrategy(cfg, simulation, sla)
    if name == "forecasting_eaes":
        return ForecastingEAESStrategy(cfg, simulation, sla)
    if name == "oracle":
        return OracleStrategy(cfg, simulation, sla)
    raise ValueError(f"unknown strategy: {name}")
