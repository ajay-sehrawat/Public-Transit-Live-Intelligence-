# -*- coding: utf-8 -*-
"""Event Adapter Transformation Engine
Normalizes raw GPS telemetry, computes geospatial deltas, and attaches event UUIDs.
"""

import os
import sys
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from services.common.clients.route_client import RouteServiceClient
from adapter_models import RawGPSEvent, NormalizedTelemetryEvent

# Inline haversine formula for self-contained execution
import math
def compute_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    return R * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


class EventAdapterEngine:
    """Enriches raw GPS pings with transit route milestones and UUIDs."""

    def __init__(self, route_client: Optional[RouteServiceClient] = None):
        self.route_client = route_client or RouteServiceClient()

    def normalize_event(self, raw_data: Dict[str, Any]) -> NormalizedTelemetryEvent:
        event_id = str(uuid.uuid4())
        now_ms = int(time.time() * 1000)

        bus_id = raw_data.get("bus_id", "UNKNOWN")
        route_id = raw_data.get("assigned_route_id") or "ROUTE-1"
        lat = float(raw_data.get("latitude", 0.0))
        lon = float(raw_data.get("longitude", 0.0))
        speed = float(raw_data.get("speed_kmh", 0.0))
        heading = float(raw_data.get("heading", 0.0))
        ts_str = raw_data.get("event_timestamp", datetime.utcnow().isoformat())

        # Convert timestamp to epoch milliseconds
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            event_epoch_ms = int(dt.timestamp() * 1000)
        except Exception:
            event_epoch_ms = now_ms

        # Query Route Service for stop milestones
        next_stop_id = "STOP-UNKNOWN"
        next_stop_name = "Unknown Stop"
        distance_meters = 0.0
        inside_geofence = False

        route_info = self.route_client.get_route_details(route_id)
        if route_info and route_info.get("stops"):
            stops = route_info["stops"]
            min_dist = float("inf")
            target_stop = stops[0]

            for s in stops:
                d = compute_distance_meters(lat, lon, s["latitude"], s["longitude"])
                if d < min_dist:
                    min_dist = d
                    target_stop = s

            next_stop_id = target_stop["stop_id"]
            next_stop_name = target_stop["stop_name"]
            distance_meters = round(min_dist, 2)
            inside_geofence = min_dist <= target_stop.get("geofence_radius_meters", 60)
        else:
            # Fallback to nearest stop query
            nearest = self.route_client.find_nearest_stop(lat, lon, max_radius=2000.0)
            if nearest.get("found"):
                next_stop_id = nearest.get("stop_id", "STOP-001")
                next_stop_name = nearest.get("stop_name", "Nearest Transit Stop")
                distance_meters = nearest.get("distance_meters", 0.0)
                inside_geofence = nearest.get("within_geofence", False)

        return NormalizedTelemetryEvent(
            event_id=event_id,
            correlation_id=raw_data.get("correlation_id", event_id),
            bus_id=bus_id,
            route_id=route_id,
            latitude=lat,
            longitude=lon,
            speed_kmh=speed,
            heading=heading,
            next_stop_id=next_stop_id,
            next_stop_name=next_stop_name,
            distance_to_next_stop_meters=distance_meters,
            is_inside_geofence=inside_geofence,
            event_timestamp=event_epoch_ms,
            event_timestamp_iso=ts_str,
            ingest_timestamp=raw_data.get("ingest_timestamp", now_ms),
            adapted_timestamp=now_ms
        )
