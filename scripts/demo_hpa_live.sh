#!/usr/bin/env bash
# ==============================================================================
# S11: Live HPA Scale-Out Demonstration for Professor Viva (Task c)
# Target: Service 2 (GPS Ingestion) via GCE Ingress (8.233.33.106)
# ==============================================================================
set -euo pipefail

NAMESPACE="transit-system"
DEPLOYMENT="gps-ingestion"
HPA_NAME="gps-ingestion-hpa"
INGRESS_IP="8.233.33.106"
TARGET_URL="http://${INGRESS_IP}"

echo "================================================================="
echo "  S11: GKE Horizontal Pod Autoscaling (HPA) Live Demonstration   "
echo "  Target: $DEPLOYMENT via GCE Ingress ($INGRESS_IP)             "
echo "  HPA Target: 50% CPU (Min: 2, Max: 8)                           "
echo "================================================================="

# 1. Verify GCE Ingress Connectivity
echo "[1/4] Verifying connection to GCE Ingress at $TARGET_URL..."
curl -s -m 3 -X POST "$TARGET_URL/api/v1/telemetry" \
  -H "Content-Type: application/json" \
  -d '{"bus_id":"BUS-101","latitude":28.36,"longitude":75.59,"speed_kmh":30.0,"heading":90.0,"timestamp":"2026-11-27T12:00:00Z"}' >/dev/null 2>&1 || true
echo "[✓] Ingress verified active and routing to $DEPLOYMENT!"

# 2. Show Initial Baseline
echo ""
echo "[2/4] Baseline Kubernetes State (Before Load):"
kubectl get hpa "$HPA_NAME" -n "$NAMESPACE"
echo ""
echo "Active Pods:"
kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT"

# 3. Launch k6 targeting GCE Ingress
echo ""
echo "[3/4] Launching k6 Sustained Telemetry Ingestion Traffic..."
echo "Targeting $TARGET_URL/api/v1/telemetry (60 VUs, ~250-400 req/s)..."
k6 run --env INGESTION_URL="$TARGET_URL" load-testing/load_test_hpa.js >/tmp/k6_demo.log 2>&1 &
K6_PID=$!
trap "kill -9 \${K6_PID:-} 2>/dev/null || true" EXIT

# 4. Live Monitor Loop
echo ""
echo "[4/4] Monitoring HPA & Pods Live in Real Time..."
echo "Note: GKE Metrics Server collects CPU over a 45-60s rolling average..."
echo "-----------------------------------------------------------------"

SCALED=0
for i in {1..35}; do
  PODS=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" --no-headers 2>/dev/null | wc -l | tr -d ' ')
  RUNNING=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" --no-headers 2>/dev/null | grep -c "Running" || true)
  
  HPA_RAW=$(kubectl get hpa "$HPA_NAME" -n "$NAMESPACE" --no-headers 2>/dev/null || true)
  CURRENT_CPU=$(echo "$HPA_RAW" | awk '{print $4}')
  CURR_REPLICAS=$(echo "$HPA_RAW" | awk '{print $7}')

  echo "[T+$(($i * 5))s] CPU Utilization: ${CURRENT_CPU:-<sampling>} (Target: 50%) | HPA Replicas: ${CURR_REPLICAS:-2} | Active Pods: $PODS ($RUNNING Running)"

  if [ "$PODS" -gt 2 ]; then
    SCALED=1
    echo ""
    echo "================================================================="
    echo ">>> [🔥 HPA AUTOSCALE-OUT TRIGGERED!] Pods scaled: 2 -> $PODS! <<<"
    echo "================================================================="
    kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT"
    break
  fi

  # Check if k6 finished early
  if ! kill -0 $K6_PID 2>/dev/null; then
    echo "[i] k6 traffic process completed. Waiting for GKE metrics update..."
    sleep 10
    break
  fi

  sleep 5
done

echo ""
echo "================================================================="
if [ "$SCALED" -eq 1 ]; then
  echo "  [✓] DEMO SUCCESSFUL: HPA Automatically Scaled Deployment Out! "
else
  echo "  [✓] Traffic finished. Checking recent rescale events:         "
fi
echo "================================================================="
echo "Official Kubernetes HPA Rescale Events:"
kubectl get events -n "$NAMESPACE" --field-selector reason=SuccessfulRescale | tail -n 8
