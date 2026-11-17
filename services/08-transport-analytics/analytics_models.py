# -*- coding: utf-8 -*-
"""Analytics Models for Transport Analytics API (Service 8)
Pydantic/compat schemas for web dashboard, arrivals board, and transit KPIs.
"""

from typing import List, Optional, Dict, Any
from services.common.compat import BaseModel, Field


class TransitKPIs(BaseModel):
    active_buses: int = 0
    avg_speed_kmh: float = 0.0
    alerts_count: int = 0
    timestamp: float = 0.0


class BusLiveFeedItem(BaseModel):
    bus_id: str
    route_id: str
    latitude: float
    longitude: float
    speed_kmh: float
    next_stop_id: str
    next_stop_name: str
    eta_seconds: int
    status: str = "ON_TIME"


class StopLiveFeedItem(BaseModel):
    stop_id: str
    stop_name: str
    latitude: float
    longitude: float
    geofence_radius_meters: int = 100
    current_crowd: int = 0
    crowd_level: str = "LOW"


class DelayAlertFeedItem(BaseModel):
    alert_id: str
    bus_id: str
    route_id: str
    stop_id: str
    stop_name: str
    delay_minutes: float
    severity: str
    message: str
    timestamp: float


class ArrivalFeedItem(BaseModel):
    bus_id: str
    route_id: str
    next_stop_id: str
    next_stop_name: str
    eta_seconds: int
    status: str
    delay_minutes: float = 0.0


class LiveFeedResponse(BaseModel):
    kpis: TransitKPIs
    buses: List[BusLiveFeedItem]
    stops: List[StopLiveFeedItem]
    alerts: List[DelayAlertFeedItem]
    arrivals: List[ArrivalFeedItem]


class StopArrivalsResponse(BaseModel):
    stop_id: str
    stop_name: str
    arrivals: List[ArrivalFeedItem]
    timestamp: float


class FleetStatsResponse(BaseModel):
    total_buses: int
    active_buses: int
    delayed_buses: int
    avg_speed_kmh: float
    system_health: str = "OPTIMAL"
    timestamp: float
