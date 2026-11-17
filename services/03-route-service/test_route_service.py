# -*- coding: utf-8 -*-
"""Unit & Integration Test Suite for Service 3: Route Service"""

import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from geometry import haversine_distance, is_within_geofence
from route_db import RouteRepository
from grpc_server import RouteGeometryServicer
from services.common.proto.transit_pb2 import (
    RouteDetailsRequest,
    NearestStopRequest,
    ListRoutesRequest
)

class TestRouteService(unittest.TestCase):

    def setUp(self):
        self.repo = RouteRepository(":memory:")
        self.servicer = RouteGeometryServicer()
        import grpc_server
        grpc_server.repo = self.repo

    def test_haversine_distance(self):
        """Verifies Haversine formula against known BITS Pilani points."""
        # Distance between BITS Main Gate (28.3638, 75.5872) and BITS Clock Tower (28.3591, 75.5879)
        dist = haversine_distance(28.3638, 75.5872, 28.3591, 75.5879)
        # Expected distance is ~525 meters
        self.assertGreater(dist, 500)
        self.assertLess(dist, 550)

    def test_geofence_arrival_detection(self):
        """Verifies geofence detection logic."""
        gate_lat, gate_lon = 28.3638, 75.5872

        # Point 20 meters away (should be inside 60m geofence)
        inside_point = (28.3639, 75.5872)
        self.assertTrue(is_within_geofence(inside_point[0], inside_point[1], gate_lat, gate_lon, radius_meters=60))

        # Point 500 meters away (should be outside)
        outside_point = (28.3591, 75.5879)
        self.assertFalse(is_within_geofence(outside_point[0], outside_point[1], gate_lat, gate_lon, radius_meters=60))

    def test_get_route_details_with_stops(self):
        """Verifies route stop sequence ordering."""
        route = self.repo.get_route("ROUTE-1")
        self.assertIsNotNone(route)
        self.assertEqual(route["route_short_name"], "1A")
        self.assertEqual(len(route["stops"]), 5)

        # Ensure stop sequence is strictly monotonically increasing
        sequences = [s["stop_sequence"] for s in route["stops"]]
        self.assertEqual(sequences, [1, 2, 3, 4, 5])
        self.assertEqual(route["stops"][0]["stop_id"], "STOP-001")
        self.assertEqual(route["stops"][4]["stop_id"], "STOP-005")

    def test_find_nearest_stop(self):
        """Verifies nearest stop lookup given GPS coordinate."""
        # Bus pinging near BITS Main Gate (28.3637, 75.5871)
        res = self.repo.find_nearest_stop(28.3637, 75.5871, max_radius=300.0)
        self.assertTrue(res["found"])
        self.assertEqual(res["stop_id"], "STOP-004")
        self.assertTrue(res["within_geofence"])

    def test_grpc_route_details(self):
        """gRPC: Verifies GetRouteDetails RPC."""
        req = RouteDetailsRequest(route_id="ROUTE-1")
        res = self.servicer.GetRouteDetails(req)
        self.assertEqual(res.route_id, "ROUTE-1")
        self.assertEqual(len(res.stops), 5)
        self.assertEqual(res.stops[0].stop_name, "Pilani Railway Station")

    def test_grpc_find_nearest_stop(self):
        """gRPC: Verifies FindNearestStop RPC."""
        req = NearestStopRequest(latitude=28.3751, longitude=75.6020, max_radius_meters=200.0)
        res = self.servicer.FindNearestStop(req)
        self.assertTrue(res.found)
        self.assertEqual(res.stop_id, "STOP-001")

if __name__ == "__main__":
    unittest.main()
