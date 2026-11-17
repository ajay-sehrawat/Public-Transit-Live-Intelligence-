# -*- coding: utf-8 -*-
"""Unit & Integration Test Suite for Service 6: Passenger Demand Service"""

import unittest
import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.dirname(__file__))

from services.common.firestore.firestore_client import InMemoryFirestore, TransitFirestoreClient
from demand_engine import PassengerDemandEngine
from demand_models import PassengerTapEvent
import main as demand_app

class TestPassengerDemand(unittest.TestCase):

    def setUp(self):
        self.firestore_store = InMemoryFirestore()
        self.firestore_store.reset()

        self.db = TransitFirestoreClient()
        self.engine = PassengerDemandEngine(firestore_client=self.db)
        demand_app.engine = self.engine

    def test_record_tap_updates_firestore(self):
        """Verifies smartcard tap updates stop crowd metrics in NoSQL Firestore."""
        # Optical sensor detects 35 waiting passengers at BITS Main Gate (STOP-004)
        tap_event = PassengerTapEvent(
            stop_id="STOP-004",
            bus_id="BUS-101",
            route_id="ROUTE-1",
            event_type="SENSOR_COUNT",
            passenger_count=35
        )

        res = self.engine.record_tap(tap_event)
        self.assertEqual(res.stop_id, "STOP-004")
        self.assertEqual(res.waiting_passenger_count, 35)
        self.assertEqual(res.crowd_level, "MODERATE")

        # Verify persisted in Firestore (Storage Product 2: NoSQL)
        doc = self.firestore_store.collection("passenger_demand").document("STOP-004").get()
        self.assertTrue(doc.exists)
        data = doc.to_dict()
        self.assertEqual(data["waiting_passenger_count"], 35)
        self.assertEqual(data["crowd_level"], "MODERATE")

    def test_crowd_level_classification(self):
        """Verifies crowd level categorization thresholds."""
        self.assertEqual(self.engine.classify_crowd_level(10), "LOW")
        self.assertEqual(self.engine.classify_crowd_level(25), "MODERATE")
        self.assertEqual(self.engine.classify_crowd_level(65), "HIGH")
        self.assertEqual(self.engine.classify_crowd_level(120), "SURGE")

    def test_archival_to_gcs_object_store(self):
        """Verifies tap buffer flush to Storage Product 3 (GCS Object Store)."""
        # Record 2 taps
        self.engine.record_tap(PassengerTapEvent(stop_id="STOP-001", passenger_count=5))
        self.engine.record_tap(PassengerTapEvent(stop_id="STOP-002", passenger_count=10))

        self.assertEqual(len(self.engine.tap_log_buffer), 2)

        # Flush to GCS
        archive_res = self.engine.archive_taps_to_gcs(bucket_name="transit-telemetry-raw-archive")
        self.assertEqual(archive_res["status"], "ARCHIVED")
        self.assertEqual(archive_res["archived_records"], 2)
        self.assertTrue(archive_res["destination_uri"].startswith("gs://transit-telemetry-raw-archive/"))

        # Buffer must be cleared after archive
        self.assertEqual(len(self.engine.tap_log_buffer), 0)

    def test_health_check(self):
        """Verifies health check."""
        res = demand_app.health_check()
        self.assertEqual(res["status"], "UP")
        self.assertEqual(res["service"], "passenger-demand")

if __name__ == "__main__":
    unittest.main()

