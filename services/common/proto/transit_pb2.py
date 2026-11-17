# -*- coding: utf-8 -*-
"""Generated Protocol Buffers module for transit.proto (Python Representation)"""

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class VehicleValidationRequest:
    bus_id: str = ""

@dataclass
class VehicleValidationResponse:
    is_valid: bool = False
    bus_id: str = ""
    status: str = "UNKNOWN"
    assigned_route_id: str = ""
    message: str = ""

@dataclass
class VehicleDetailsRequest:
    bus_id: str = ""

@dataclass
class VehicleDetailsResponse:
    bus_id: str = ""
    license_plate: str = ""
    model: str = ""
    capacity: int = 0
    propulsion_type: str = "ELECTRIC"
    status: str = "ACTIVE"
    assigned_route_id: str = ""
    created_at: str = ""

@dataclass
class ListVehiclesRequest:
    status_filter: str = ""

@dataclass
class ListVehiclesResponse:
    vehicles: List[VehicleDetailsResponse] = field(default_factory=list)

@dataclass
class StopInfo:
    stop_id: str = ""
    stop_name: str = ""
    sequence: int = 0
    latitude: float = 0.0
    longitude: float = 0.0
    geofence_radius_meters: int = 60
    expected_travel_sec_from_prev: int = 180
    distance_meters_from_prev: int = 1000
    scheduled_dwell_time_sec: int = 30

@dataclass
class RouteDetailsRequest:
    route_id: str = ""

@dataclass
class RouteDetailsResponse:
    route_id: str = ""
    route_short_name: str = ""
    route_long_name: str = ""
    start_terminal: str = ""
    end_terminal: str = ""
    total_distance_km: float = 0.0
    nominal_transit_time_min: int = 0
    stops: List[StopInfo] = field(default_factory=list)

@dataclass
class NearestStopRequest:
    latitude: float = 0.0
    longitude: float = 0.0
    max_radius_meters: float = 500.0

@dataclass
class NearestStopResponse:
    found: bool = False
    stop_id: str = ""
    stop_name: str = ""
    distance_meters: float = 0.0
    within_geofence: bool = False

@dataclass
class ListRoutesRequest:
    active_only: bool = True

@dataclass
class RouteSummary:
    route_id: str = ""
    route_short_name: str = ""
    route_long_name: str = ""
    total_distance_km: float = 0.0
    stop_count: int = 0

@dataclass
class ListRoutesResponse:
    routes: List[RouteSummary] = field(default_factory=list)

