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
    speed_kmh: float = Field(..., example=34.5, description="Current velocity in km/h")
    heading: float = Field(..., example=182.0, description="Compass bearing (0-360 degrees)")
    timestamp: str = Field(..., example="2026-11-18T02:15:00Z", description="ISO-8601 UTC timestamp")

    @validator("timestamp")
    def validate_timestamp(cls, v):
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
            return v
        except Exception:
            raise ValueError("Invalid ISO-8601 timestamp format")

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
