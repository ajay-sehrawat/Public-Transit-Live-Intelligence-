#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate high concurrent telemetry traffic to trigger live Kubernetes HPA scale-up.
Target: http://8.233.33.106/api/v1/telemetry (GPS Ingestion Service & HPA)
"""

import sys
import time
import json
import urllib.request
import concurrent.futures
import subprocess

TARGET_URL = "http://8.233.33.106/api/v1/telemetry"
PAYLOAD = json.dumps({
    "bus_id": "BUS-101",
    "latitude": 28.3645,
    "longitude": 75.5885,
    "speed_kmh": 36.5,
    "heading": 180.0,
    "timestamp": "2026-11-20T10:00:00Z"
}).encode("utf-8")

HEADERS = {"Content-Type": "application/json"}

def send_request(request_id):
    """Sends a single telemetry request to the ingestion endpoint."""
    try:
        req = urllib.request.Request(TARGET_URL, data=PAYLOAD, headers=HEADERS, method="POST")
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            return resp.status
    except Exception as e:
        return str(e)

def get_hpa_status():
    """Queries current GKE HPA state via kubectl."""
    try:
        res = subprocess.run(
            ["kubectl", "get", "hpa", "gps-ingestion-hpa", "-n", "transit-system", "--no-headers"],
            capture_output=True, text=True, timeout=3
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().split()
            # NAME REFERENCE TARGETS MIN MAX REPLICAS
            return f"Replicas: {parts[-1]} | Targets: {parts[2]}"
    except Exception:
        pass
    return "Querying HPA..."

def main():
    print("=" * 75)
    print("  S11: REAL-TIME WORKLOAD GENERATOR FOR LIVE KUBERNETES HPA SCALE-UP")
    print(f"  Target: {TARGET_URL}")
    print("=" * 75)
    print(f"[*] Initial State -> {get_hpa_status()}\n")

    print("[+] Starting high-concurrency request surge (50 concurrent threads)...")
    print("[+] Watch the HPA scale up pods in another terminal using:")
    print("    kubectl get hpa -n transit-system -w\n")

    success_count = 0
    start_time = time.time()
    total_requests = 1000
    workers = 50

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(send_request, i) for i in range(total_requests)]
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            res = future.result()
            if res in (200, 202):
                success_count += 1
            if i % 100 == 0 or i == total_requests:
                elapsed = time.time() - start_time
                rps = round(i / elapsed, 1)
                hpa_info = get_hpa_status()
                print(f"  [{i:>4}/{total_requests}] Requests Sent ({rps} req/s) | Success: {success_count} | {hpa_info}")

    print("\n" + "=" * 75)
    print("  [✓] WORKLOAD SURGE COMPLETED SUCCESSFULLY!")
    print(f"  Total Sent: {total_requests} requests in {round(time.time() - start_time, 2)}s")
    print("=" * 75)
    print("\nCheck live pods now:")
    print("  kubectl get pods -n transit-system -l app=gps-ingestion")
    print("  kubectl get hpa -n transit-system\n")

if __name__ == "__main__":
    main()

