# -*- coding: utf-8 -*-
"""Service 4: Event Adapter Microservice
Consumes raw GPS events from Kafka, enriches with route milestones, and emits normalized events.
"""

import os
import sys
import time
import threading
import logging
from typing import Dict, Any, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.dirname(__file__))

from services.common.compat import FastAPI, HTTPException, status, CORSMiddleware, run_server
from services.common.kafka.kafka_client import TransitKafkaConsumer, TransitKafkaProducer
from services.common.clients.route_client import RouteServiceClient
from adapter_engine import EventAdapterEngine
from adapter_models import RawGPSEvent, NormalizedTelemetryEvent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [EventAdapter] %(message)s"
)
logger = logging.getLogger("EventAdapterService")

app = FastAPI(
    title="Event Adapter Service",
    description="Normalizes raw GPS telemetry, attaches event UUIDs, and enriches with transit route milestones.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RAW_TOPIC = "bus-gps-raw"
NORMALIZED_TOPIC = "bus-gps-normalized"

# Operational Metrics
ADAPTED_COUNT = 0
ERROR_COUNT = 0

engine: Optional[EventAdapterEngine] = None
kafka_producer: Optional[TransitKafkaProducer] = None
kafka_consumer: Optional[TransitKafkaConsumer] = None
is_running = False

def process_raw_message(record: Dict[str, Any]):
    """Processes a single raw telemetry event from Kafka."""
    global ADAPTED_COUNT, ERROR_COUNT
    try:
        raw_val = record.get("value", {})
        normalized = engine.normalize_event(raw_val)

        # Publish to normalized topic
        kafka_producer.send(
            NORMALIZED_TOPIC,
            key=normalized.bus_id,
            value=normalized.dict()
        )
        ADAPTED_COUNT += 1
        logger.info(f"Normalized event {normalized.event_id} for bus {normalized.bus_id} -> Next Stop: {normalized.next_stop_name}")
    except Exception as e:
        ERROR_COUNT += 1
        logger.error(f"Error adapting raw message: {e}")

def run_consumer_loop():
    """Streaming background consumer loop polling from Kafka."""
    logger.info(f"Starting consumer loop on topic '{RAW_TOPIC}'...")
    while is_running:
        try:
            records = kafka_consumer.poll(max_records=50)
            for record in records:
                process_raw_message(record)
            time.sleep(0.05)
        except Exception as e:
            logger.error(f"Error in Kafka consumer polling: {e}")
            time.sleep(1.0)

@app.on_event("startup")
def startup():
    global engine, kafka_producer, kafka_consumer, is_running
    logger.info("Initializing Event Adapter Service...")
    engine = EventAdapterEngine()
    kafka_producer = TransitKafkaProducer()
    kafka_consumer = TransitKafkaConsumer(topic=RAW_TOPIC, group_id="event-adapter-group")

    # Register in-memory subscriber callback if running in-memory
    kafka_consumer.subscribe_callback(process_raw_message)

    is_running = True
    consumer_thread = threading.Thread(target=run_consumer_loop, daemon=True)
    consumer_thread.start()
    logger.info("[✓] Event Adapter Service started successfully.")

@app.on_event("shutdown")
def shutdown():
    global is_running
    is_running = False

@app.get("/health", tags=["Observability"])
def health_check():
    return {
        "status": "UP",
        "service": "event-adapter",
        "adapted_events_total": ADAPTED_COUNT,
        "error_count": ERROR_COUNT
    }

@app.get("/metrics", tags=["Observability"])
def metrics():
    return (
        f"# HELP event_adapter_processed_total Total events adapted and normalized\n"
        f"# TYPE event_adapter_processed_total counter\n"
        f"event_adapter_processed_total {ADAPTED_COUNT}\n"
        f"# HELP event_adapter_errors_total Total normalization errors\n"
        f"# TYPE event_adapter_errors_total counter\n"
        f"event_adapter_errors_total {ERROR_COUNT}\n"
    )

@app.post("/api/v1/adapt", response_model=NormalizedTelemetryEvent, tags=["Event Normalization"])
def adapt_event_http(payload: RawGPSEvent):
    """Synchronous HTTP endpoint for event adaptation."""
    if not engine:
        raise HTTPException(status_code=500, detail="Adapter engine not initialized.")
    data = payload.model_dump() if hasattr(payload, 'model_dump') else payload.dict()
    return engine.normalize_event(data)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8004))
    logger.info(f"Starting Event Adapter on port {port}...")
    run_server(app, host="0.0.0.0", port=port)
