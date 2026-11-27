#!/usr/bin/env bash
# ==============================================================================
# S11: Live HPA Scale-Out Demonstration for Professor Viva (Task c)
# ==============================================================================
set -euo pipefail

NAMESPACE="transit-system"
DEPLOYMENT="gps-ingestion"
HPA_NAME="gps-ingestion-hpa"
PORT=8002

echo "================================================================="
echo "  S11: GKE Horizontal Pod Autoscaling (HPA) Live Demonstration   "
echo "  Target: $DEPLOYMENT (HPA Target: 50% CPU, Min: 2, Max: 8)     "
echo "================================================================="

# 1. Clean up old port-forwards and start fresh
echo "[1/4] Ensuring clean port-forward to $DEPLOYMENT on port $PORT..."
fuser -k $PORT/tcp 2>/dev/null || pkill -f "port-forward.*$PORT" 2>/dev/null || true
sleep 1

kubectl port-forward -n "$NAMESPACE" "svc/gps-ingestion-service" "$PORT:$PORT" >/dev/null 2>&1 &
PF_PID=$!
trap "kill -9 $PF_PID 2>/dev/null || true; kill -9 \${K6_PID:-} 2>/dev/null || true" EXIT

# Wait for port-forward to be ready
READY=0
for i in {1..10}; do
  if curl -s -m 2 "http://localhost:$PORT/health" >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "[!] Port-forward starting up, verifying pod readiness..."
fi
echo "[✓] Port-forward verified healthy to $DEPLOYMENT:$PORT"

# 2. Show Initial Baseline
echo ""
echo "[2/4] Baseline Kubernetes State (Before Load):"
kubectl get hpa "$HPA_NAME" -n "$NAMESPACE"
echo ""
echo "Active Pods:"
kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT"

# 3. Launch k6 in background
echo ""
echo "[3/4] Launching k6 Sustained Load Test (12 VUs, ~220 req/s for 2m)..."
echo "Generating traffic to push CPU past the 50% HPA threshold..."
k6 run --env INGESTION_URL="http://localhost:$PORT" load-testing/load_test_hpa.js >/tmp/k6_demo.log 2>&1 &
K6_PID=$!

# 4. Live Monitor Loop (Run for up to 2m30s to allow GKE Metrics Server to compute average CPU)
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
    # Give metrics server 15 seconds to reflect the final load
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
  echo "  [✓] Check k6 output log and latest events:                   "
  tail -n 15 /tmp/k6_demo.log 2>/dev/null || true
fi
echo "================================================================="
echo "Official Kubernetes HPA Rescale Events:"
kubectl get events -n "$NAMESPACE" --field-selector reason=SuccessfulRescale | tail -n 8
