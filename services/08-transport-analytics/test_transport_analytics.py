# -*- coding: utf-8 -*-
"""Unit & Integration Tests for Service 8: Transport Analytics API & Public Web Service"""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Import Service 8 main via importlib for directory name safety
import importlib.util
service_path = os.path.join(os.path.dirname(__file__), "main.py")
spec = importlib.util.spec_from_file_location("transport_analytics_service", service_path)
analytics_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analytics_mod)

app = analytics_mod.app


class TestTransportAnalyticsService(unittest.TestCase):
    """Verifies Public Web Service endpoints, live feed, metrics, and dashboard."""

    def test_01_health_check(self):
        res = analytics_mod.health_check()
        self.assertEqual(res["status"], "UP")
        self.assertEqual(res["service"], "transport-analytics-api")

    def test_02_metrics_exposition(self):
        response = analytics_mod.get_metrics()
        body = response.body.decode("utf-8") if hasattr(response, "body") else str(response)
        self.assertIn("transport_analytics_http_requests_total", body)
        self.assertIn("transport_analytics_active_buses", body)

    def test_03_dashboard_html_serving(self):
        response = analytics_mod.get_dashboard_root()
        content = response.body.decode("utf-8") if hasattr(response, "body") else str(response)
        self.assertIn("leaflet", content.lower())
        self.assertIn("Public Transit Live Intelligence", content)
        self.assertIn("/api/v1/analytics/live-feed", content)

    def test_04_live_feed_telemetry(self):
        feed = analytics_mod.get_live_feed()
        self.assertIn("kpis", feed)
        self.assertIn("buses", feed)
        self.assertIn("stops", feed)
        self.assertIn("alerts", feed)
        self.assertIn("arrivals", feed)

        self.assertGreaterEqual(feed["kpis"]["active_buses"], 1)
        self.assertGreaterEqual(len(feed["stops"]), 3)
        self.assertGreaterEqual(len(feed["buses"]), 1)

    def test_05_stop_arrivals_board(self):
        arrivals = analytics_mod.get_stop_arrivals("STOP-002")
        self.assertEqual(arrivals["stop_id"], "STOP-002")
        self.assertIn("arrivals", arrivals)
        self.assertIsInstance(arrivals["arrivals"], list)

    def test_06_delays_endpoint(self):
        delays = analytics_mod.get_delays()
        self.assertIn("alerts", delays)
        self.assertIsInstance(delays["alerts"], list)
        self.assertGreaterEqual(delays["total_delays"], 0)

    def test_07_fleet_stats(self):
        stats = analytics_mod.get_fleet_stats()
        self.assertIn("total_buses", stats)
        self.assertIn("active_buses", stats)
        self.assertIn("system_health", stats)
        self.assertIn(stats["system_health"], ["OPTIMAL", "WARNING", "DEGRADED"])

    def test_08_stops_configuration(self):
        stops_res = analytics_mod.get_stops()
        self.assertIn("stops", stops_res)
        self.assertEqual(stops_res["total_stops"], len(analytics_mod.DEFAULT_STOPS))

    def test_09_dispatch_new_bus(self):
        res = analytics_mod.dispatch_new_bus({"bus_id": "BUS-999", "route_id": "ROUTE-1", "model": "Volvo EV", "capacity": 60})
        self.assertEqual(res["status"], "DEPLOYED")
        self.assertEqual(res["bus_id"], "BUS-999")
        self.assertIn("BUS-999", analytics_mod.LIVE_FLEET_STATE)

    def test_10_trigger_delay_incident(self):
        res = analytics_mod.trigger_transit_delay({"bus_id": "BUS-999", "delay_minutes": 12.0})
        self.assertEqual(res["status"], "ALERT_DISPATCHED")
        self.assertEqual(res["severity"], "CRITICAL")
        self.assertEqual(res["delay_minutes"], 12.0)

        # Verify live fleet state reflects delay and status
        self.assertEqual(analytics_mod.LIVE_FLEET_STATE["BUS-999"]["status"], "DELAYED")
        self.assertEqual(analytics_mod.LIVE_FLEET_STATE["BUS-999"]["delay"], 12.0)

        # Verify live feed returns delayed ETA (base travel time + 12.0 * 60 seconds)
        feed = analytics_mod.get_live_feed()
        bus_999 = next((b for b in feed["buses"] if b["bus_id"] == "BUS-999"), None)
        self.assertIsNotNone(bus_999)
        self.assertEqual(bus_999["delay_minutes"], 12.0)
        self.assertGreaterEqual(bus_999["eta_seconds"], 12 * 60)

    def test_11_simulate_crowd_surge(self):
        res = analytics_mod.simulate_station_crowd({"stop_id": "STOP-002", "passenger_count": 140})
        self.assertEqual(res["status"], "CROWD_UPDATED")
        self.assertEqual(res["crowd_level"], "SURGE")


if __name__ == "__main__":
    unittest.main()
