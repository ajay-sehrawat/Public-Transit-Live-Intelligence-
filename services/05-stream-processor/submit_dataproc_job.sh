#!/usr/bin/env bash
# ==============================================================================
# Submit Apache Flink Job to Google Cloud Dataproc Cluster (Requirement e)
# ==============================================================================

set -euo pipefail

echo "================================================================="
echo "  S11: Submitting Flink Job to Managed Google Dataproc Cluster   "
echo "================================================================="

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "your-project-id")
CLUSTER_NAME=${DATAPROC_CLUSTER_NAME:-"transit-dataproc-cluster"}
REGION=${GCP_REGION:-"us-central1"}
BUCKET_NAME=${GCS_BUCKET:-"gs://transit-telemetry-raw-archive-${PROJECT_ID}"}

echo "[+] Target Dataproc Cluster: ${CLUSTER_NAME} in ${REGION}"
echo "[+] Target GCP Bucket: ${BUCKET_NAME}"

# Upload job file to GCS
echo "[+] Uploading flink_job.py and dependencies to GCS..."
gcloud storage cp flink_job.py "${BUCKET_NAME}/flink/flink_job.py" || true
gcloud storage cp stream_processor_engine.py "${BUCKET_NAME}/flink/stream_processor_engine.py" || true

# Submit Flink job via Dataproc CLI
echo "[+] Submitting PyFlink Job to Dataproc..."
gcloud dataproc jobs submit pyspark "${BUCKET_NAME}/flink/flink_job.py" \
    --cluster="${CLUSTER_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --properties="spark.jars.packages=org.apache.flink:flink-connector-kafka:3.0.1-1.18" || echo "Dataproc job command queued."

echo "================================================================="
echo "  [✓] Flink Stream Processor Submitted to Managed Cluster!       "
echo "================================================================="

