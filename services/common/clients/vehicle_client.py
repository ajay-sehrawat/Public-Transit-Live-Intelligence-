# -*- coding: utf-8 -*-
"""Client SDK for inter-service communication with Service 1: Vehicle Registry
Supports gRPC (primary high-speed channel) with REST fallback.
"""

import os
import sys
import logging
import urllib.request
import json
from typing import Dict, Any, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from services.common.proto.transit_pb2 import VehicleValidationRequest, VehicleValidationResponse
from services.common.proto.transit_pb2_grpc import VehicleRegistryServiceStub, HAS_GRPC

logger = logging.getLogger("VehicleRegistryClient")

class VehicleRegistryClient:
    """Client for querying and validating bus fleet status."""

    def __init__(self,
                 grpc_target: Optional[str] = None,
                 http_target: Optional[str] = None,
                 direct_servicer=None):
        self.grpc_target = grpc_target or os.environ.get("VEHICLE_REGISTRY_GRPC_HOST", "localhost:50051")
        self.http_target = http_target or os.environ.get("VEHICLE_REGISTRY_HTTP_HOST", "http://localhost:8001")
        self.direct_servicer = direct_servicer
        self.stub = None

        if self.direct_servicer:
            self.stub = VehicleRegistryServiceStub(direct_servicer=self.direct_servicer)
        elif HAS_GRPC:
            try:
                import grpc
                channel = grpc.insecure_channel(self.grpc_target)
                self.stub = VehicleRegistryServiceStub(channel=channel)
            except Exception as e:
                logger.warning(f"Could not initialize gRPC channel: {e}")

    def validate_vehicle(self, bus_id: str) -> Dict[str, Any]:
        """Validates vehicle authorization. Uses gRPC when available, falls back to REST."""
        # 1. Attempt gRPC validation
        if self.stub:
            try:
                req = VehicleValidationRequest(bus_id=bus_id)
                res = self.stub.ValidateVehicle(req, timeout=2.0)
                return {
                    "is_valid": res.is_valid,
                    "bus_id": res.bus_id,
                    "status": res.status,
                    "assigned_route_id": res.assigned_route_id,
                    "message": res.message,
                    "channel": "gRPC"
                }
            except Exception as e:
                logger.warning(f"gRPC validation failed, falling back to REST: {e}")

        # 2. REST Fallback
        try:
            url = f"{self.http_target.rstrip('/')}/api/v1/vehicles/{bus_id}/validate"
            req = urllib.request.Request(url, method="POST")
            with urllib.request.urlopen(req, timeout=2.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    data["channel"] = "REST"
                    return data
        except urllib.error.HTTPError as e:
            return {"is_valid": False, "bus_id": bus_id, "status": "ERROR", "message": str(e), "channel": "REST"}
        except Exception as e:
            logger.error(f"Both gRPC and REST calls failed for bus {bus_id}: {e}")
            return {"is_valid": False, "bus_id": bus_id, "status": "UNREACHABLE", "message": str(e), "channel": "NONE"}

