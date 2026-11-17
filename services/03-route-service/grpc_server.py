# -*- coding: utf-8 -*-
"""gRPC Server implementation for Service 3: Route Geometry Service"""

import logging
import sys
import os

# Add service directory and parent directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.proto.transit_pb2 import (
    RouteDetailsRequest,
    RouteDetailsResponse,
    StopInfo,
    NearestStopRequest,
    NearestStopResponse,
    ListRoutesRequest,
    ListRoutesResponse,
    RouteSummary,
)
from services.common.proto.transit_pb2_grpc import (
    RouteGeometryServiceServicer,
    add_RouteGeometryServiceServicer_to_server,
    HAS_GRPC,
)
from route_db import repo

logger = logging.getLogger("RouteService.gRPC")

class RouteGeometryServicer(RouteGeometryServiceServicer):
    """Authoritative gRPC Handler for Route Service geometry & stop queries."""

    def GetRouteDetails(self, request: RouteDetailsRequest, context=None) -> RouteDetailsResponse:
        route = repo.get_route(request.route_id)
        if not route:
            return RouteDetailsResponse(route_id=request.route_id)

        stops_list = [
            StopInfo(
                stop_id=s["stop_id"],
                stop_name=s["stop_name"],
                sequence=int(s["stop_sequence"]),
                latitude=float(s["latitude"]),
                longitude=float(s["longitude"]),
                geofence_radius_meters=int(s.get("geofence_radius_meters", 60)),
                expected_travel_sec_from_prev=int(s.get("expected_travel_sec_from_prev", 180)),
                distance_meters_from_prev=int(s.get("distance_meters_from_prev", 1000)),
                scheduled_dwell_time_sec=int(s.get("scheduled_dwell_time_sec", 30))
            )
            for s in route.get("stops", [])
        ]

        return RouteDetailsResponse(
            route_id=route["route_id"],
            route_short_name=route["route_short_name"],
            route_long_name=route["route_long_name"],
            start_terminal=route["start_terminal"],
            end_terminal=route["end_terminal"],
            total_distance_km=float(route["total_distance_km"]),
            nominal_transit_time_min=int(route["nominal_transit_time_min"]),
            stops=stops_list
        )

    def FindNearestStop(self, request: NearestStopRequest, context=None) -> NearestStopResponse:
        radius = request.max_radius_meters if request.max_radius_meters > 0 else 1000.0
        result = repo.find_nearest_stop(request.latitude, request.longitude, max_radius=radius)
        return NearestStopResponse(
            found=result["found"],
            stop_id=result["stop_id"] or "",
            stop_name=result["stop_name"] or "",
            distance_meters=result["distance_meters"],
            within_geofence=result["within_geofence"]
        )

    def ListRoutes(self, request: ListRoutesRequest, context=None) -> ListRoutesResponse:
        routes = repo.list_routes(active_only=request.active_only)
        summaries = []
        for r in routes:
            stops = repo.get_route_stops(r["route_id"])
            summaries.append(RouteSummary(
                route_id=r["route_id"],
                route_short_name=r["route_short_name"],
                route_long_name=r["route_long_name"],
                total_distance_km=float(r["total_distance_km"]),
                stop_count=len(stops)
            ))
        return ListRoutesResponse(routes=summaries)

def create_grpc_server(port: int = 50053):
    if not HAS_GRPC:
        logger.warning("grpcio library is not installed on system; using direct in-memory servicer.")
        return RouteGeometryServicer()

    import grpc
    from concurrent import futures
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = RouteGeometryServicer()
    add_RouteGeometryServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"Route gRPC Server listening on port {port}")
    return server
