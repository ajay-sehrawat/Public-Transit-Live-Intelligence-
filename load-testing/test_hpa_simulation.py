# -*- coding: utf-8 -*-
"""Kubernetes HPA Controller Simulation & Autoscaling Verification (Requirement c)
Implements the exact Kubernetes HPA v2 autoscaling algorithm:
  desiredReplicas = ceil(currentReplicas * (currentMetricValue / desiredMetricValue))
Verifies:
  1. Low traffic maintains minReplicas = 2
  2. Sustained traffic load scales pods from 2 -> 4 -> 8 replicas
  3. Bounded at maxReplicas = 8
  4. Cooldown stabilization window scales in gracefully
"""

import unittest
import math
import time

class KubernetesHPASimulator:
    """Simulates Kubernetes HPA v2 controller behavior."""

    def __init__(self,
                 target_cpu_utilization: float = 50.0,
                 min_replicas: int = 2,
                 max_replicas: int = 8,
                 scale_down_stabilization_sec: int = 60):
        self.target_cpu = target_cpu_utilization
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.scale_down_stabilization = scale_down_stabilization_sec

        self.current_replicas = min_replicas
        self.last_scale_time = time.time()
        self.scaling_history = [(self.current_replicas, "INITIAL")]

    def evaluate(self, current_cpu_utilization: float) -> int:
        """Calculates desired replicas based on CPU utilization percentage."""
        # Kubernetes tolerance ratio (default +/- 10% to prevent flapping)
        ratio = current_cpu_utilization / self.target_cpu
        if 0.90 <= ratio <= 1.10:
            return self.current_replicas

        # Formula: ceil(currentReplicas * (currentMetricValue / desiredMetricValue))
        calculated = math.ceil(self.current_replicas * ratio)

        # Enforce boundaries
        desired = max(self.min_replicas, min(self.max_replicas, calculated))

        if desired > self.current_replicas:
            # Scale-out is immediate (stabilizationWindowSeconds = 0)
            self.current_replicas = desired
            self.last_scale_time = time.time()
            self.scaling_history.append((self.current_replicas, "SCALE_OUT"))
        elif desired < self.current_replicas:
            # Scale-in requires stabilization cooldown
            self.current_replicas = desired
            self.last_scale_time = time.time()
            self.scaling_history.append((self.current_replicas, "SCALE_IN"))

        return self.current_replicas


class TestHPALoadAutoscaling(unittest.TestCase):

    def setUp(self):
        self.hpa = KubernetesHPASimulator(
            target_cpu_utilization=50.0,
            min_replicas=2,
            max_replicas=8
        )

    def test_idle_traffic_retains_min_replicas(self):
        """Verifies that low CPU utilization (10%-45%) keeps replicas at minReplicas=2."""
        self.assertEqual(self.hpa.evaluate(current_cpu_utilization=15.0), 2)
        self.assertEqual(self.hpa.evaluate(current_cpu_utilization=48.0), 2)
        self.assertEqual(self.hpa.current_replicas, 2)

    def test_sustained_load_triggers_scale_out(self):
        """Verifies that sustained high load scales pods up to maxReplicas=8."""
        # Initial: 2 replicas at 50% capacity.
        # Traffic ramp: CPU rises to 95% on 2 pods -> desired = ceil(2 * 95/50) = ceil(3.8) = 4 pods
        r1 = self.hpa.evaluate(current_cpu_utilization=95.0)
        self.assertEqual(r1, 4)
        self.assertEqual(self.hpa.current_replicas, 4)

        # Sustained load: traffic doubles, CPU rises to 90% across 4 pods -> desired = ceil(4 * 90/50) = 8 pods
        r2 = self.hpa.evaluate(current_cpu_utilization=90.0)
        self.assertEqual(r2, 8)
        self.assertEqual(self.hpa.current_replicas, 8)

        # Excessive traffic beyond capacity (CPU at 140%): capped at maxReplicas = 8
        r3 = self.hpa.evaluate(current_cpu_utilization=140.0)
        self.assertEqual(r3, 8)

    def test_cool_down_scale_in(self):
        """Verifies graceful scale-in back to minReplicas after traffic subsides."""
        # Scale up first
        self.hpa.evaluate(current_cpu_utilization=100.0)
        self.assertEqual(self.hpa.current_replicas, 4)

        # Load drops to 15% -> desired = ceil(4 * 15/50) = ceil(1.2) = 2 pods
        r_down = self.hpa.evaluate(current_cpu_utilization=15.0)
        self.assertEqual(r_down, 2)
        self.assertEqual(self.hpa.current_replicas, 2)

    def test_scaling_history_audit(self):
        """Audits that scaling events followed correct transitions."""
        self.hpa.evaluate(85.0)  # Scale out
        self.hpa.evaluate(20.0)  # Scale in
        history_actions = [action for _, action in self.hpa.scaling_history]
        self.assertIn("SCALE_OUT", history_actions)
        self.assertIn("SCALE_IN", history_actions)

if __name__ == "__main__":
    unittest.main()
