# -*- coding: utf-8 -*-
"""Unit & Integration Test Suite for Service 5: Stream Processor (Apache Flink)
Verifies:
  1. Event-time 1-minute tumbling window stateful aggregation
  2. BoundedOutOfOrderness watermarking
  3. Late-event side output handling
  4. Publishing to results Kafka topics ('bus-arrival-estimates' and 'bus-route-stats')
"""

import unittest
import sys
import os
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)
sys.path.append(os.path.dirname(__file__))

from services.common.kafka.kafka_client import InMemoryKafkaBroker, TransitKafkaProducer
from stream_processor_engine import StreamProcessorEngine

class TestFlinkStreamProcessor(unittest.TestCase):

    def setUp(self):
        self.kafka_broker = InMemoryKafkaBroker()
        self.kafka_broker.reset()
        self.producer = TransitKafkaProducer()
        self.engine = StreamProcessorEngine(kafka_producer=self.producer)

    def test_1_minute_tumbling_window_aggregation(self):
        """Verifies stateful 1-minute window aggregation calculates rolling speed and ETA."""
        # Base window epoch: 2026-11-18 02:00:00 UTC = 1794967200000 ms
        base_ts = 1794967200000

        # Simulate 4 pings during the 1-minute window for BUS-101 (speeds: 30, 32, 34, 36 km/h)
        # Average speed should be exactly 33.0 km/h
        pings = [
            {
                "event_id": "evt-01",
                "bus_id": "BUS-101",
                "route_id": "ROUTE-1",
                "speed_kmh": 30.0,
                "distance_to_next_stop_meters": 600.0,
                "next_stop_id": "STOP-004",
                "next_stop_name": "BITS Main Gate",
                "is_inside_geofence": False,
                "event_timestamp": base_ts + 10000 # 10s
            },
            {
                "event_id": "evt-02",
                "bus_id": "BUS-101",
                "route_id": "ROUTE-1",
                "speed_kmh": 32.0,
                "distance_to_next_stop_meters": 500.0,
                "next_stop_id": "STOP-004",
                "next_stop_name": "BITS Main Gate",
                "is_inside_geofence": False,
                "event_timestamp": base_ts + 20000 # 20s
            },
            {
                "event_id": "evt-03",
                "bus_id": "BUS-101",
                "route_id": "ROUTE-1",
                "speed_kmh": 34.0,
                "distance_to_next_stop_meters": 400.0,
                "next_stop_id": "STOP-004",
                "next_stop_name": "BITS Main Gate",
                "is_inside_geofence": False,
                "event_timestamp": base_ts + 30000 # 30s
            },
            {
                "event_id": "evt-04",
                "bus_id": "BUS-101",
                "route_id": "ROUTE-1",
                "speed_kmh": 36.0,
                "distance_to_next_stop_meters": 300.0,
                "next_stop_id": "STOP-004",
                "next_stop_name": "BITS Main Gate",
                "is_inside_geofence": False,
                "event_timestamp": base_ts + 45000 # 45s
            }
        ]

        # Feed events into Flink 1-minute window
        for p in pings:
            self.engine.process_event(p)

        # Trigger window evaluation (advances watermark or flushes completed window)
        results = self.engine.flush_all_windows()
        self.assertEqual(len(results), 1)
        last_result = results[0]
        self.assertIsNotNone(last_result)
        self.assertEqual(last_result["bus_id"], "BUS-101")
        self.assertEqual(last_result["route_id"], "ROUTE-1")
        self.assertEqual(last_result["sample_count"], 4)
        self.assertEqual(last_result["rolling_avg_speed_kmh"], 33.0)
        self.assertEqual(last_result["next_stop_id"], "STOP-004")
        self.assertEqual(last_result["distance_to_stop_meters"], 300.0)

        # Speed: 33 km/h = 9.166 m/s. ETA = 300m / 9.166 m/s + 30s dwell = ~62 seconds
        self.assertGreaterEqual(last_result["eta_seconds"], 55)
        self.assertLessEqual(last_result["eta_seconds"], 70)

        # Verify output messages in Kafka results topics
        estimates_messages = self.kafka_broker.get_messages("bus-arrival-estimates")
        self.assertGreaterEqual(len(estimates_messages), 1)
        self.assertEqual(estimates_messages[-1]["key"], "BUS-101")
        self.assertEqual(estimates_messages[-1]["value"]["next_stop_name"], "BITS Main Gate")

        stats_messages = self.kafka_broker.get_messages("bus-route-stats")
        self.assertGreaterEqual(len(stats_messages), 1)
        self.assertEqual(stats_messages[-1]["key"], "ROUTE-1")

    def test_watermark_advancement_and_late_event_side_output(self):
        """Verifies that late-arriving events are diverted to side output."""
        base_ts = 1794967200000

        # Event 1 advances event-time to base_ts + 60,000ms
        ping_advanced = {
            "event_id": "evt-advanced",
            "bus_id": "BUS-101",
            "route_id": "ROUTE-1",
            "speed_kmh": 30.0,
            "distance_to_next_stop_meters": 200.0,
            "next_stop_id": "STOP-004",
            "next_stop_name": "BITS Main Gate",
            "is_inside_geofence": False,
            "event_timestamp": base_ts + 60000
        }
        self.engine.process_event(ping_advanced)

        # Watermark is now: (base_ts + 60000) - 20000 = base_ts + 40000 ms
        self.assertEqual(self.engine.current_watermark, base_ts + 40000)

        # Event 2 arrives late (timestamp: base_ts + 10000 ms, which is < watermark)
        ping_late = {
            "event_id": "evt-late-01",
            "bus_id": "BUS-101",
            "route_id": "ROUTE-1",
            "speed_kmh": 25.0,
            "distance_to_next_stop_meters": 700.0,
            "next_stop_id": "STOP-004",
            "next_stop_name": "BITS Main Gate",
            "is_inside_geofence": False,
            "event_timestamp": base_ts + 10000  # 30 seconds behind watermark!
        }
        res_late = self.engine.process_event(ping_late)

        # Late event should NOT be processed in standard window
        self.assertIsNone(res_late)

        # Must land in late events side output
        self.assertEqual(len(self.engine.late_events_side_output), 1)
        late_entry = self.engine.late_events_side_output[0]
        self.assertEqual(late_entry["event"]["event_id"], "evt-late-01")
        self.assertEqual(late_entry["reason"], "BOUNDED_OUT_OF_ORDERNESS_EXCEEDED")

    def test_delay_detection_alert_trigger(self):
        """Verifies that large delays trigger status = 'DELAYED' for Service 7 alerts."""
        base_ts = 1794967200000
        # Very high distance (5,000 meters) with low speed (10 km/h) -> ETA will exceed 5 minutes delay
        ping_delayed = {
            "event_id": "evt-delayed",
            "bus_id": "BUS-102",
            "route_id": "ROUTE-1",
            "speed_kmh": 10.0,
            "distance_to_next_stop_meters": 4500.0,
            "next_stop_id": "STOP-005",
            "next_stop_name": "BITS Clock Tower",
            "is_inside_geofence": False,
            "event_timestamp": base_ts + 15000
        }
        self.engine.process_event(ping_delayed)
        results = self.engine.flush_all_windows()
        self.assertEqual(len(results), 1)
        res = results[0]
        self.assertIsNotNone(res)
        self.assertGreater(res["delay_seconds"], 300)
        self.assertEqual(res["status"], "DELAYED")

    def test_automatic_watermark_window_triggering(self):
        """Tests that a window triggers automatically when subsequent events advance watermark past window_end."""
        base_ts = 1794967200000

        # Event inside Window 1
        ping_w1 = {
            "event_id": "evt-w1",
            "bus_id": "BUS-101",
            "route_id": "ROUTE-1",
            "speed_kmh": 35.0,
            "distance_to_next_stop_meters": 400.0,
            "next_stop_id": "STOP-004",
            "next_stop_name": "BITS Main Gate",
            "is_inside_geofence": False,
            "event_timestamp": base_ts + 30000
        }
        res1 = self.engine.process_event(ping_w1)
        self.assertIsNone(res1)

        # Event in Window 2 with timestamp base_ts + 85,000 ms
        # Watermark advances to: (base_ts + 85000) - 20000 = base_ts + 65000 ms (> base_ts + 60000 ms)!
        ping_w2 = {
            "event_id": "evt-w2",
            "bus_id": "BUS-101",
            "route_id": "ROUTE-1",
            "speed_kmh": 36.0,
            "distance_to_next_stop_meters": 200.0,
            "next_stop_id": "STOP-004",
            "next_stop_name": "BITS Main Gate",
            "is_inside_geofence": False,
            "event_timestamp": base_ts + 85000
        }
        triggered_w1 = self.engine.process_event(ping_w2)

        # Window 1 MUST have triggered automatically!
        self.assertIsNotNone(triggered_w1)
        self.assertEqual(triggered_w1["bus_id"], "BUS-101")
        self.assertEqual(triggered_w1["sample_count"], 1)

if __name__ == "__main__":
    unittest.main()
