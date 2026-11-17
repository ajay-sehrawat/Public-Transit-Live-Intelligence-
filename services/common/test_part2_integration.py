# -*- coding: utf-8 -*-
"""End-to-End Integration Test for Part 2
Verifies Service 1 (Vehicle Registry), Service 3 (Route Service), and the Inter-Service Clients.
"""

import unittest
import sys
import os
import importlib.util

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

from services.common.clients.vehicle_client import VehicleRegistryClient
from services.common.clients.route_client import RouteServiceClient

# Helper to import modules from hyphenated directories
def import_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

vr_db = import_from_path("vehicle_db", os.path.join(REPO_ROOT, "services/01-vehicle-registry/vehicle_db.py"))
vr_grpc = import_from_path("vr_grpc", os.path.join(REPO_ROOT, "services/01-vehicle-registry/grpc_server.py"))

rt_db = import_from_path("route_db", os.path.join(REPO_ROOT, "services/03-route-service/route_db.py"))
rt_grpc = import_from_path("rt_grpc", os.path.join(REPO_ROOT, "services/03-route-service/grpc_server.py"))

class TestPart2Integration(unittest.TestCase):

    def setUp(self):
        # Create direct servicers to test full client-to-server contracts
        self.vehicle_servicer = vr_grpc.VehicleRegistryServicer()
        self.route_servicer = rt_grpc.RouteGeometryServicer()

        self.vehicle_client = VehicleRegistryClient(direct_servicer=self.vehicle_servicer)
        self.route_client = RouteServiceClient(direct_servicer=self.route_servicer)

    def test_vehicle_validation_flow(self):
        """Verifies inter-service vehicle validation flow."""
        # 1. Valid bus
        res_valid = self.vehicle_client.validate_vehicle("BUS-101")
        self.assertTrue(res_valid["is_valid"])
        self.assertEqual(res_valid["status"], "ACTIVE")
        self.assertEqual(res_valid["assigned_route_id"], "ROUTE-1")

        # 2. Maintenance bus
        res_maint = self.vehicle_client.validate_vehicle("BUS-302")
        self.assertFalse(res_maint["is_valid"])
        self.assertEqual(res_maint["status"], "MAINTENANCE")

        # 3. Unregistered bus
        res_unknown = self.vehicle_client.validate_vehicle("BUS-ROGUE-999")
        self.assertFalse(res_unknown["is_valid"])
        self.assertEqual(res_unknown["status"], "NOT_FOUND")

    def test_route_geometry_flow(self):
        """Verifies inter-service route lookup and geofence detection."""
        route_info = self.route_client.get_route_details("ROUTE-1")
        self.assertIsNotNone(route_info)
        self.assertEqual(route_info["route_short_name"], "1A")
        self.assertEqual(len(route_info["stops"]), 5)

        # Verify nearest stop lookup for bus ping near BITS Main Gate (28.3638, 75.5872)
        nearest = self.route_client.find_nearest_stop(28.3638, 75.5872, max_radius=100.0)
        self.assertTrue(nearest["found"])
        self.assertEqual(nearest["stop_id"], "STOP-004")
        self.assertTrue(nearest["within_geofence"])

    def test_fleet_and_route_correlation(self):
        """Verifies that an authorized vehicle's assigned route exists and has stops."""
        bus = self.vehicle_client.validate_vehicle("BUS-101")
        self.assertTrue(bus["is_valid"])
        assigned_route = bus["assigned_route_id"]

        route_info = self.route_client.get_route_details(assigned_route)
        self.assertIsNotNone(route_info)
        self.assertEqual(route_info["route_id"], assigned_route)
        self.assertGreaterEqual(len(route_info["stops"]), 3)

if __name__ == "__main__":
    unittest.main()
