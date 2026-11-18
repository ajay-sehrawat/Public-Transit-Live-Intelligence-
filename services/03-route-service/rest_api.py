# -*- coding: utf-8 -*-
"""FastAPI REST API for Service 3: Route Service"""

import os
import sys
from typing import Optional, List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))

from services.common.compat import FastAPI, HTTPException, Query, status, CORSMiddleware
from route_db import repo
from geometry import haversine_distance, is_within_geofence
from route_models import RouteModel, StopModel, NearestStopResult

app = FastAPI(
    title="Route Service",
    description="Maintains transit routes, stops, ordered sequences, geofences, and segment distances.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REQUEST_COUNT = 0
ERROR_COUNT = 0

@app.middleware("http")
async def track_metrics(request, call_next):
    global REQUEST_COUNT, ERROR_COUNT
    REQUEST_COUNT += 1
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            ERROR_COUNT += 1
        return response
    except Exception:
        ERROR_COUNT += 1
        raise

@app.get("/health", tags=["Observability"])
def health_check():
    return {
        "status": "UP",
        "service": "route-service",
        "total_routes": len(repo.list_routes()),
        "total_stops": len(repo.list_stops())
    }

@app.get("/metrics", tags=["Observability"])
def get_metrics():
    total_routes = len(repo.list_routes())
    total_stops = len(repo.list_stops())
    return (
        f"# HELP route_service_requests_total Total HTTP requests received\n"
        f"# TYPE route_service_requests_total counter\n"
        f"route_service_requests_total {REQUEST_COUNT}\n"
        f"# HELP route_service_errors_total Total HTTP errors\n"
        f"# TYPE route_service_errors_total counter\n"
        f"route_service_errors_total {ERROR_COUNT}\n"
        f"# HELP route_service_routes_count Active transit routes\n"
        f"# TYPE route_service_routes_count gauge\n"
        f"route_service_routes_count {total_routes}\n"
        f"# HELP route_service_stops_count Total transit stops\n"
        f"# TYPE route_service_stops_count gauge\n"
        f"route_service_stops_count {total_stops}\n"
    )

@app.get("/api/v1/routes", tags=["Routes"])
def list_routes(active_only: bool = Query(True, description="Filter for active routes")):
    return repo.list_routes(active_only=active_only)

@app.get("/api/v1/routes/{route_id}", tags=["Routes"])
def get_route(route_id: str):
    route = repo.get_route(route_id)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' not found."
        )
    return route

@app.get("/api/v1/routes/{route_id}/stops", tags=["Routes"])
def get_route_stops(route_id: str):
    stops = repo.get_route_stops(route_id)
    if not stops:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Route '{route_id}' has no configured stops or does not exist."
        )
    return stops

@app.get("/api/v1/stops", tags=["Stops & Geofences"])
def list_stops():
    return repo.list_stops()

@app.get("/api/v1/stops/nearest", response_model=NearestStopResult, tags=["Stops & Geofences"])
def get_nearest_stop(
    lat: float = Query(..., description="Current latitude coordinate (e.g. 28.3638)"),
    lon: float = Query(..., description="Current longitude coordinate (e.g. 75.5872)"),
    max_radius_meters: float = Query(1000.0, description="Maximum search distance in meters")
):
    result = repo.find_nearest_stop(lat, lon, max_radius=max_radius_meters)
    return NearestStopResult(**result)

@app.get("/api/v1/stops/{stop_id}/geofence-check", tags=["Stops & Geofences"])
def check_geofence(
    stop_id: str,
    lat: float = Query(..., description="Latitude to check"),
    lon: float = Query(..., description="Longitude to check")
):
    stops = {s["stop_id"]: s for s in repo.list_stops()}
    if stop_id not in stops:
        raise HTTPException(status_code=404, detail=f"Stop '{stop_id}' not found.")

    stop = stops[stop_id]
    dist = haversine_distance(lat, lon, stop["latitude"], stop["longitude"])
    radius = stop.get("geofence_radius_meters", 60)
    inside = dist <= radius

    return {
        "stop_id": stop_id,
        "stop_name": stop["stop_name"],
        "distance_meters": round(dist, 2),
        "geofence_radius_meters": radius,
        "is_inside_geofence": inside
    }
