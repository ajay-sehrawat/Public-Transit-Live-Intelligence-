#!/usr/bin/env bash
# ==============================================================================
# S11: Google Cloud Project Setup & API Initialization Script
# Prepares your GCP Project with all required free services and APIs
# ==============================================================================

set -euo pipefail

echo "================================================================="
echo "  S11 Public Transportation System: GCP Environment Setup       "
echo "================================================================="

# Check for gcloud CLI
if ! command -v gcloud &> /dev/null; then
    echo "[!] gcloud CLI is not detected in your PATH."
    echo "    Install Google Cloud SDK from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Retrieve active project
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || true)

if [ -z "$CURRENT_PROJECT" ] || [ "$CURRENT_PROJECT" = "(unset)" ]; then
    echo "[!] No active GCP project configured."
    read -rp "Enter your GCP Project ID: " PROJECT_ID
    gcloud config set project "$PROJECT_ID"
else
    PROJECT_ID="$CURRENT_PROJECT"
fi

echo "[+] Operating on GCP Project: ${PROJECT_ID}"

echo "[+] Enabling required Google Cloud APIs (All eligible under Free Tier / Credits)..."
gcloud services enable \
    compute.googleapis.com \
    container.googleapis.com \
    sqladmin.googleapis.com \
    firestore.googleapis.com \
    storage.googleapis.com \
    pubsub.googleapis.com \
    cloudfunctions.googleapis.com \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    dataproc.googleapis.com \
    monitoring.googleapis.com \
    logging.googleapis.com \
    --project="${PROJECT_ID}"

echo "[✓] All APIs enabled successfully."

# Initialize Firestore in Native Mode if not already present
echo "[+] Checking Google Cloud Firestore status..."
if ! gcloud firestore databases describe --database="(default)" --project="${PROJECT_ID}" &>/dev/null; then
    echo "[+] Creating Firestore (default) database in us-central1 (Always Free)..."
    gcloud firestore databases create --location=us-central1 --type=firestore-native --project="${PROJECT_ID}" || true
else
    echo "[✓] Firestore (default) database already active."
fi

echo "================================================================="
echo "  [✓] GCP Project is configured and ready for Terraform Part 1!  "
echo "================================================================="

