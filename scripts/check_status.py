#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""System Status & Health Check Script
Checks if microservices, public web dashboard, and cloud/K8s components are running.
"""

import os
import sys
import socket
import urllib.request
import json
import subprocess

SERVICES = [
    {
        "name": "Service 8: Transport Analytics Dashboard",
        "port": 8080,
        "protocol": "HTTP",
        "health_path": "/health",
        "description": "Public Leaflet Web Dashboard & Live ETAs"
    },
    {
        "name": "Service 1: Vehicle Registry (REST)",
        "port": 8001,
        "protocol": "HTTP",
        "health_path": "/health",
        "description": "Fleet Master Inventory & Vehicle Specs"
    },
    {
        "name": "Service 1: Vehicle Registry (gRPC)",
        "port": 50051,
        "protocol": "gRPC",
        "description": "High-speed Protobuf Validation Server"
    },
    {
        "name": "Service 2: GPS Ingestion Service",
        "port": 8002,
        "protocol": "HTTP",
        "health_path": "/health",
        "description": "High-throughput Telemetry Ingestion"
    },
    {
        "name": "Service 3: Route Service (REST)",
        "port": 8003,
        "protocol": "HTTP",
        "health_path": "/health",
        "description": "Route Geometry & Stop Matrix"
    },
    {
        "name": "Service 3: Route Service (gRPC)",
        "port": 50053,
        "protocol": "gRPC",
        "description": "Nearest Stop & Haversine Lookup Server"
    },
    {
        "name": "Service 4: Event Adapter",
        "port": 8004,
        "protocol": "HTTP",
        "health_path": "/health",
        "description": "Kafka Consumer, Normalizer & ZK Leader"
    },
    {
        "name": "Service 6: Passenger Demand Service",
        "port": 8006,
        "protocol": "HTTP",
        "health_path": "/health",
        "description": "Smartcard Taps & Crowd Density API"
    },
    {
        "name": "ZooKeeper Cluster (Client Port)",
        "port": 2181,
        "protocol": "TCP",
        "description": "Distributed Coordination & Leader Election"
    },
    {
        "name": "Prometheus Server",
        "port": 9090,
        "protocol": "HTTP",
        "health_path": "/-/healthy",
        "description": "Metrics Collector & Time-Series DB"
    },
    {
        "name": "Grafana Dashboard UI",
        "port": 3000,
        "protocol": "HTTP",
        "health_path": "/api/health",
        "description": "Operations & Transit KPIs Visualization"
    }
]


def check_port(host: str, port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.4)
        result = s.connect_ex((host, port))
        s.close()
        return result == 0
    except Exception:
        return False


def probe_http(url: str):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "StatusChecker/1.0"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            status_code = resp.status
            body = resp.read().decode("utf-8", errors="ignore")
            try:
                data = json.loads(body)
                return True, status_code, data
            except Exception:
                return True, status_code, body[:50]
    except Exception as e:
        return False, None, str(e)


def check_k8s_status():
    print("\n" + "=" * 70)
    print("  KUBERNETES / GKE CLOUD CLUSTER STATUS")
    print("=" * 70)
    try:
        res = subprocess.run(
            ["kubectl", "get", "pods", "-n", "transit-system", "--no-headers"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().split("\n")
            print(f"[✓] Connected to Kubernetes cluster. Found {len(lines)} pods in 'transit-system':\n")
            for line in lines:
                parts = line.split()
                name = parts[0]
                ready = parts[1]
                status = parts[2]
                color_icon = "🟢" if "Running" in status else "🟡"
                print(f"  {color_icon} {name:<42} {ready:<8} {status}")
        else:
            print("  [i] Kubernetes cluster not currently connected or namespace is empty.")
            print("      To connect to live GKE: gcloud container clusters get-credentials gke-transit-s11-prod --zone asia-south1-a")
    except Exception:
        print("  [i] kubectl CLI not found or cluster offline.")


def main():
    print("=" * 70)
    print("  S11 PUBLIC TRANSIT SYSTEM — LOCAL SERVICE STATUS CHECK")
    print("=" * 70)
    print(f"{'SERVICE NAME':<40} {'PORT':<8} {'STATUS':<15} {'HEALTH / DETAILS'}")
    print("-" * 70)

    any_running = False

    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]
        proto = svc["protocol"]
        health_path = svc.get("health_path")

        is_open = check_port("127.0.0.1", port)

        if is_open:
            any_running = True
            status_str = "🟢 RUNNING"
            detail_str = "Port Open"

            if health_path and proto == "HTTP":
                ok, code, data = probe_http(f"http://127.0.0.1:{port}{health_path}")
                if ok:
                    if isinstance(data, dict):
                        detail_str = f"HTTP {code} ({data.get('status', 'OK')})"
                    else:
                        detail_str = f"HTTP {code}"
                else:
                    detail_str = "No HTTP Health Response"

            print(f"{name:<40} {port:<8} {status_str:<15} {detail_str}")
        else:
            print(f"{name:<40} {port:<8} {'⚪ STOPPED':<15} {svc['description']}")

    print("-" * 70)

    if not any_running:
        print("\n[!] NO LOCAL SERVICES ARE CURRENTLY LISTENING ON STANDARD PORTS.")
        print("\n👉 TO START THE LIVE WEB DASHBOARD LOCALLY:")
        print("   Run: python3 services/08-transport-analytics/main.py")
        print("   Then open your browser at: http://localhost:8080/\n")
        print("👉 TO START THE VEHICLE REGISTRY:")
        print("   Run: python3 services/01-vehicle-registry/main.py\n")
        print("👉 TO START GPS INGESTION:")
        print("   Run: python3 services/02-gps-ingestion/main.py\n")
        print("👉 TO RUN ALL 14 TEST SUITES:")
        print("   Run: python3 services/08-transport-analytics/test_transport_analytics.py")
    else:
        print("\n[✓] At least one local service is active.")
        print("    If Service 8 is running, visit: http://localhost:8080/ in your browser.")

    check_k8s_status()
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
