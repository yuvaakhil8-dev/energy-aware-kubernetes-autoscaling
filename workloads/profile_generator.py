#!/usr/bin/env python3
"""
Workload Profile Generator for Energy-Aware Autoscaling Experiments.

Generates repeatable workload profiles for experimentation:
- Low, medium, and high constant loads
- Low-to-high-to-low transitions
- Configurable duration and request rates
"""

import time
import json
import random
from typing import Dict, List, Tuple


# Workload profile definitions
# Each profile specifies: CPU target, request rate (req/s), average latency (ms)
WORKLOAD_PROFILES: Dict[str, Tuple[float, float, float]] = {
    "light": (15.0, 5.0, 30.0),   # cpu%, req/s, latency_ms
    "medium": (50.0, 20.0, 100.0),
    "heavy": (85.0, 50.0, 200.0),
    "spike": (85.0, 100.0, 300.0),  # sudden spike
    "burst": (60.0, 30.0, 80.0),   # short burst
}


class WorkloadProfile:
    """Represents a workload profile with associated metrics."""
    
    def __init__(self, name: str, cpu_percent: float, request_rate: float, 
                 avg_latency_ms: float):
        self.name = name
        self.cpu_percent = cpu_percent
        self.request_rate = request_rate
        self.avg_latency_ms = avg_latency_ms
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "cpu_percent": self.cpu_percent,
            "request_rate": self.request_rate,
            "avg_latency_ms": self.avg_latency_ms
        }


def get_profile(name: str) -> WorkloadProfile:
    """Get a workload profile by name."""
    if name in WORKLOAD_PROFILES:
        cpu, rate, latency = WORKLOAD_PROFILES[name]
        return WorkloadProfile(name, cpu, rate, latency)
    else:
        raise ValueError(f"Unknown workload profile: {name}")


def list_profiles() -> List[str]:
    """List available workload profile names."""
    return list(WORKLOAD_PROFILES.keys())


def generate_transition_sequence(
    start: str = "light",
    end: str = "light",
    transitions: List[str] = None,
    dwell_time: float = 5.0
) -> List[Tuple[str, float]]:
    """
    Generate a sequence of workload transitions.
    
    Args:
        start: Starting workload profile
        end: Ending workload profile
        transitions: List of intermediate profiles (None auto-generates)
        dwell_time: Seconds to dwell at each profile
    
    Returns:
        List of (profile_name, duration_seconds) tuples
    """
    if transitions is None:
        # Auto-generate a transition sequence: start -> medium -> heavy -> medium -> start
        if start == end == "light":
            transitions = ["medium", "heavy", "medium"]
        elif start == "light" and end == "heavy":
            transitions = ["medium"]
        elif start == "heavy" and end == "light":
            transitions = ["medium"]
        else:
            transitions = ["medium"]
    
    sequence = []
    current = start
    if current not in transitions:
        sequence.append((current, dwell_time))
    
    for profile in transitions:
        sequence.append((profile, dwell_time))
    
    # Add end profile if different
    if end != start or (end == start and len(sequence) > 0 and sequence[-1][0] != end):
        if sequence[-1][0] != end:
            sequence.append((end, dwell_time))
    
    return sequence


def generate_constant_profile(profile_name: str, duration: float) -> List[Tuple[str, float]]:
    """Generate a constant workload profile for specified duration."""
    return [(profile_name, duration)]


def export_profiles_to_json(filename: str):
    """Export all workload profiles to a JSON file."""
    data = {
        "profiles": {name: profile.to_dict() for name, profile in WORKLOAD_PROFILES.items()},
        "descriptions": {
            "light": "Low load - minimal CPU usage, low request rate",
            "medium": "Medium load - moderate CPU usage, standard request rate",
            "heavy": "High load - high CPU usage, high request rate",
            "spike": "Sudden traffic spike - maximum CPU and request rate",
            "burst": "Short burst of traffic - moderate CPU and rate"
        }
    }
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Exported workload profiles to {filename}")


# Example usage
if __name__ == "__main__":
    print("Available workload profiles:")
    for name in list_profiles():
        profile = get_profile(name)
        print(f"  {name}: CPU={profile.cpu_percent}%, "
              f"Rate={profile.request_rate} req/s, Latency={profile.avg_latency_ms}ms")
    
    # Export to JSON
    export_profiles_to_json("workload_profiles.json")