# -*- coding: utf-8 -*-
"""Unit & Integration Test Suite for Service 4: Event Adapter"""

import unittest
import sys
import os
import importlib.util

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.dirname(__file__))

from services.common.kafka.kafka_client import InMemoryKafkaBroker, TransitKafkaProducer, TransitKafkaConsumer
from services.common.clients.route_client import RouteServiceClient

def import_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

rt_db = import_from_path("rt_db", os.path.join(REPO_ROOT, "services/03-route-service/route_db.py"))
rt_grpc = import_from_path("rt_grpc", os.path.join(REPO_ROOT, "services/03-route-service/grpc_server.py"))

from adapter_engine import EventAdapterEngine
import main as adapter_app

class TestEventAdapter(unittest.TestCase):

    def setUp(self):
        self.kafka_broker = InMemoryKafkaBroker()
        self.kafka_broker.reset()

        # Connect Route Service servicer to adapter engine
        self.route_servicer = rt_grpc.RouteGeometryServicer()
        self.route_client = RouteServiceClient(direct_servicer=self.route_servicer)
        self.engine = EventAdapterEngine(route_client=self.route_client)

        adapter_app.engine = self.engine
        adapter_app.kafka_producer = TransitKafkaProducer()
        adapter_app.kafka_consumer = TransitKafkaConsumer(topic="bus-gps-raw")

    def test_normalize_event_milestone_enrichment(self):
        """Verifies normalization attaches UUID, epoch ms, and matches nearest stop."""
        raw_event = {
            "correlation_id": "corr-12345",
            "bus_id": "BUS-101",
            "assigned_route_id": "ROUTE-1",
            "latitude": 28.3638,  # BITS Main Gate coordinates
            "longitude": 75.5872,
            "speed_kmh": 28.5,
            "heading": 185.0,
            "event_timestamp": "2026-11-18T02:15:00Z",
            "ingest_timestamp": 1794968100000
        }

        normalized = self.engine.normalize_event(raw_event)

        # 1. UUID event_id attached
        self.assertTrue(len(normalized.event_id) > 20)
        self.assertEqual(normalized.bus_id, "BUS-101")
        self.assertEqual(normalized.route_id, "ROUTE-1")

        # 2. Next stop milestone matched to STOP-004 (BITS Main Gate)
        self.assertEqual(normalized.next_stop_id, "STOP-004")
        self.assertEqual(normalized.next_stop_name, "BITS Main Gate")
        self.assertLess(normalized.distance_to_next_stop_meters, 50.0)
        self.assertTrue(normalized.is_inside_geofence)

        # 3. Epoch timestamp converted properly
        self.assertGreater(normalized.event_timestamp, 1700000000000)

    def test_process_raw_kafka_message(self):
        """Tests Kafka message consumption from 'bus-gps-raw' and emission to 'bus-gps-normalized'."""
        raw_record = {
            "topic": "bus-gps-raw",
            "key": "BUS-101",
            "value": {
                "correlation_id": "corr-test-01",
                "bus_id": "BUS-101",
                "assigned_route_id": "ROUTE-1",
                "latitude": 28.3752, # Pilani Railway Station
                "longitude": 75.6021,
                "speed_kmh": 35.0,
                "heading": 180.0,
                "event_timestamp": "2026-11-18T02:15:00Z"
            }
        }

        # Process message
        adapter_app.process_raw_message(raw_record)

        # Verify message landed in 'bus-gps-normalized'
        normalized_messages = self.kafka_broker.get_messages("bus-gps-normalized")
        self.assertEqual(len(normalized_messages), 1)
        emitted = normalized_messages[0]["value"]
        self.assertEqual(emitted["bus_id"], "BUS-101")
        self.assertEqual(emitted["next_stop_id"], "STOP-001")
        self.assertEqual(emitted["next_stop_name"], "Pilani Railway Station")
        self.assertTrue(emitted["is_inside_geofence"])

    def test_health_check(self):
        """Verifies health endpoint."""
        res = adapter_app.health_check()
        self.assertEqual(res["status"], "UP")
        self.assertEqual(res["service"], "event-adapter")

if __name__ == "__main__":
    unittest.main()

