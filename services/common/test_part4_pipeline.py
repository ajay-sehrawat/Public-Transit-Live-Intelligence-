# -*- coding: utf-8 -*-
"""End-to-End Pipeline Integration Test for Part 4
Verifies the complete ingestion & event adaptation pipeline:
  [Bus GPS Device] -> Service 2 (GPS Ingest)
                   -> gRPC Check (Service 1)
                   -> ZooKeeper Heartbeat
                   -> Kafka ('bus-gps-raw')
                   -> Service 4 (Event Adapter)
                   -> Route Geometry Lookup (Service 3)
                   -> Kafka ('bus-gps-normalized')
"""

import unittest
import sys
import os
import importlib.util

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

def import_from_path(module_name, file_path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module

vr_db = import_from_path("vr_db", os.path.join(REPO_ROOT, "services/01-vehicle-registry/vehicle_db.py"))
vr_grpc = import_from_path("vr_grpc", os.path.join(REPO_ROOT, "services/01-vehicle-registry/grpc_server.py"))

rt_db = import_from_path("rt_db", os.path.join(REPO_ROOT, "services/03-route-service/route_db.py"))
rt_grpc = import_from_path("rt_grpc", os.path.join(REPO_ROOT, "services/03-route-service/grpc_server.py"))

from services.common.clients.vehicle_client import VehicleRegistryClient
from services.common.clients.route_client import RouteServiceClient
from services.common.kafka.kafka_client import InMemoryKafkaBroker, TransitKafkaProducer, TransitKafkaConsumer
from services.common.zookeeper.zk_client import InMemoryZooKeeper, ZooKeeperClient

ingest_main = import_from_path("ingest_main", os.path.join(REPO_ROOT, "services/02-gps-ingestion/main.py"))
adapter_main = import_from_path("adapter_main", os.path.join(REPO_ROOT, "services/04-event-adapter/main.py"))
adapter_engine_mod = import_from_path("adapter_engine_mod", os.path.join(REPO_ROOT, "services/04-event-adapter/adapter_engine.py"))

# Ready for tests

class TestPart4Pipeline(unittest.TestCase):

    def setUp(self):
        # 1. Reset shared in-memory infrastructure
        self.kafka_broker = InMemoryKafkaBroker()
        self.kafka_broker.reset()

        self.zk_tree = InMemoryZooKeeper()
        self.zk_tree.reset()

        # 2. Wire Service 1 (Vehicle Registry)
        self.vr_servicer = vr_grpc.VehicleRegistryServicer()
        self.vehicle_client = VehicleRegistryClient(direct_servicer=self.vr_servicer)

        # 3. Wire Service 3 (Route Service)
        self.rt_servicer = rt_grpc.RouteGeometryServicer()
        self.route_client = RouteServiceClient(direct_servicer=self.rt_servicer)

        # 4. Wire Service 2 (GPS Ingestion)
        ingest_main.vehicle_client = self.vehicle_client
        ingest_main.kafka_producer = TransitKafkaProducer()
        ingest_main.zk_client = ZooKeeperClient(session_id="session-ingest-test")

        # 5. Wire Service 4 (Event Adapter)
        self.adapter_engine = adapter_engine_mod.EventAdapterEngine(route_client=self.route_client)
        adapter_main.engine = self.adapter_engine
        adapter_main.kafka_producer = TransitKafkaProducer()
        adapter_main.kafka_consumer = TransitKafkaConsumer(topic="bus-gps-raw")

    def test_full_streaming_pipeline_active_bus(self):
        """Simulates live bus ping through the entire ingestion and adaptation chain."""
        # Step 1: Bus BUS-101 sends GPS coordinates approaching BITS Main Gate (28.3638, 75.5872)
        raw_ping = ingest_main.GPSTelemetryPayload(
            bus_id="BUS-101",
            latitude=28.3638,
            longitude=75.5872,
            speed_kmh=32.0,
            heading=180.0,
            timestamp="2026-11-18T02:15:00Z"
        )

        # Ingestion entrypoint accepts and validates via gRPC
        ingest_res = ingest_main.ingest_telemetry(raw_ping)
        self.assertEqual(ingest_res.status, "ACCEPTED")
        self.assertEqual(ingest_res.bus_id, "BUS-101")
        self.assertEqual(ingest_res.assigned_route_id, "ROUTE-1")

        # Step 2: Verify raw message in Kafka 'bus-gps-raw'
        raw_messages = self.kafka_broker.get_messages("bus-gps-raw")
        self.assertEqual(len(raw_messages), 1)
        raw_record = raw_messages[0]
        self.assertEqual(raw_record["key"], "BUS-101")

        # Step 3: Event Adapter consumes from 'bus-gps-raw'
        adapter_main.process_raw_message(raw_record)

        # Step 4: Verify normalized message in Kafka 'bus-gps-normalized'
        norm_messages = self.kafka_broker.get_messages("bus-gps-normalized")
        self.assertEqual(len(norm_messages), 1)

        normalized = norm_messages[0]["value"]
        self.assertEqual(normalized["bus_id"], "BUS-101")
        self.assertEqual(normalized["route_id"], "ROUTE-1")
        self.assertEqual(normalized["next_stop_id"], "STOP-004")
        self.assertEqual(normalized["next_stop_name"], "BITS Main Gate")
        self.assertTrue(normalized["is_inside_geofence"])
        self.assertGreater(normalized["event_timestamp"], 1700000000000)
        self.assertTrue(len(normalized["event_id"]) > 20)

    def test_pipeline_rejects_unregistered_bus(self):
        """Simulates rogue bus ping that must be rejected at the edge without reaching Kafka."""
        rogue_ping = ingest_main.GPSTelemetryPayload(
            bus_id="BUS-ROGUE-X",
            latitude=28.3638,
            longitude=75.5872,
            speed_kmh=20.0,
            heading=90.0,
            timestamp="2026-11-18T02:15:00Z"
        )

        with self.assertRaises(Exception):
            ingest_main.ingest_telemetry(rogue_ping)

        # Verify nothing entered Kafka topics
        self.assertEqual(len(self.kafka_broker.get_messages("bus-gps-raw")), 0)
        self.assertEqual(len(self.kafka_broker.get_messages("bus-gps-normalized")), 0)

if __name__ == "__main__":
    unittest.main()
