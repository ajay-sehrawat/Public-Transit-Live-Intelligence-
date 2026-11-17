# -*- coding: utf-8 -*-
"""gRPC Server implementation for Service 1: Vehicle Registry Service"""

import logging
import sys
import os

# Add service directory and parent directory to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.proto.transit_pb2 import (
    VehicleValidationRequest,
    VehicleValidationResponse,
    VehicleDetailsRequest,
    VehicleDetailsResponse,
    ListVehiclesRequest,
    ListVehiclesResponse,
)
from services.common.proto.transit_pb2_grpc import (
    VehicleRegistryServiceServicer,
    add_VehicleRegistryServiceServicer_to_server,
    HAS_GRPC,
)
from vehicle_db import repo

logger = logging.getLogger("VehicleRegistry.gRPC")

class VehicleRegistryServicer(VehicleRegistryServiceServicer):
    """Authoritative gRPC Handler for bus validation and queries."""

    def ValidateVehicle(self, request: VehicleValidationRequest, context=None) -> VehicleValidationResponse:
        """Sub-5ms validation used by GPS Ingestion Service."""
        vehicle = repo.get_vehicle(request.bus_id)
        if not vehicle:
            return VehicleValidationResponse(
                is_valid=False,
                bus_id=request.bus_id,
                status="NOT_FOUND",
                assigned_route_id="",
                message=f"Vehicle {request.bus_id} is not registered in transit fleet"
            )

        is_active = vehicle.get("status") == "ACTIVE"
        return VehicleValidationResponse(
            is_valid=is_active,
            bus_id=vehicle["bus_id"],
            status=vehicle.get("status", "UNKNOWN"),
            assigned_route_id=vehicle.get("assigned_route_id") or "",
            message="Vehicle is authorized and active" if is_active else f"Vehicle status is {vehicle.get('status')}"
        )

    def GetVehicleDetails(self, request: VehicleDetailsRequest, context=None) -> VehicleDetailsResponse:
        vehicle = repo.get_vehicle(request.bus_id)
        if not vehicle:
            return VehicleDetailsResponse(bus_id=request.bus_id, status="NOT_FOUND")

        return VehicleDetailsResponse(
            bus_id=vehicle["bus_id"],
            license_plate=vehicle["license_plate"],
            model=vehicle["model"],
            capacity=int(vehicle["capacity"]),
            propulsion_type=vehicle.get("propulsion_type", "ELECTRIC"),
            status=vehicle.get("status", "ACTIVE"),
            assigned_route_id=vehicle.get("assigned_route_id") or "",
            created_at=str(vehicle.get("created_at", ""))
        )

    def ListActiveVehicles(self, request: ListVehiclesRequest, context=None) -> ListVehiclesResponse:
        status_filter = request.status_filter or "ACTIVE"
        vehicles = repo.list_vehicles(status=status_filter)
        response_list = [
            VehicleDetailsResponse(
                bus_id=v["bus_id"],
                license_plate=v["license_plate"],
                model=v["model"],
                capacity=int(v["capacity"]),
                propulsion_type=v.get("propulsion_type", "ELECTRIC"),
                status=v.get("status", "ACTIVE"),
                assigned_route_id=v.get("assigned_route_id") or "",
                created_at=str(v.get("created_at", ""))
            )
            for v in vehicles
        ]
        return ListVehiclesResponse(vehicles=response_list)

def create_grpc_server(port: int = 50051):
    """Instantiates and starts the gRPC server."""
    if not HAS_GRPC:
        logger.warning("grpcio library is not installed on system; using direct in-memory servicer.")
        return VehicleRegistryServicer()

    import grpc
    from concurrent import futures
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = VehicleRegistryServicer()
    add_VehicleRegistryServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{port}')
    logger.info(f"gRPC Server listening on port {port}")
    return server
