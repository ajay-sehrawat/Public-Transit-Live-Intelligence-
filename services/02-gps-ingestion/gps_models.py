# -*- coding: utf-8 -*-
"""Pydantic Data Models for Service 2: GPS Ingestion Service"""

import os
import sys
from datetime import datetime
from typing import Optional, List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

from services.common.compat import BaseModel, Field, validator

class GPSTelemetryPayload(BaseModel):
    bus_id: str = Field(..., example="BUS-101", description="Unique bus identifier")
    latitude: float = Field(..., example=28.3638, description="WGS-84 Latitude")
    longitude: float = Field(..., example=75.5872, description="WGS-84 Longitude")
    speed_kmh: float = Field(0.0, example=34.5, description="Current velocity in km/h")
    heading: float = Field(0.0, example=182.0, description="Compass bearing (0-360 degrees)")
    timestamp: any = Field(..., example="2026-11-18T02:15:00Z", description="ISO-8601 UTC timestamp or Unix epoch")

    @validator("latitude")
    def validate_latitude(cls, v):
        if v is not None and not (-90.0 <= float(v) <= 90.0):
            raise ValueError(f"Latitude {v} out of bounds [-90.0, +90.0]")
        return float(v)

    @validator("longitude")
    def validate_longitude(cls, v):
        if v is not None and not (-180.0 <= float(v) <= 180.0):
            raise ValueError(f"Longitude {v} out of bounds [-180.0, +180.0]")
        return float(v)

    @validator("timestamp")
    def validate_timestamp(cls, v):
        if isinstance(v, (int, float)):
            from datetime import timezone
            return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
        try:
            datetime.fromisoformat(str(v).replace("Z", "+00:00"))
            return str(v)
        except Exception:
            raise ValueError("Invalid ISO-8601 or epoch timestamp format")

class BatchTelemetryPayload(BaseModel):
    pings: List[GPSTelemetryPayload] = []

class IngestionResponse(BaseModel):
    status: str = "ACCEPTED"
    correlation_id: str = ""
    bus_id: str = ""
    assigned_route_id: Optional[str] = None
    ingest_timestamp: int = 0
    message: str = ""

class BatchIngestionResponse(BaseModel):
    status: str = "COMPLETED"
    total_received: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    details: List[IngestionResponse] = []
