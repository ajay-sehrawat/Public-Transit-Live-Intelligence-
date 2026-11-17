# -*- coding: utf-8 -*-
"""Unit & Integration Test Suite for Service 2: GPS Ingestion Service
Supports both direct function testing (vanilla Python) and TestClient when installed.
"""

import unittest
import sys
import os
import importlib.util

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.dirname(__file__))

from services.common.clients.vehicle_client import VehicleRegistryClient
from services.common.kafka.kafka_client import InMemoryKafkaBroker, TransitKafkaProducer
from services.common.zookeeper.zk_client import InMemoryZooKeeper, ZooKeeperClient
from gps_models import GPSTelemetryPayload, BatchTelemetryPayload

def import_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

vr_db = import_from_path("vr_db", os.path.join(REPO_ROOT, "services/01-vehicle-registry/vehicle_db.py"))
vr_grpc = import_from_path("vr_grpc", os.path.join(REPO_ROOT, "services/01-vehicle-registry/grpc_server.py"))

import main as ingest_app

try:
    from fastapi.testclient import TestClient
    from fastapi import HTTPException
    HAS_TESTCLIENT = True
except ImportError:
    HAS_TESTCLIENT = False
    class HTTPException(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code
            self.detail = detail

class TestGPSIngestion(unittest.TestCase):

    def setUp(self):
        self.kafka_broker = InMemoryKafkaBroker()
        self.kafka_broker.reset()

        self.zk_tree = InMemoryZooKeeper()
        self.zk_tree.reset()

        self.vr_servicer = vr_grpc.VehicleRegistryServicer()
        ingest_app.vehicle_client = VehicleRegistryClient(direct_servicer=self.vr_servicer)
        ingest_app.kafka_producer = TransitKafkaProducer()
        ingest_app.zk_client = ZooKeeperClient(session_id="test-ingest")

        if HAS_TESTCLIENT:
            self.client = TestClient(ingest_app.app)
        else:
            self.client = None

    def test_health_check(self):
        """Verifies health check."""
        res = ingest_app.health_check()
        self.assertEqual(res["status"], "UP")
        self.assertEqual(res["service"], "gps-ingestion")
        self.assertTrue(res["kafka_connected"])

    def test_valid_telemetry_ingest(self):
        """Ingests valid GPS telemetry for active bus BUS-101 and verifies Kafka topic output."""
        payload = GPSTelemetryPayload(
            bus_id="BUS-101",
            latitude=28.3638,
            longitude=75.5872,
            speed_kmh=32.5,
            heading=180.0,
            timestamp="2026-11-18T02:15:00Z"
        )
        res = ingest_app.ingest_telemetry(payload)
        self.assertEqual(res.status, "ACCEPTED")
        self.assertEqual(res.bus_id, "BUS-101")
        self.assertEqual(res.assigned_route_id, "ROUTE-1")

        # Verify message in Kafka topic 'bus-gps-raw'
        messages = self.kafka_broker.get_messages("bus-gps-raw")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["key"], "BUS-101")
        self.assertEqual(messages[0]["value"]["latitude"], 28.3638)
        self.assertEqual(messages[0]["value"]["assigned_route_id"], "ROUTE-1")

    def test_rejected_telemetry_maintenance_bus(self):
        """Rejects telemetry for a bus currently in MAINTENANCE status."""
        payload = GPSTelemetryPayload(
            bus_id="BUS-302",
            latitude=28.3638,
            longitude=75.5872,
            speed_kmh=0.0,
            heading=0.0,
            timestamp="2026-11-18T02:15:00Z"
        )
        with self.assertRaises(Exception) as ctx:
            ingest_app.ingest_telemetry(payload)

        # Ensure NO message was published to Kafka
        messages = self.kafka_broker.get_messages("bus-gps-raw")
        self.assertEqual(len(messages), 0)

    def test_batch_ingestion(self):
        """Tests vehicular gateway batch telemetry ingestion."""
        batch_payload = BatchTelemetryPayload(
            pings=[
                GPSTelemetryPayload(
                    bus_id="BUS-101",
                    latitude=28.3638,
                    longitude=75.5872,
                    speed_kmh=30.0,
                    heading=180.0,
                    timestamp="2026-11-18T02:15:00Z"
                ),
                GPSTelemetryPayload(
                    bus_id="BUS-102",
                    latitude=28.3711,
                    longitude=75.5985,
                    speed_kmh=40.0,
                    heading=175.0,
                    timestamp="2026-11-18T02:15:00Z"
                ),
                GPSTelemetryPayload(
                    bus_id="BUS-302", # Maintenance
                    latitude=28.3711,
                    longitude=75.5985,
                    speed_kmh=40.0,
                    heading=175.0,
                    timestamp="2026-11-18T02:15:00Z"
                )
            ]
        )
        res = ingest_app.ingest_telemetry_batch(batch_payload)
        self.assertEqual(res.status, "COMPLETED")
        self.assertEqual(res.total_received, 3)
        self.assertEqual(res.accepted_count, 2)
        self.assertEqual(res.rejected_count, 1)

        # Verify 2 messages in Kafka
        messages = self.kafka_broker.get_messages("bus-gps-raw")
        self.assertEqual(len(messages), 2)

if __name__ == "__main__":
    unittest.main()
