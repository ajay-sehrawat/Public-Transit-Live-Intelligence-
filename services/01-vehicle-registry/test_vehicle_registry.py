# -*- coding: utf-8 -*-
"""Unit & Integration Test Suite for Service 1: Vehicle Registry Service
Tests both REST API and gRPC servicer methods.
"""

import unittest
import sys
import os

# Add paths
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from vehicle_db import VehicleRepository
from grpc_server import VehicleRegistryServicer
from services.common.proto.transit_pb2 import (
    VehicleValidationRequest,
    VehicleDetailsRequest,
    ListVehiclesRequest
)

class TestVehicleRegistry(unittest.TestCase):

    def setUp(self):
        # Use clean in-memory database for isolated testing
        self.repo = VehicleRepository(":memory:")
        self.servicer = VehicleRegistryServicer()
        # Point global repo in grpc_server to test repo
        import grpc_server
        grpc_server.repo = self.repo

    def test_seeded_vehicles_exist(self):
        """Verifies that baseline seed vehicles exist in registry."""
        vehicles = self.repo.list_vehicles()
        self.assertGreaterEqual(len(vehicles), 8)
        bus_101 = self.repo.get_vehicle("BUS-101")
        self.assertIsNotNone(bus_101)
        self.assertEqual(bus_101["license_plate"], "RJ-18-PA-0101")
        self.assertEqual(bus_101["status"], "ACTIVE")

    def test_grpc_validate_active_vehicle(self):
        """gRPC: Validates an active bus (BUS-101)."""
        req = VehicleValidationRequest(bus_id="BUS-101")
        res = self.servicer.ValidateVehicle(req)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.status, "ACTIVE")
        self.assertEqual(res.assigned_route_id, "ROUTE-1")

    def test_grpc_validate_maintenance_vehicle(self):
        """gRPC: Validates a bus currently in MAINTENANCE (BUS-302)."""
        req = VehicleValidationRequest(bus_id="BUS-302")
        res = self.servicer.ValidateVehicle(req)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, "MAINTENANCE")

    def test_grpc_validate_nonexistent_vehicle(self):
        """gRPC: Rejects an unregistered vehicle ID."""
        req = VehicleValidationRequest(bus_id="BUS-UNKNOWN-999")
        res = self.servicer.ValidateVehicle(req)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.status, "NOT_FOUND")

    def test_create_and_delete_vehicle(self):
        """Repository: Tests full vehicle lifecycle creation and deletion."""
        new_bus = {
            "bus_id": "BUS-999",
            "license_plate": "RJ-18-PZ-9999",
            "model": "Volvo Test Electric",
            "capacity": 55,
            "propulsion_type": "ELECTRIC",
            "status": "ACTIVE",
            "assigned_route_id": "ROUTE-1"
        }
        created = self.repo.create_vehicle(new_bus)
        self.assertEqual(created["bus_id"], "BUS-999")

        # Verify gRPC validation now recognizes it
        req = VehicleValidationRequest(bus_id="BUS-999")
        res = self.servicer.ValidateVehicle(req)
        self.assertTrue(res.is_valid)

        # Delete vehicle
        deleted = self.repo.delete_vehicle("BUS-999")
        self.assertTrue(deleted)
        self.assertIsNone(self.repo.get_vehicle("BUS-999"))

    def test_filter_by_status(self):
        """Repository: Tests filtering vehicles by operational status."""
        active_buses = self.repo.list_vehicles(status="ACTIVE")
        maintenance_buses = self.repo.list_vehicles(status="MAINTENANCE")
        self.assertTrue(all(b["status"] == "ACTIVE" for b in active_buses))
        self.assertTrue(all(b["status"] == "MAINTENANCE" for b in maintenance_buses))

if __name__ == "__main__":
    unittest.main()
