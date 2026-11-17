# -*- coding: utf-8 -*-
"""Pydantic Data Models for Service 4: Event Adapter"""

import os
import sys
from typing import Optional, Dict, Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

from services.common.compat import BaseModel, Field

class RawGPSEvent(BaseModel):
    correlation_id: str = ""
    bus_id: str = ""
    assigned_route_id: Optional[str] = None
    latitude: float = 0.0
    longitude: float = 0.0
    speed_kmh: float = 0.0
    heading: float = 0.0
    event_timestamp: str = ""
    ingest_timestamp: int = 0

class NormalizedTelemetryEvent(BaseModel):
    event_id: str = ""
    correlation_id: str = ""
    bus_id: str = ""
    route_id: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    speed_kmh: float = 0.0
    heading: float = 0.0
    next_stop_id: str = ""
    next_stop_name: str = ""
    distance_to_next_stop_meters: float = 0.0
    is_inside_geofence: bool = False
    event_timestamp: int = 0       # Millisecond epoch timestamp for Flink event-time
    event_timestamp_iso: str = ""
    ingest_timestamp: int = 0
    adapted_timestamp: int = 0
