# -*- coding: utf-8 -*-
"""Data models for Service 6: Passenger Demand Service"""

import os
import sys
from typing import Optional, List, Dict, Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

from services.common.compat import BaseModel, Field

class PassengerTapEvent(BaseModel):
    stop_id: str = Field(..., example="STOP-004")
    bus_id: Optional[str] = Field(None, example="BUS-101")
    route_id: Optional[str] = Field(None, example="ROUTE-1")
    event_type: str = Field("BOARDING", example="BOARDING") # BOARDING, ALIGHTING, SENSOR_COUNT
    passenger_count: int = Field(1, ge=1, example=1)
    timestamp: Optional[str] = None

class StopDemandResponse(BaseModel):
    stop_id: str = ""
    stop_name: str = ""
    waiting_passenger_count: int = 0
    crowd_level: str = "LOW" # LOW, MODERATE, HIGH, SURGE
    rolling_hourly_boardings: int = 0
    rolling_hourly_alightings: int = 0
    last_updated: str = ""

class RouteDemandSummary(BaseModel):
    route_id: str = ""
    total_waiting_passengers: int = 0
    average_stop_crowd_level: str = "LOW"
    congested_stops: List[str] = []

