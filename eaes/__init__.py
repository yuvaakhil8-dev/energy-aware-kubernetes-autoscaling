"""Energy-Aware Experiment Simulator (EAES) core package.

The package is intentionally independent of Flask and of any Kubernetes
cluster.  It provides the configuration loader, workload generator, cluster
backend abstraction, energy model, strategies, and experiment engine used by
the research rebuild.
"""

__version__ = "3.0.0"
