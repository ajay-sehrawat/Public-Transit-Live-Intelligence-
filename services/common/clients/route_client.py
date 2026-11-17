# -*- coding: utf-8 -*-
"""Client SDK for inter-service communication with Service 3: Route Service
Supports gRPC (primary) with REST fallback.
"""

import os
import sys
import logging
import urllib.request
import json
from typing import Dict, Any, Optional, List

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.proto.transit_pb2 import RouteDetailsRequest, NearestStopRequest
from services.common.proto.transit_pb2_grpc import RouteGeometryServiceStub, HAS_GRPC

logger = logging.getLogger("RouteServiceClient")

class RouteServiceClient:
    """Client for querying route geometry, stops, and geospatial proximity."""

    def __init__(self,
                 grpc_target: Optional[str] = None,
                 http_target: Optional[str] = None,
                 direct_servicer=None):
        self.grpc_target = grpc_target or os.environ.get("ROUTE_SERVICE_GRPC_HOST", "localhost:50053")
        self.http_target = http_target or os.environ.get("ROUTE_SERVICE_HTTP_HOST", "http://localhost:8003")
        self.direct_servicer = direct_servicer
        self.stub = None

        if self.direct_servicer:
            self.stub = RouteGeometryServiceStub(direct_servicer=self.direct_servicer)
        elif HAS_GRPC:
            try:
                import grpc
                channel = grpc.insecure_channel(self.grpc_target)
                self.stub = RouteGeometryServiceStub(channel=channel)
            except Exception as e:
                logger.warning(f"Could not initialize gRPC channel for RouteService: {e}")

    def get_route_details(self, route_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves full route geometry and stop sequence."""
        if self.stub:
            try:
                req = RouteDetailsRequest(route_id=route_id)
                res = self.stub.GetRouteDetails(req, timeout=2.0)
                if not res.route_short_name:
                    return None
                return {
                    "route_id": res.route_id,
                    "route_short_name": res.route_short_name,
                    "route_long_name": res.route_long_name,
                    "start_terminal": res.start_terminal,
                    "end_terminal": res.end_terminal,
                    "total_distance_km": res.total_distance_km,
                    "nominal_transit_time_min": res.nominal_transit_time_min,
                    "stops": [
                        {
                            "stop_id": s.stop_id,
                            "stop_name": s.stop_name,
                            "sequence": s.sequence,
                            "latitude": s.latitude,
                            "longitude": s.longitude,
                            "geofence_radius_meters": s.geofence_radius_meters,
                            "expected_travel_sec_from_prev": s.expected_travel_sec_from_prev,
                            "distance_meters_from_prev": s.distance_meters_from_prev,
                            "scheduled_dwell_time_sec": s.scheduled_dwell_time_sec,
                        }
                        for s in res.stops
                    ],
                    "channel": "gRPC"
                }
            except Exception as e:
                logger.warning(f"gRPC GetRouteDetails failed, falling back to REST: {e}")

        # REST Fallback
        try:
            url = f"{self.http_target.rstrip('/')}/api/v1/routes/{route_id}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    data["channel"] = "REST"
                    return data
        except Exception as e:
            logger.error(f"Failed to fetch route {route_id}: {e}")
            return None

    def find_nearest_stop(self, lat: float, lon: float, max_radius: float = 1000.0) -> Dict[str, Any]:
        """Finds nearest transit stop for coordinates."""
        if self.stub:
            try:
                req = NearestStopRequest(latitude=lat, longitude=lon, max_radius_meters=max_radius)
                res = self.stub.FindNearestStop(req, timeout=2.0)
                return {
                    "found": res.found,
                    "stop_id": res.stop_id,
                    "stop_name": res.stop_name,
                    "distance_meters": res.distance_meters,
                    "within_geofence": res.within_geofence,
                    "channel": "gRPC"
                }
            except Exception as e:
                logger.warning(f"gRPC FindNearestStop failed, falling back to REST: {e}")

        # REST Fallback
        try:
            url = f"{self.http_target.rstrip('/')}/api/v1/stops/nearest?lat={lat}&lon={lon}&max_radius_meters={max_radius}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=2.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    data["channel"] = "REST"
                    return data
        except Exception as e:
            logger.error(f"Failed to find nearest stop for ({lat}, {lon}): {e}")
            return {"found": False, "distance_meters": -1.0, "within_geofence": False, "channel": "NONE"}

