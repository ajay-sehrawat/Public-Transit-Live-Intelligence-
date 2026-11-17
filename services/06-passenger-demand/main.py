# -*- coding: utf-8 -*-
"""Service 6: Passenger Demand Microservice
Ingests smartcard/sensor taps, updates Firestore NoSQL crowd metrics, and dumps batch logs to GCS.
"""

import os
import sys
import logging
from typing import Dict, Any, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.dirname(__file__))

from services.common.compat import FastAPI, HTTPException, status, CORSMiddleware
from services.common.firestore.firestore_client import TransitFirestoreClient
from demand_engine import PassengerDemandEngine
from demand_models import PassengerTapEvent, StopDemandResponse

try:
    import uvicorn
except ImportError:
    uvicorn = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PaxDemand] %(message)s")
logger = logging.getLogger("PassengerDemandService")

app = FastAPI(
    title="Passenger Demand Service",
    description="Estimates real-time stop crowd levels and manages NoSQL crowd metrics.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine: Optional[PassengerDemandEngine] = None
TOTAL_TAPS = 0

@app.on_event("startup")
def startup():
    global engine
    logger.info("Initializing Passenger Demand Service...")
    engine = PassengerDemandEngine()
    logger.info("[✓] Passenger Demand Service ready.")

@app.get("/health", tags=["Observability"])
def health_check():
    return {
        "status": "UP",
        "service": "passenger-demand",
        "buffered_taps": len(engine.tap_log_buffer) if engine else 0,
        "total_taps_processed": TOTAL_TAPS
    }

@app.get("/metrics", tags=["Observability"])
def metrics():
    return (
        f"# HELP passenger_demand_taps_total Total smartcard/sensor taps processed\n"
        f"# TYPE passenger_demand_taps_total counter\n"
        f"passenger_demand_taps_total {TOTAL_TAPS}\n"
    )

@app.post("/api/v1/demand/tap", response_model=StopDemandResponse, tags=["Passenger Ingestion"])
def record_tap(payload: PassengerTapEvent):
    """Ingests smartcard tap or optical queue counter event."""
    global TOTAL_TAPS
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized.")
    TOTAL_TAPS += 1
    return engine.record_tap(payload)

@app.get("/api/v1/demand/stops/{stop_id}", response_model=StopDemandResponse, tags=["Passenger Demand"])
def get_stop_demand(stop_id: str):
    """Retrieves real-time crowd index for a transit stop from NoSQL Firestore."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized.")
    return engine.get_stop_demand(stop_id)

@app.post("/api/v1/demand/archive", tags=["Object Storage Archival"])
def archive_taps():
    """Flushes buffered tap events to Storage Product 3 (Google Cloud Storage)."""
    if not engine:
        raise HTTPException(status_code=500, detail="Engine not initialized.")
    bucket = os.environ.get("GCS_BUCKET_NAME", "transit-telemetry-raw-archive")
    return engine.archive_taps_to_gcs(bucket_name=bucket)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8006))
    logger.info(f"Starting Passenger Demand Service on port {port}...")
    if uvicorn:
        uvicorn.run(app, host="0.0.0.0", port=port)

