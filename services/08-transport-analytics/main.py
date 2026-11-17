# -*- coding: utf-8 -*-
"""Service 8: Transport Analytics API & Public Web Service
Provides real-time analytics, public bus arrival board, fleet tracking, and
an interactive live Leaflet map dashboard (Requirement: Public Web Service).
"""

import os
import sys
import time
import logging
from typing import Dict, Any, List, Optional

# Ensure project root in sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from services.common.compat import FastAPI, HTTPException, Request, Response, JSONResponse
from services.common.firestore.firestore_client import TransitFirestoreClient
from services.common.clients.route_client import RouteServiceClient
from services.common.metrics import generate_prometheus_metrics

# Use importlib to import analytics_models safely from current directory
import importlib.util
models_path = os.path.join(os.path.dirname(__file__), "analytics_models.py")
spec = importlib.util.spec_from_file_location("analytics_models", models_path)
analytics_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analytics_models)

TransitKPIs = analytics_models.TransitKPIs
BusLiveFeedItem = analytics_models.BusLiveFeedItem
StopLiveFeedItem = analytics_models.StopLiveFeedItem
DelayAlertFeedItem = analytics_models.DelayAlertFeedItem
ArrivalFeedItem = analytics_models.ArrivalFeedItem
LiveFeedResponse = analytics_models.LiveFeedResponse
StopArrivalsResponse = analytics_models.StopArrivalsResponse
FleetStatsResponse = analytics_models.FleetStatsResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("TransportAnalyticsService")

app = FastAPI(
    title="Public Transport Analytics & Live Feed API",
    version="1.0.0",
    description="Real-time transit telemetry, arrival estimates, delay alerts, and live dashboard."
)

# Clients
firestore_client = TransitFirestoreClient()
route_client = RouteServiceClient()

# Static HTML file path
STATIC_INDEX_PATH = os.path.join(os.path.dirname(__file__), "static", "index.html")

# In-memory metrics counters for Prometheus
REQUEST_COUNTS: Dict[str, int] = {}
REQUEST_LATENCIES: Dict[str, float] = {}

# Default stops around BITS Pilani campus area for fallback/enrichment
DEFAULT_STOPS = [
    {
        "stop_id": "STOP-001",
        "stop_name": "Pilani Bus Stand",
        "latitude": 28.3638,
        "longitude": 75.5872,
        "geofence_radius_meters": 80,
        "capacity": 100
    },
    {
        "stop_id": "STOP-002",
        "stop_name": "BITS Clock Tower",
        "latitude": 28.3645,
        "longitude": 75.5885,
        "geofence_radius_meters": 60,
        "capacity": 150
    },
    {
        "stop_id": "STOP-003",
        "stop_name": "Library Circle",
        "latitude": 28.3658,
        "longitude": 75.5901,
        "geofence_radius_meters": 50,
        "capacity": 80
    },
    {
        "stop_id": "STOP-004",
        "stop_name": "Hostel Gate 2",
        "latitude": 28.3672,
        "longitude": 75.5925,
        "geofence_radius_meters": 70,
        "capacity": 60
    },
    {
        "stop_id": "STOP-005",
        "stop_name": "CEERI Main Gate",
        "latitude": 28.3695,
        "longitude": 75.5950,
        "geofence_radius_meters": 90,
        "capacity": 120
    }
]


def _record_metric(endpoint: str, latency_ms: float):
    REQUEST_COUNTS[endpoint] = REQUEST_COUNTS.get(endpoint, 0) + 1
    REQUEST_LATENCIES[endpoint] = REQUEST_LATENCIES.get(endpoint, 0.0) + latency_ms


def _seed_sample_transit_state():
    """Seeds realistic transit telemetry into Firestore if empty."""
    est_col = firestore_client.collection("realtime_bus_estimates")
    existing = est_col.stream()
    if not existing:
        logger.info("Initializing Firestore with realistic demonstration transit state...")
        # Seed 3 active buses
        buses = [
            {
                "bus_id": "BUS-101",
                "route_id": "ROUTE-PILANI-01",
                "current_lat": 28.3640,
                "current_lon": 28.3640,
                "latitude": 28.3640,
                "longitude": 75.5875,
                "speed_kmh": 34.2,
                "next_stop_id": "STOP-002",
                "next_stop_name": "BITS Clock Tower",
                "eta_seconds": 160,
                "delay_minutes": 0.0,
                "status": "ON_TIME",
                "updated_at": time.time()
            },
            {
                "bus_id": "BUS-102",
                "route_id": "ROUTE-PILANI-01",
                "current_lat": 28.3662,
                "current_lon": 75.5910,
                "latitude": 28.3662,
                "longitude": 75.5910,
                "speed_kmh": 12.0,
                "next_stop_id": "STOP-004",
                "next_stop_name": "Hostel Gate 2",
                "eta_seconds": 450,
                "delay_minutes": 6.5,
                "status": "DELAYED",
                "updated_at": time.time()
            },
            {
                "bus_id": "BUS-103",
                "route_id": "ROUTE-PILANI-02",
                "current_lat": 28.3685,
                "current_lon": 75.5940,
                "latitude": 28.3685,
                "longitude": 75.5940,
                "speed_kmh": 28.5,
                "next_stop_id": "STOP-005",
                "next_stop_name": "CEERI Main Gate",
                "eta_seconds": 220,
                "delay_minutes": 0.0,
                "status": "ON_TIME",
                "updated_at": time.time()
            }
        ]
        for b in buses:
            est_col.document(b["bus_id"]).set(b)

        # Seed delay alert
        alert_col = firestore_client.collection("delay_alerts")
        alert_col.document("ALERT-BUS-102").set({
            "alert_id": "ALERT-BUS-102",
            "bus_id": "BUS-102",
            "route_id": "ROUTE-PILANI-01",
            "stop_id": "STOP-004",
            "stop_name": "Hostel Gate 2",
            "delay_minutes": 6.5,
            "severity": "HIGH",
            "message": "Traffic bottleneck near Library Circle causing 6.5m transit delay.",
            "timestamp": time.time()
        })

        # Seed crowd demand
        demand_col = firestore_client.collection("passenger_demand")
        demand_col.document("STOP-001").set({
            "stop_id": "STOP-001",
            "passenger_count": 25,
            "crowd_level": "LOW",
            "congestion_ratio": 0.25,
            "timestamp": time.time()
        })
        demand_col.document("STOP-002").set({
            "stop_id": "STOP-002",
            "passenger_count": 115,
            "crowd_level": "HIGH",
            "congestion_ratio": 0.77,
            "timestamp": time.time()
        })


# Initialize seed data
_seed_sample_transit_state()


@app.get("/")
def get_dashboard_root():
    """Serves the public Leaflet map and live transit visualization dashboard."""
    t0 = time.time()
    try:
        if os.path.exists(STATIC_INDEX_PATH):
            with open(STATIC_INDEX_PATH, "r", encoding="utf-8") as f:
                content = f.read()
            _record_metric("get_dashboard_root", (time.time() - t0) * 1000)
            return Response(content=content, media_type="text/html")
        return {"message": "Transport Analytics API active. Static dashboard not found."}
    except Exception as e:
        logger.error(f"Error serving dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard")
def get_dashboard_alias():
    """Alias for / to access public transit dashboard."""
    return get_dashboard_root()


@app.get("/health")
def health_check():
    """Kubernetes liveness and readiness probe endpoint."""
    return {
        "status": "UP",
        "service": "transport-analytics-api",
        "version": "1.0.0",
        "timestamp": time.time()
    }


@app.get("/metrics")
def get_metrics():
    """Prometheus metrics exposition endpoint (Requirement h)."""
    lines = [
        "# HELP transport_analytics_http_requests_total Total HTTP requests handled",
        "# TYPE transport_analytics_http_requests_total counter"
    ]
    for endpoint, count in REQUEST_COUNTS.items():
        lines.append(f'transport_analytics_http_requests_total{{endpoint="{endpoint}"}} {count}')

    lines.append("# HELP transport_analytics_active_buses Current tracked transit buses")
    lines.append("# TYPE transport_analytics_active_buses gauge")
    buses_snap = firestore_client.collection("realtime_bus_estimates").stream()
    lines.append(f"transport_analytics_active_buses {len(buses_snap)}")

    lines.append("# HELP transport_analytics_delay_alerts_total Active transit delay alerts")
    lines.append("# TYPE transport_analytics_delay_alerts_total gauge")
    alerts_snap = firestore_client.collection("delay_alerts").stream()
    lines.append(f"transport_analytics_delay_alerts_total {len(alerts_snap)}")

    content = "\n".join(lines) + "\n"
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/api/v1/analytics/live-feed")
def get_live_feed():
    """Aggregated live telemetry feed for the public dashboard.
    Returns:
      - System KPIs (active buses, average speed, alerts count)
      - Tracked buses with coordinates and ETAs
      - Transit stops with geofence and crowd metrics
      - Active delay alerts
      - Upcoming stop arrivals countdown
    """
    t0 = time.time()
    try:
        # 1. Fetch Buses
        bus_docs = firestore_client.collection("realtime_bus_estimates").stream()
        buses: List[Dict[str, Any]] = []
        arrivals: List[Dict[str, Any]] = []
        total_speed = 0.0

        for snap in bus_docs:
            d = snap.to_dict() or {}
            bus_id = d.get("bus_id", snap.id)
            lat = d.get("latitude", d.get("current_lat", 28.3638))
            lon = d.get("longitude", d.get("current_lon", 75.5872))
            speed = float(d.get("speed_kmh", 0.0))
            total_speed += speed

            item = {
                "bus_id": bus_id,
                "route_id": d.get("route_id", "ROUTE-PILANI-01"),
                "latitude": lat,
                "longitude": lon,
                "speed_kmh": round(speed, 1),
                "next_stop_id": d.get("next_stop_id", "STOP-001"),
                "next_stop_name": d.get("next_stop_name", "Transit Stop"),
                "eta_seconds": int(d.get("eta_seconds", 300)),
                "status": d.get("status", "ON_TIME")
            }
            buses.append(item)

            arrivals.append({
                "bus_id": bus_id,
                "route_id": d.get("route_id", "ROUTE-PILANI-01"),
                "next_stop_id": d.get("next_stop_id", "STOP-001"),
                "next_stop_name": d.get("next_stop_name", "Transit Stop"),
                "eta_seconds": int(d.get("eta_seconds", 300)),
                "status": d.get("status", "ON_TIME"),
                "delay_minutes": float(d.get("delay_minutes", 0.0))
            })

        arrivals.sort(key=lambda x: x["eta_seconds"])

        # 2. Fetch Crowd Demand for Stops
        demand_docs = firestore_client.collection("passenger_demand").stream()
        crowd_map = {}
        for snap in demand_docs:
            d = snap.to_dict() or {}
            crowd_map[snap.id] = {
                "current_crowd": d.get("passenger_count", 0),
                "crowd_level": d.get("crowd_level", "LOW")
            }

        # 3. Build Stops List
        stops = []
        for s in DEFAULT_STOPS:
            crowd_info = crowd_map.get(s["stop_id"], {"current_crowd": 15, "crowd_level": "LOW"})
            stops.append({
                "stop_id": s["stop_id"],
                "stop_name": s["stop_name"],
                "latitude": s["latitude"],
                "longitude": s["longitude"],
                "geofence_radius_meters": s["geofence_radius_meters"],
                "current_crowd": crowd_info["current_crowd"],
                "crowd_level": crowd_info["crowd_level"]
            })

        # 4. Fetch Delay Alerts
        alert_docs = firestore_client.collection("delay_alerts").stream()
        alerts = []
        for snap in alert_docs:
            d = snap.to_dict() or {}
            alerts.append({
                "alert_id": d.get("alert_id", snap.id),
                "bus_id": d.get("bus_id", "UNKNOWN"),
                "route_id": d.get("route_id", "ROUTE-PILANI-01"),
                "stop_id": d.get("stop_id", "STOP-001"),
                "stop_name": d.get("stop_name", "Transit Stop"),
                "delay_minutes": float(d.get("delay_minutes", 5.0)),
                "severity": d.get("severity", "HIGH"),
                "message": d.get("message", "Service delay detected."),
                "timestamp": d.get("timestamp", time.time())
            })

        avg_speed = round(total_speed / len(buses), 1) if buses else 0.0

        response_data = {
            "kpis": {
                "active_buses": len(buses),
                "avg_speed_kmh": avg_speed,
                "alerts_count": len(alerts),
                "timestamp": time.time()
            },
            "buses": buses,
            "stops": stops,
            "alerts": alerts,
            "arrivals": arrivals
        }

        _record_metric("get_live_feed", (time.time() - t0) * 1000)
        return response_data

    except Exception as e:
        logger.error(f"Error generating live feed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/arrivals/{stop_id}")
def get_stop_arrivals(stop_id: str):
    """Arrivals countdown board for a specific transit stop."""
    t0 = time.time()
    try:
        # Match stop name
        stop_name = stop_id
        for s in DEFAULT_STOPS:
            if s["stop_id"] == stop_id:
                stop_name = s["stop_name"]
                break

        bus_docs = firestore_client.collection("realtime_bus_estimates").stream()
        arrivals = []
        for snap in bus_docs:
            d = snap.to_dict() or {}
            if d.get("next_stop_id") == stop_id or not d.get("next_stop_id"):
                arrivals.append({
                    "bus_id": d.get("bus_id", snap.id),
                    "route_id": d.get("route_id", "ROUTE-PILANI-01"),
                    "next_stop_id": stop_id,
                    "next_stop_name": stop_name,
                    "eta_seconds": int(d.get("eta_seconds", 300)),
                    "status": d.get("status", "ON_TIME"),
                    "delay_minutes": float(d.get("delay_minutes", 0.0))
                })

        arrivals.sort(key=lambda x: x["eta_seconds"])
        _record_metric("get_stop_arrivals", (time.time() - t0) * 1000)

        return {
            "stop_id": stop_id,
            "stop_name": stop_name,
            "arrivals": arrivals,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error fetching arrivals for stop {stop_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/delays")
def get_delays():
    """Lists all active transit delay alerts."""
    t0 = time.time()
    try:
        alert_docs = firestore_client.collection("delay_alerts").stream()
        alerts = [snap.to_dict() or {} for snap in alert_docs]
        _record_metric("get_delays", (time.time() - t0) * 1000)
        return {"alerts": alerts, "total_delays": len(alerts), "timestamp": time.time()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/fleet-stats")
def get_fleet_stats():
    """Aggregated fleet performance metrics."""
    t0 = time.time()
    try:
        bus_docs = firestore_client.collection("realtime_bus_estimates").stream()
        buses = [snap.to_dict() or {} for snap in bus_docs]
        delayed = [b for b in buses if b.get("status") == "DELAYED" or b.get("delay_minutes", 0) > 5.0]
        avg_speed = sum(b.get("speed_kmh", 0.0) for b in buses) / len(buses) if buses else 0.0

        health = "OPTIMAL"
        if len(delayed) > len(buses) // 2:
            health = "DEGRADED"
        elif len(delayed) > 0:
            health = "WARNING"

        _record_metric("get_fleet_stats", (time.time() - t0) * 1000)
        return {
            "total_buses": len(buses),
            "active_buses": len(buses),
            "delayed_buses": len(delayed),
            "avg_speed_kmh": round(avg_speed, 1),
            "system_health": health,
            "timestamp": time.time()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/analytics/stops")
def get_stops():
    """Lists all configured transit stops and geofences."""
    return {"stops": DEFAULT_STOPS, "total_stops": len(DEFAULT_STOPS)}


@app.post("/api/v1/analytics/seed-demo")
def seed_demo_data():
    """Utility endpoint to inject demonstration transit telemetry and delay incidents."""
    _seed_sample_transit_state()
    return {"status": "SUCCESS", "message": "Demo transit telemetry successfully seeded into Firestore."}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Transport Analytics Public API on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
