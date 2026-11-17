# -*- coding: utf-8 -*-
"""Service 2: GPS Ingestion Service (FastAPI)
High-throughput ingestion entrypoint validating bus telemetry via gRPC and publishing to Kafka.
"""

import os
import sys
import time
import uuid
import logging
from typing import Optional, List
from services.common.compat import FastAPI, HTTPException, status, CORSMiddleware
try:
    import uvicorn
except ImportError:
    uvicorn = None

# Add repo root and service directory to path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from services.common.clients.vehicle_client import VehicleRegistryClient
from services.common.kafka.kafka_client import TransitKafkaProducer
from services.common.zookeeper.zk_client import ZooKeeperClient
from services.common.zookeeper.config_watcher import DistributedConfigManager
from services.common.zookeeper.node_registry import EphemeralNodeRegistry
from gps_models import (
    GPSTelemetryPayload,
    BatchTelemetryPayload,
    IngestionResponse,
    BatchIngestionResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [GPS-Ingest] %(message)s"
)
logger = logging.getLogger("GPSIngestionService")

app = FastAPI(
    title="GPS Ingestion Service",
    description="High-throughput telemetry ingestion entrypoint validating bus pings via gRPC and streaming to Kafka.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Operational Metrics
INGEST_TOTAL = 0
INGEST_ACCEPTED = 0
INGEST_REJECTED = 0

# Core Service Dependencies
vehicle_client: Optional[VehicleRegistryClient] = None
kafka_producer: Optional[TransitKafkaProducer] = None
zk_client: Optional[ZooKeeperClient] = None
config_manager: Optional[DistributedConfigManager] = None
node_registry: Optional[EphemeralNodeRegistry] = None

POD_ID = os.environ.get("HOSTNAME", f"gps-ingest-{uuid.uuid4().hex[:6]}")
RAW_TOPIC = "bus-gps-raw"

@app.on_event("startup")
def startup_event():
    global vehicle_client, kafka_producer, zk_client, config_manager, node_registry
    logger.info(f"Initializing GPS Ingestion Service (Pod ID: {POD_ID})...")

    # 1. Initialize Vehicle Registry gRPC Client
    vehicle_client = VehicleRegistryClient()

    # 2. Initialize Kafka Producer
    kafka_producer = TransitKafkaProducer()

    # 3. Initialize ZooKeeper Coordination
    zk_client = ZooKeeperClient(session_id=f"session-{POD_ID}")
    config_manager = DistributedConfigManager(zk_client)
    node_registry = EphemeralNodeRegistry(zk_client)

    # Register this pod as an active ephemeral ingestion gateway
    node_registry.register_node(POD_ID, {
        "pod_id": POD_ID,
        "role": "gps-ingest-gateway",
        "registered_at": int(time.time() * 1000)
    })
    logger.info(f"[✓] GPS Ingestion Service ready on pod {POD_ID}")

@app.on_event("shutdown")
def shutdown_event():
    global node_registry, zk_client
    logger.info("Shutting down GPS Ingestion Service...")
    if node_registry:
        node_registry.deregister()
    if zk_client:
        zk_client.close()

@app.get("/health", tags=["Observability"])
def health_check():
    return {
        "status": "UP",
        "service": "gps-ingestion",
        "pod_id": POD_ID,
        "kafka_connected": kafka_producer is not None,
        "zookeeper_connected": zk_client is not None,
        "metrics": {
            "total_received": INGEST_TOTAL,
            "accepted": INGEST_ACCEPTED,
            "rejected": INGEST_REJECTED
        }
    }

@app.get("/metrics", tags=["Observability"])
def metrics():
    """Prometheus-compatible plain text metrics."""
    return (
        f"# HELP gps_ingest_total Total GPS telemetry pings received\n"
        f"# TYPE gps_ingest_total counter\n"
        f"gps_ingest_total {INGEST_TOTAL}\n"
        f"# HELP gps_ingest_accepted Total GPS pings validated and streamed to Kafka\n"
        f"# TYPE gps_ingest_accepted counter\n"
        f"gps_ingest_accepted {INGEST_ACCEPTED}\n"
        f"# HELP gps_ingest_rejected Total GPS pings rejected by validation\n"
        f"# TYPE gps_ingest_rejected counter\n"
        f"gps_ingest_rejected {INGEST_REJECTED}\n"
    )

@app.post("/api/v1/telemetry", status_code=status.HTTP_202_ACCEPTED,
          response_model=IngestionResponse, tags=["Telemetry Ingestion"])
def ingest_telemetry(payload: GPSTelemetryPayload):
    """Ingests, validates, and streams a single GPS location coordinate."""
    global INGEST_TOTAL, INGEST_ACCEPTED, INGEST_REJECTED
    INGEST_TOTAL += 1
    correlation_id = str(uuid.uuid4())
    now_ms = int(time.time() * 1000)

    # 1. Low-Latency Inter-Service gRPC Validation (Service 1)
    validation = vehicle_client.validate_vehicle(payload.bus_id)
    if not validation.get("is_valid", False):
        INGEST_REJECTED += 1
        logger.warning(f"Rejected telemetry for {payload.bus_id}: {validation.get('message')}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "VEHICLE_VALIDATION_FAILED",
                "bus_id": payload.bus_id,
                "reason": validation.get("message"),
                "status": validation.get("status")
            }
        )

    assigned_route = validation.get("assigned_route_id")

    # 2. Check ZooKeeper dynamic speed limit / restrictions
    speed_limit = 80.0
    if config_manager:
        speed_limit = config_manager.get_config("max_speed_kmh", 80.0)
    if payload.speed_kmh > speed_limit + 30.0:
        logger.warning(f"Speed anomaly detected for {payload.bus_id}: {payload.speed_kmh} km/h (Limit: {speed_limit})")

    # 3. Construct Raw Telemetry Kafka Message
    kafka_message = {
        "correlation_id": correlation_id,
        "bus_id": payload.bus_id,
        "assigned_route_id": assigned_route,
        "latitude": payload.latitude,
        "longitude": payload.longitude,
        "speed_kmh": payload.speed_kmh,
        "heading": payload.heading,
        "event_timestamp": payload.timestamp,
        "ingest_timestamp": now_ms,
        "ingest_pod": POD_ID
    }

    # 4. Stream to Kafka topic 'bus-gps-raw' (Partition Key: bus_id)
    kafka_producer.send(RAW_TOPIC, key=payload.bus_id, value=kafka_message)
    INGEST_ACCEPTED += 1

    return IngestionResponse(
        status="ACCEPTED",
        correlation_id=correlation_id,
        bus_id=payload.bus_id,
        assigned_route_id=assigned_route,
        ingest_timestamp=now_ms,
        message="Telemetry validated and published to bus-gps-raw"
    )

@app.post("/api/v1/telemetry/batch", status_code=status.HTTP_202_ACCEPTED,
          response_model=BatchIngestionResponse, tags=["Telemetry Ingestion"])
def ingest_telemetry_batch(payload: BatchTelemetryPayload):
    """High-throughput batch ingestion for vehicular IoT gateways."""
    results = []
    accepted = 0
    rejected = 0

    for ping in payload.pings:
        try:
            res = ingest_telemetry(ping)
            results.append(res)
            accepted += 1
        except HTTPException as e:
            rejected += 1
            results.append(IngestionResponse(
                status="REJECTED",
                correlation_id=str(uuid.uuid4()),
                bus_id=ping.bus_id,
                assigned_route_id=None,
                ingest_timestamp=int(time.time() * 1000),
                message=str(e.detail)
            ))

    return BatchIngestionResponse(
        status="COMPLETED",
        total_received=len(payload.pings),
        accepted_count=accepted,
        rejected_count=rejected,
        details=results
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8002))
    logger.info(f"Starting GPS Ingestion Service on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
