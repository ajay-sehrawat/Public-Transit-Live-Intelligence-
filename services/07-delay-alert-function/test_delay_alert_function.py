# -*- coding: utf-8 -*-
"""Unit Test Suite for Service 7: Delay Alert Service (Serverless Function)"""

import unittest
import sys
import os
import json

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.dirname(__file__))

from services.common.firestore.firestore_client import InMemoryFirestore, TransitFirestoreClient
from services.common.kafka.kafka_client import InMemoryKafkaBroker, TransitKafkaProducer
import main as alert_fn

class TestDelayAlertFunction(unittest.TestCase):

    def setUp(self):
        self.firestore_store = InMemoryFirestore()
        self.firestore_store.reset()

        self.kafka_broker = InMemoryKafkaBroker()
        self.kafka_broker.reset()

        alert_fn.firestore_client = TransitFirestoreClient()
        alert_fn.kafka_producer = TransitKafkaProducer()

    def test_on_time_eta_does_not_trigger_alert(self):
        """Verifies that normal delays (< 5 min) do NOT generate an alert."""
        on_time_payload = {
            "bus_id": "BUS-101",
            "route_id": "ROUTE-1",
            "delay_seconds": 60, # 1 minute delay (normal traffic)
            "status": "ON_TIME",
            "next_stop_name": "BITS Main Gate"
        }

        res = alert_fn.delay_alert_pubsub_handler(on_time_payload)
        self.assertIsNone(res["alert"])

        # Verify Firestore collection 'delay_alerts' is empty
        docs = self.firestore_store.collection("delay_alerts").stream()
        self.assertEqual(len(docs), 0)

        # Verify Kafka alerts topic has no messages
        messages = self.kafka_broker.get_messages("bus-delay-alerts")
        self.assertEqual(len(messages), 0)

    def test_delayed_eta_triggers_alert_and_writes_firestore(self):
        """Verifies that delay >= 5 minutes triggers alert and writes to NoSQL Firestore."""
        delayed_payload = {
            "bus_id": "BUS-102",
            "route_id": "ROUTE-1",
            "next_stop_id": "STOP-004",
            "next_stop_name": "BITS Main Gate",
            "delay_seconds": 450, # 7.5 minutes delay
            "status": "DELAYED"
        }

        res = alert_fn.delay_alert_pubsub_handler(delayed_payload)
        alert = res["alert"]
        self.assertIsNotNone(alert)
        self.assertEqual(alert["bus_id"], "BUS-102")
        self.assertEqual(alert["delay_minutes"], 7.5)
        self.assertEqual(alert["severity"], "MINOR")
        self.assertTrue(alert["is_active"])

        # Verify document exists in Firestore (Storage Product 2: NoSQL)
        docs = self.firestore_store.collection("delay_alerts").stream()
        self.assertEqual(len(docs), 1)
        stored_alert = docs[0].to_dict()
        self.assertEqual(stored_alert["bus_id"], "BUS-102")
        self.assertEqual(stored_alert["severity"], "MINOR")

        # Verify message published to Kafka
        messages = self.kafka_broker.get_messages("bus-delay-alerts")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["key"], "ROUTE-1")

    def test_severe_delay_classification(self):
        """Verifies SEVERE classification for delays > 20 minutes."""
        critical_payload = {
            "bus_id": "BUS-103",
            "route_id": "ROUTE-2",
            "next_stop_name": "Nutan Market Terminal",
            "delay_seconds": 1500, # 25 minutes delay
            "status": "DELAYED"
        }
        res = alert_fn.delay_alert_pubsub_handler(critical_payload)
        self.assertEqual(res["alert"]["severity"], "SEVERE")

    def test_gcs_incident_upload_trigger(self):
        """Verifies GCS object finalize trigger for incident reports."""
        gcs_event = {
            "bucket": "transit-telemetry-raw-archive-test",
            "name": "incidents/roadblock-pilani-main.json",
            "route_id": "ROUTE-1"
        }
        res = alert_fn.incident_storage_handler(gcs_event)
        self.assertEqual(res["status"], "INCIDENT_ALERT_CREATED")
        alert = res["alert"]
        self.assertEqual(alert["trigger_type"], "GCS_INCIDENT_UPLOAD")
        self.assertEqual(alert["severity"], "MODERATE")

if __name__ == "__main__":
    unittest.main()

