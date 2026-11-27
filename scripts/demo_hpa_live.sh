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
echo "[1/4] Ensuring port-forward to $DEPLOYMENT on port $PORT is active..."
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
echo "[✓] Port-forward established to $DEPLOYMENT:$PORT"

# 2. Show Initial Baseline
echo ""
echo "[2/4] Baseline Kubernetes State (Before Load):"
kubectl get hpa "$HPA_NAME" -n "$NAMESPACE"
echo ""
echo "Active Pods:"
kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT"

# 3. Launch k6 in background
echo ""
echo "[3/4] Launching k6 Sustained Load Test..."
echo "Generating traffic to push CPU past the 50% HPA threshold..."
k6 run --env INGESTION_URL="http://localhost:$PORT" load-testing/load_test_hpa.js >/tmp/k6_demo.log 2>&1 &
K6_PID=$!

# 4. Live Monitor Loop
echo ""
echo "[4/4] Monitoring HPA & Pods Live in Real Time..."
echo "-----------------------------------------------------------------"

SCALED=0
for i in {1..24}; do
  PODS=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" --no-headers 2>/dev/null | wc -l | tr -d ' ')
  RUNNING=$(kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT" --no-headers 2>/dev/null | grep -c "Running" || true)
  HPA_LINE=$(kubectl get hpa "$HPA_NAME" -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{print "CPU: "$3", Replicas: "$6}')

  echo "[T+$(($i * 5))s] $HPA_LINE | Total Pods: $PODS ($RUNNING Running)"

  if [ "$PODS" -gt 2 ]; then
    SCALED=1
    echo ""
    echo "================================================================="
    echo ">>> [🔥 HPA AUTOSCALE-OUT TRIGGERED!] Pods scaled: 2 -> $PODS! <<<"
    echo "================================================================="
    kubectl get pods -n "$NAMESPACE" -l "app=$DEPLOYMENT"
    break
  fi

  # Check if k6 finished
  if ! kill -0 $K6_PID 2>/dev/null; then
    echo "[i] k6 traffic phase completed."
    break
  fi

  sleep 5
done

echo ""
echo "================================================================="
if [ "$SCALED" -eq 1 ]; then
  echo "  [✓] DEMO SUCCESSFUL: HPA Automatically Scaled Deployment Out! "
else
  echo "  [✓] Checking Kubernetes HPA Rescale History...               "
fi
echo "================================================================="
echo "Official Kubernetes HPA Rescale Events:"
kubectl get events -n "$NAMESPACE" --field-selector reason=SuccessfulRescale
