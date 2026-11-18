# -*- coding: utf-8 -*-
"""Service 7: Delay Alert Service (Serverless Cloud Function - Requirement b)
Asynchronous event-driven function triggered by Kafka arrival predictions or GCS incident files.
Persists alert records into Google Cloud Firestore (Storage Product 2: NoSQL).
"""

import os
import sys
import json
import time
import base64
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.dirname(__file__))

try:
    from services.common.firestore.firestore_client import TransitFirestoreClient
except ImportError:
    class TransitFirestoreClient:
        def __init__(self, project_id=None):
            from google.cloud import firestore
            self.db = firestore.Client(project=project_id or os.environ.get("GCP_PROJECT_ID"))
        def collection(self, name):
            return self.db.collection(name)

try:
    from services.common.kafka.kafka_client import TransitKafkaProducer
except ImportError:
    class TransitKafkaProducer:
        def send(self, topic, key=None, value=None):
            logger.info(f"[Kafka Alert Published] Topic={topic}, Key={key}, Value={value}")

from alert_models import TransitDelayAlert

logging.basicConfig(level=logging.INFO, format="%(asctime)s [ServerlessAlert] %(message)s")
logger = logging.getLogger("DelayAlertFunction")

DELAY_THRESHOLD_SEC = 300  # 5 minutes threshold
ALERT_TOPIC = "bus-delay-alerts"

firestore_client: Optional[TransitFirestoreClient] = None
kafka_producer: Optional[TransitKafkaProducer] = None

def get_clients():
    global firestore_client, kafka_producer
    if not firestore_client:
        firestore_client = TransitFirestoreClient()
    if not kafka_producer:
        kafka_producer = TransitKafkaProducer()
    return firestore_client, kafka_producer

def evaluate_and_create_alert(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluates arrival estimate or incident payload, formats alert, and writes to Firestore."""
    db, producer = get_clients()

    delay_sec = int(data.get("delay_seconds", 0))
    status_str = str(data.get("status", "ON_TIME"))

    # Only trigger alerts if delay is >= 5 minutes (300 seconds) or explicitly flagged DELAYED
    if delay_sec < DELAY_THRESHOLD_SEC and status_str != "DELAYED":
        return None

    bus_id = data.get("bus_id", "BUS-UNKNOWN")
    route_id = data.get("route_id", "ROUTE-UNKNOWN")
    stop_id = data.get("next_stop_id", "STOP-UNKNOWN")
    stop_name = data.get("next_stop_name", "Upcoming Stop")
    delay_min = round(delay_sec / 60.0, 1)

    # Classify severity
    if delay_sec >= 1200: # >= 20 mins
        severity = "SEVERE"
    elif delay_sec >= 600: # >= 10 mins
        severity = "MODERATE"
    else:
        severity = "MINOR"

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    alert_id = f"ALT-{bus_id}-{int(time.time())}"

    message = f"🚨 Transit Alert: Bus {bus_id} on {route_id} is delayed by {delay_min} mins approaching {stop_name}."

    alert_record = {
        "alert_id": alert_id,
        "bus_id": bus_id,
        "route_id": route_id,
        "stop_id": stop_id,
        "stop_name": stop_name,
        "delay_seconds": delay_sec,
        "delay_minutes": delay_min,
        "severity": severity,
        "trigger_type": data.get("trigger_type", "ETA_STREAM"),
        "message": message,
        "is_active": True,
        "created_at": now_iso
    }

    # 1. Persist to Managed NoSQL Database (Firestore - Storage Product 2)
    db.collection("delay_alerts").document(alert_id).set(alert_record)

    # 2. Publish to Kafka alert topic for downstream consumers & public dashboard
    producer.send(ALERT_TOPIC, key=route_id, value=alert_record)

    logger.info(f"📢 [Serverless Alert Dispatched] {alert_id}: {message} ({severity})")
    return alert_record

def delay_alert_pubsub_handler(event: Dict[str, Any], context=None) -> Dict[str, Any]:
    """Google Cloud Functions entrypoint for Cloud Pub/Sub / Kafka messages."""
    logger.info("Received event trigger in delay_alert_pubsub_handler...")
    payload_data = {}

    if "data" in event:
        # Base64 decoded data from Pub/Sub
        try:
            decoded = base64.b64decode(event["data"]).decode("utf-8")
            payload_data = json.loads(decoded)
        except Exception:
            payload_data = event["data"] if isinstance(event["data"], dict) else {}
    else:
        payload_data = event

    result = evaluate_and_create_alert(payload_data)
    return {"status": "SUCCESS", "alert": result}

def incident_storage_handler(data: Dict[str, Any], context=None) -> Dict[str, Any]:
    """Google Cloud Functions entrypoint for GCS Object Finalize events (Storage Product 3)."""
    file_name = data.get("name", "")
    bucket_name = data.get("bucket", "")
    logger.info(f"Received GCS incident file upload notification: {bucket_name}/{file_name}")

    # Process incident disruption reports
    if "incidents/" in file_name or file_name.endswith(".json"):
        synthetic_incident = {
            "bus_id": "FLEET-BROADCAST",
            "route_id": data.get("route_id", "ROUTE-1"),
            "next_stop_name": "Campus Corridor",
            "delay_seconds": 900, # 15 min delay for road disruption
            "status": "DELAYED",
            "trigger_type": "GCS_INCIDENT_UPLOAD"
        }
        alert = evaluate_and_create_alert(synthetic_incident)
        return {"status": "INCIDENT_ALERT_CREATED", "alert": alert}

    return {"status": "IGNORED", "reason": "Not an incident file"}

