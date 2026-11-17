# -*- coding: utf-8 -*-
"""Passenger Demand Estimation Engine
Maintains stop crowd metrics in Firestore (NoSQL) and prepares GCS batch dumps.
"""

import os
import sys
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

from services.common.firestore.firestore_client import TransitFirestoreClient
from demand_models import PassengerTapEvent, StopDemandResponse

STOP_NAMES = {
    "STOP-001": "Pilani Railway Station",
    "STOP-002": "Bus Stand Circle",
    "STOP-003": "Birla Museum Stop",
    "STOP-004": "BITS Main Gate",
    "STOP-005": "BITS Clock Tower",
    "STOP-006": "Vidya Vihar Terminal",
    "STOP-007": "VFAST Guest House",
    "STOP-008": "Shiv Ganga Park",
    "STOP-009": "Nutan Market Terminal",
    "STOP-010": "CEERI Main Gate",
}

class PassengerDemandEngine:
    """Computes stop-level waiting crowds and persists to NoSQL."""

    def __init__(self, firestore_client: Optional[TransitFirestoreClient] = None):
        self.db = firestore_client or TransitFirestoreClient()
        self.tap_log_buffer: List[Dict[str, Any]] = []

    def classify_crowd_level(self, waiting_count: int) -> str:
        """Classifies stop crowd congestion."""
        if waiting_count >= 100:
            return "SURGE"
        elif waiting_count >= 50:
            return "HIGH"
        elif waiting_count >= 20:
            return "MODERATE"
        return "LOW"

    def record_tap(self, event: PassengerTapEvent) -> StopDemandResponse:
        """Records boarding or alighting and updates Firestore NoSQL document."""
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        stop_id = event.stop_id
        stop_name = STOP_NAMES.get(stop_id, f"Stop {stop_id}")

        doc_ref = self.db.collection("passenger_demand").document(stop_id)
        snapshot = doc_ref.get()

        current = snapshot.to_dict() if snapshot.exists else {
            "stop_id": stop_id,
            "stop_name": stop_name,
            "waiting_passenger_count": 15, # Baseline crowd
            "rolling_hourly_boardings": 0,
            "rolling_hourly_alightings": 0
        }

        waiting = current.get("waiting_passenger_count", 0)
        boardings = current.get("rolling_hourly_boardings", 0)
        alightings = current.get("rolling_hourly_alightings", 0)

        count = event.passenger_count
        if event.event_type == "BOARDING":
            waiting = max(0, waiting - count) # Boarded bus, no longer waiting
            boardings += count
        elif event.event_type == "ALIGHTING":
            alightings += count
        else: # SENSOR_COUNT (Waiting queue detected by optical camera)
            waiting = count

        crowd_level = self.classify_crowd_level(waiting)

        updated_data = {
            "stop_id": stop_id,
            "stop_name": stop_name,
            "waiting_passenger_count": waiting,
            "crowd_level": crowd_level,
            "rolling_hourly_boardings": boardings,
            "rolling_hourly_alightings": alightings,
            "last_updated": now_iso
        }

        # Persist to Firestore NoSQL (Storage Product 2)
        doc_ref.set(updated_data)

        # Buffer tap for GCS batch archive (Storage Product 3)
        self.tap_log_buffer.append({
            "stop_id": stop_id,
            "bus_id": event.bus_id,
            "route_id": event.route_id,
            "event_type": event.event_type,
            "count": count,
            "timestamp": now_iso
        })

        return StopDemandResponse(**updated_data)

    def get_stop_demand(self, stop_id: str) -> StopDemandResponse:
        """Retrieves real-time demand for a stop."""
        doc = self.db.collection("passenger_demand").document(stop_id).get()
        if doc.exists:
            return StopDemandResponse(**doc.to_dict())

        # Return default initialized baseline
        stop_name = STOP_NAMES.get(stop_id, f"Stop {stop_id}")
        return StopDemandResponse(
            stop_id=stop_id,
            stop_name=stop_name,
            waiting_passenger_count=10,
            crowd_level="LOW",
            rolling_hourly_boardings=0,
            rolling_hourly_alightings=0,
            last_updated=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    def archive_taps_to_gcs(self, bucket_name: str = "transit-telemetry-raw-archive") -> Dict[str, Any]:
        """Simulates flushing buffered tap events to Storage Product 3 (GCS Object Store)."""
        archived_count = len(self.tap_log_buffer)
        now_ts = int(time.time())
        gcs_path = f"gs://{bucket_name}/passenger-tap-batches/taps-{now_ts}.json"

        # Clear buffer upon archival
        self.tap_log_buffer.clear()

        return {
            "status": "ARCHIVED",
            "archived_records": archived_count,
            "destination_uri": gcs_path,
            "timestamp": now_ts
        }

