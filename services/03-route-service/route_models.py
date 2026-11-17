# -*- coding: utf-8 -*-
"""Data models for Route Service Microservice"""

from typing import List, Optional
import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

from services.common.compat import BaseModel, Field

class StopModel(BaseModel):
    stop_id: str = Field(..., example="STOP-001")
    stop_name: str = Field(..., example="Pilani Railway Station")
    latitude: float = Field(..., example=28.3752)
    longitude: float = Field(..., example=75.6021)
    geofence_radius_meters: int = Field(60, example=60)
    has_shelter: bool = True
    passenger_capacity: int = 100

class RouteStopModel(BaseModel):
    stop_id: str
    stop_name: str
    sequence: int
    latitude: float
    longitude: float
    geofence_radius_meters: int
    expected_travel_sec_from_prev: int
    distance_meters_from_prev: int
    scheduled_dwell_time_sec: int

class RouteModel(BaseModel):
    route_id: str = Field(..., example="ROUTE-1")
    route_short_name: str = Field(..., example="1A")
    route_long_name: str = Field(..., example="Pilani Railway Station to BITS Main Campus")
    start_terminal: str = Field(..., example="Pilani Station")
    end_terminal: str = Field(..., example="BITS Clock Tower")
    total_distance_km: float = Field(..., example=4.5)
    nominal_transit_time_min: int = Field(..., example=15)
    is_active: bool = True
    stops: List[RouteStopModel] = []

class NearestStopResult(BaseModel):
    found: bool
    stop_id: Optional[str] = None
    stop_name: Optional[str] = None
    distance_meters: float
    within_geofence: bool

