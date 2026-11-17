#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verification Suite for Observability Stack (Requirement h)
Validates Prometheus configuration, scrape targets, Grafana dashboard panels,
and Loki logging pipeline definitions without requiring external PyYAML.
"""

import os
import sys
import json
import re

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OBS_DIR = os.path.join(BASE_DIR, "k8s", "observability")


def test_prometheus_stack():
    print("[*] Validating Prometheus Stack Manifest...")
    prom_path = os.path.join(OBS_DIR, "prometheus-stack.yaml")
    assert os.path.exists(prom_path), f"Missing {prom_path}"

    with open(prom_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "kind: ConfigMap" in content
    assert "name: prometheus-config" in content
    assert "kind: Deployment" in content
    assert "name: prometheus-server" in content
    assert "kind: Service" in content
    assert "name: prometheus-service" in content

    required_jobs = [
        "transit-vehicle-registry",
        "transit-gps-ingestion",
        "transit-route-service",
        "transit-event-adapter",
        "transit-passenger-demand",
        "transit-transport-analytics",
        "zookeeper-cluster"
    ]
    for job in required_jobs:
        assert f'job_name: "{job}"' in content or f"job_name: '{job}'" in content or f"job_name: {job}" in content, \
            f"Prometheus config missing scrape job: {job}"

    # Verify Alert Rules
    assert "alert: HighGpsIngestionLatency" in content
    assert "alert: ActiveDelaySpike" in content
    assert "alert: PodCrashLooping" in content

    print("  [✓] Prometheus configuration contains 7 target transit services & alert rules.")


def test_grafana_stack():
    print("[*] Validating Grafana Dashboards Manifest...")
    grafana_path = os.path.join(OBS_DIR, "grafana-dashboards.yaml")
    assert os.path.exists(grafana_path), f"Missing {grafana_path}"

    with open(grafana_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "name: grafana-datasources" in content
    assert "name: grafana-transit-dashboard" in content
    assert "kind: Deployment" in content
    assert "name: grafana" in content
    assert "kind: Service" in content
    assert "name: grafana-service" in content

    # Check DataSources
    assert "name: Prometheus" in content
    assert "name: Loki" in content

    # Check Transit Operations Dashboard panels
    assert "Ingestion Throughput (req/sec)" in content
    assert "p95 API Latencies by Service (ms)" in content
    assert "HPA Dynamic Replica Scaling" in content
    assert "Active Tracked Fleet & Average Speed (km/h)" in content
    assert "Active Transit Delay Incidents (> 5 min late)" in content

    print("  [✓] Grafana provisioning verified with Prometheus/Loki datasources and 5 transit metric panels.")


def test_loki_stack():
    print("[*] Validating Loki & Promtail Logging Stack...")
    loki_path = os.path.join(OBS_DIR, "loki-stack.yaml")
    assert os.path.exists(loki_path), f"Missing {loki_path}"

    with open(loki_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "name: loki-config" in content
    assert "name: loki" in content
    assert "name: loki-service" in content
    assert "name: promtail-config" in content
    assert "kind: DaemonSet" in content
    assert "name: promtail" in content

    # Verify log scraping paths
    assert "/var/log/pods/*/*/*.log" in content
    assert "http://loki-service.transit-system.svc.cluster.local:3100/loki/api/v1/push" in content

    print("  [✓] Loki logging engine and Promtail node DaemonSet properly declared.")


if __name__ == "__main__":
    print("=" * 65)
    print("  OBSERVABILITY STACK VERIFICATION SUITE (Requirement h)")
    print("=" * 65)
    test_prometheus_stack()
    test_grafana_stack()
    test_loki_stack()
    print("=" * 65)
    print("  ALL OBSERVABILITY STACK VERIFICATIONS PASSED (3/3)")
    print("=" * 65)
