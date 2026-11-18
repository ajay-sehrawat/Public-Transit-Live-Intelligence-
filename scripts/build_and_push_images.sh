#!/usr/bin/env bash
# ==============================================================================
# S11: Build and Push All Transit Microservice Images to Google Artifact Registry
# ==============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || true)

if [ -z "$CURRENT_PROJECT" ] || [ "$CURRENT_PROJECT" = "(unset)" ]; then
    echo "[!] No active GCP project configured."
    read -rp "Enter your GCP Project ID: " PROJECT_ID
else
    PROJECT_ID="$CURRENT_PROJECT"
fi

REGION=${GCP_REGION:-"asia-south1"}
REPO_NAME=${REPO_NAME:-"transit-docker-repo"}
TAG=${IMAGE_TAG:-"v1.0.0"}

REGISTRY_HOST="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

echo "================================================================="
echo "  BUILDING & PUSHING S11 MICROSERVICES TO ARTIFACT REGISTRY      "
echo "================================================================="
echo "[+] GCP Project:       ${PROJECT_ID}"
echo "[+] Artifact Registry: ${REGISTRY_HOST}"
echo "[+] Image Tag:         ${TAG}"
echo "================================================================="

# 1. Ensure Artifact Registry repository exists
echo "[+] Verifying Artifact Registry repository..."
if ! gcloud artifacts repositories describe "${REPO_NAME}" --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "[+] Creating Artifact Registry repository '${REPO_NAME}'..."
    gcloud artifacts repositories create "${REPO_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="Docker repository for S11 Public Transit microservices" \
        --project="${PROJECT_ID}"
else
    echo "[✓] Repository '${REPO_NAME}' exists."
fi

# 2. Configure Docker authentication for Artifact Registry
echo "[+] Configuring Docker credential helper..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Microservices list (directory, service-name)
SERVICES=(
    "01-vehicle-registry:vehicle-registry"
    "02-gps-ingestion:gps-ingestion"
    "03-route-service:route-service"
    "04-event-adapter:event-adapter"
    "06-passenger-demand:passenger-demand"
    "08-transport-analytics:transport-analytics"
)

# 3. Build, Tag and Push each service
for entry in "${SERVICES[@]}"; do
    IFS=":" read -r dir name <<< "$entry"
    IMAGE_URI="${REGISTRY_HOST}/${name}:${TAG}"
    GCR_FALLBACK_URI="gcr.io/${PROJECT_ID}/${name}:${TAG}"

    echo ""
    echo "-----------------------------------------------------------------"
    echo "[*] Building ${name} from services/${dir}..."
    docker build -t "${IMAGE_URI}" -t "${GCR_FALLBACK_URI}" -f "${PROJECT_ROOT}/services/${dir}/Dockerfile" "${PROJECT_ROOT}"

    echo "[*] Pushing ${IMAGE_URI}..."
    docker push "${IMAGE_URI}"
    echo "[✓] ${name} pushed successfully!"
done

echo ""
echo "================================================================="
echo "  [✓] ALL 6 TRANSIT MICROSERVICE IMAGES BUILT & PUSHED!          "
echo "================================================================="

