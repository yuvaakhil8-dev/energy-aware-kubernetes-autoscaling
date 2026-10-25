"""Explicit node-level energy model.

All energy is modelled, never measured.  The model is deliberately separated
from the controller: energy is an output metric, not a scaling input.

    P_node(u) = P_idle + (P_max - P_idle) * u        [W]
    E_node    = P_node(u) * dt * PUE + startup_energy [J]
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List


class EnergyModelError(ValueError):
    """Raised for invalid energy configurations or utilisation values."""


class EnergyModel:
    def __init__(
        self,
        energy_config: Dict[str, Any],
        scenario: str | None = None,
        pue: float | None = None,
    ):
        self.config = energy_config
        scenario = scenario or energy_config["default_scenario"]
        if scenario not in energy_config["scenarios"]:
            raise EnergyModelError(f"unknown energy scenario: {scenario}")
        spec = energy_config["scenarios"][scenario]
        self.scenario = scenario
        self.p_idle_w = float(spec["p_idle_w"])
        self.p_max_w = float(spec["p_max_w"])
        self.pue = float(energy_config["pue"] if pue is None else pue)
        self.startup_energy_j = float(energy_config.get("node_startup_energy_j", 0.0))
        if self.p_idle_w < 0 or self.p_max_w <= 0 or self.p_max_w <= self.p_idle_w:
            raise EnergyModelError("require P_max > P_idle >= 0")
        if self.pue < 1.0:
            raise EnergyModelError("PUE must be >= 1.0")
        if self.startup_energy_j < 0:
            raise EnergyModelError("node startup energy must be non-negative")

    def node_power_w(self, utilization: float) -> float:
        if not isinstance(utilization, (int, float)) or not math.isfinite(utilization):
            raise EnergyModelError("utilization must be a finite number")
        if utilization < 0.0 or utilization > 1.0:
            raise EnergyModelError("utilization must be in [0, 1]")
        return self.p_idle_w + (self.p_max_w - self.p_idle_w) * float(utilization)

    def node_energy_j(self, utilization: float, dt_s: float) -> float:
        if dt_s <= 0:
            raise EnergyModelError("dt_s must be positive")
        return self.node_power_w(utilization) * float(dt_s) * self.pue

    def node_components_j(self, utilization: float, dt_s: float) -> Dict[str, float]:
        """Split node energy into idle and dynamic components (both include PUE)."""
        idle = self.p_idle_w * float(dt_s) * self.pue
        dynamic = (self.p_max_w - self.p_idle_w) * float(utilization) * float(dt_s) * self.pue
        return {"idle_j": idle, "dynamic_j": dynamic, "total_j": idle + dynamic}

    def attribute_pod_energy(
        self,
        node_components: Dict[str, float],
        pod_served: Iterable[float],
        startup_energy_j: float = 0.0,
    ) -> List[float]:
        """Attribute node energy to occupied pods.

        Dynamic energy follows CPU-use share; idle and startup energy follow
        requested-resource share.  With equal requests this is an equal split.
        The returned pod energies sum to node energy within floating tolerance.
        """
        served = [max(0.0, float(x)) for x in pod_served]
        n = len(served)
        if n == 0:
            return []
        total_served = sum(served)
        if total_served > 0:
            dynamic_shares = [x / total_served for x in served]
        else:
            dynamic_shares = [1.0 / n] * n
        idle_share = 1.0 / n
        startup_share = 1.0 / n
        return [
            node_components["dynamic_j"] * dynamic_shares[i]
            + node_components["idle_j"] * idle_share
            + float(startup_energy_j) * startup_share
            for i in range(n)
        ]

    def per_request(self, total_energy_j: float, served: int, offered: int) -> Dict[str, float | None]:
        if served < 0 or offered < 0:
            raise EnergyModelError("request counts must be non-negative")
        return {
            "energy_per_served_request_j": (total_energy_j / served) if served > 0 else None,
            "energy_per_offered_request_j": (total_energy_j / offered) if offered > 0 else None,
        }


def conservation_error(total_node_energy_j: float, pod_energies_j: Iterable[float]) -> float:
    """Absolute conservation error; zero for a correct attribution."""
    return abs(float(total_node_energy_j) - sum(float(x) for x in pod_energies_j))


def scenario_names(energy_config: Dict[str, Any]) -> List[str]:
    return list(energy_config["scenarios"].keys())
