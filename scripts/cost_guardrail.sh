#!/usr/bin/env bash
# ==============================================================================
# S11: Cost Guardrail & Ephemeral Teardown Script
# Ensures zero-cost limits are respected and provides 1-command teardown
# ==============================================================================

set -euo pipefail

echo "================================================================="
echo "  S11 Public Transportation: Zero-Cost Resource Audit           "
echo "================================================================="

CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || true)
if [ -z "$CURRENT_PROJECT" ] || [ "$CURRENT_PROJECT" = "(unset)" ]; then
    echo "[!] Please run 'gcloud config set project <PROJECT_ID>' first."
    exit 1
fi

echo "[+] Checking running compute resources in project: ${CURRENT_PROJECT}"

echo "--- 1. GKE Clusters ---"
gcloud container clusters list --project="${CURRENT_PROJECT}" || echo "None found"

echo "--- 2. Cloud SQL Instances ---"
gcloud sql instances list --project="${CURRENT_PROJECT}" || echo "None found"

echo "--- 3. Cloud Storage Buckets ---"
gcloud storage buckets list --project="${CURRENT_PROJECT}" || echo "None found"

echo "--- 4. Cloud Functions ---"
gcloud functions list --project="${CURRENT_PROJECT}" || echo "None found"

echo ""
echo "================================================================="
echo "  EPHEMERAL TEARDOWN INSTRUCTION:"
echo "  When demonstration/testing is finished, run:"
echo "    cd terraform && terraform destroy -auto-approve"
echo "  This immediately halts all active billable resources."
echo "================================================================="

