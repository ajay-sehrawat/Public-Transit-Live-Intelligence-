# -*- coding: utf-8 -*-
"""FastAPI REST API for Service 1: Vehicle Registry Service"""

import os
import sys
from typing import Optional, List

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))

from services.common.compat import FastAPI, HTTPException, Query, status, CORSMiddleware
from vehicle_models import VehicleCreate, VehicleUpdate, VehicleValidationResult
from vehicle_db import repo

app = FastAPI(
    title="Vehicle Registry Service",
    description="Maintains authoritative public transit fleet records, vehicle capacity, and route assignments.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simulated Prometheus Metrics counters
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
    """Kubernetes liveness and readiness probe endpoint."""
    return {
        "status": "UP",
        "service": "vehicle-registry",
        "database": "CONNECTED",
        "total_vehicles": len(repo.list_vehicles())
    }

@app.get("/metrics", tags=["Observability"])
def get_metrics():
    """Prometheus-compatible plain text metrics."""
    total_vehicles = len(repo.list_vehicles())
    active_vehicles = len(repo.list_vehicles(status="ACTIVE"))
    return (
        f"# HELP vehicle_registry_requests_total Total HTTP requests received\n"
        f"# TYPE vehicle_registry_requests_total counter\n"
        f"vehicle_registry_requests_total {REQUEST_COUNT}\n"
        f"# HELP vehicle_registry_errors_total Total HTTP errors\n"
        f"# TYPE vehicle_registry_errors_total counter\n"
        f"vehicle_registry_errors_total {ERROR_COUNT}\n"
        f"# HELP vehicle_registry_fleet_total Total registered buses in fleet\n"
        f"# TYPE vehicle_registry_fleet_total gauge\n"
        f"vehicle_registry_fleet_total {total_vehicles}\n"
        f"# HELP vehicle_registry_active_buses Currently active operational buses\n"
        f"# TYPE vehicle_registry_active_buses gauge\n"
        f"vehicle_registry_active_buses {active_vehicles}\n"
    )

@app.get("/api/v1/vehicles", tags=["Fleet Management"])
def list_vehicles(
    status: Optional[str] = Query(None, description="Filter by status (e.g. ACTIVE, MAINTENANCE)"),
    route_id: Optional[str] = Query(None, description="Filter by assigned route ID")
):
    """Retrieve list of transit buses with optional filtering."""
    return repo.list_vehicles(status=status, route_id=route_id)

@app.get("/api/v1/vehicles/{bus_id}", tags=["Fleet Management"])
def get_vehicle(bus_id: str):
    """Retrieve complete metadata for a specific transit bus."""
    vehicle = repo.get_vehicle(bus_id)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{bus_id}' not found in registry."
        )
    return vehicle

@app.post("/api/v1/vehicles", status_code=status.HTTP_201_CREATED, tags=["Fleet Management"])
def register_vehicle(payload: VehicleCreate):
    """Register a new bus into the transit fleet registry."""
    existing = repo.get_vehicle(payload.bus_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle '{payload.bus_id}' already exists in registry."
        )
    return repo.create_vehicle(payload.dict())

@app.patch("/api/v1/vehicles/{bus_id}", tags=["Fleet Management"])
def update_vehicle(bus_id: str, payload: VehicleUpdate):
    """Update bus parameters, maintenance status, or route assignment."""
    vehicle = repo.get_vehicle(bus_id)
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{bus_id}' not found."
        )
    return repo.update_vehicle(bus_id, payload.dict(exclude_unset=True))

@app.delete("/api/v1/vehicles/{bus_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Fleet Management"])
def deregister_vehicle(bus_id: str):
    """Deregister/retire a vehicle from the transit fleet."""
    success = repo.delete_vehicle(bus_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle '{bus_id}' not found."
        )
    return None

@app.post("/api/v1/vehicles/{bus_id}/validate", response_model=VehicleValidationResult, tags=["Inter-Service RPC"])
def validate_vehicle_http(bus_id: str):
    """HTTP validation endpoint mirroring the gRPC ValidateVehicle RPC."""
    vehicle = repo.get_vehicle(bus_id)
    if not vehicle:
        return VehicleValidationResult(
            is_valid=False,
            bus_id=bus_id,
            status="NOT_FOUND",
            assigned_route_id=None,
            message="Vehicle is not registered in transit registry."
        )
    is_active = vehicle.get("status") == "ACTIVE"
    return VehicleValidationResult(
        is_valid=is_active,
        bus_id=bus_id,
        status=vehicle.get("status", "UNKNOWN"),
        assigned_route_id=vehicle.get("assigned_route_id"),
        message="Vehicle is active and authorized" if is_active else f"Vehicle status is {vehicle.get('status')}"
    )
