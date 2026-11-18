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

# Route waypoint networks for real-time bus trajectory simulation
ROUTE_WAYPOINTS = {
    "ROUTE-1": [
        {"stop_id": "STOP-001", "name": "Pilani Bus Stand", "lat": 28.3638, "lon": 75.5872},
        {"stop_id": "STOP-002", "name": "BITS Clock Tower", "lat": 28.3645, "lon": 75.5885},
        {"stop_id": "STOP-003", "name": "Library Circle", "lat": 28.3658, "lon": 75.5901},
        {"stop_id": "STOP-004", "name": "Hostel Gate 2", "lat": 28.3672, "lon": 75.5925},
        {"stop_id": "STOP-005", "name": "CEERI Main Gate", "lat": 28.3695, "lon": 75.5950},
    ],
    "ROUTE-2": [
        {"stop_id": "STOP-001", "name": "Pilani Bus Stand", "lat": 28.3638, "lon": 75.5872},
        {"stop_id": "STOP-002", "name": "BITS Clock Tower", "lat": 28.3645, "lon": 75.5885},
        {"stop_id": "STOP-004", "name": "Hostel Gate 2", "lat": 28.3672, "lon": 75.5925},
        {"stop_id": "STOP-005", "name": "CEERI Main Gate", "lat": 28.3695, "lon": 75.5950},
    ],
    "ROUTE-3": [
        {"stop_id": "STOP-005", "name": "CEERI Main Gate", "lat": 28.3695, "lon": 75.5950},
        {"stop_id": "STOP-003", "name": "Library Circle", "lat": 28.3658, "lon": 75.5901},
        {"stop_id": "STOP-002", "name": "BITS Clock Tower", "lat": 28.3645, "lon": 75.5885},
        {"stop_id": "STOP-001", "name": "Pilani Bus Stand", "lat": 28.3638, "lon": 75.5872},
    ]
}

# Live dynamic fleet simulation state
import math
import random
import threading

LIVE_FLEET_STATE = {
    "BUS-101": {"route_id": "ROUTE-1", "lat": 28.3640, "lon": 75.5878, "target_idx": 1, "dir": 1, "speed": 34.0, "status": "ON_TIME", "delay": 0.0},
    "BUS-102": {"route_id": "ROUTE-1", "lat": 28.3662, "lon": 75.5910, "target_idx": 3, "dir": 1, "speed": 11.5, "status": "DELAYED", "delay": 6.5},
    "BUS-103": {"route_id": "ROUTE-1", "lat": 28.3690, "lon": 75.5945, "target_idx": 3, "dir": -1, "speed": 28.0, "status": "ON_TIME", "delay": 0.0},
    "BUS-201": {"route_id": "ROUTE-2", "lat": 28.3642, "lon": 75.5880, "target_idx": 2, "dir": 1, "speed": 31.0, "status": "ON_TIME", "delay": 0.0},
    "BUS-202": {"route_id": "ROUTE-2", "lat": 28.3670, "lon": 75.5920, "target_idx": 1, "dir": -1, "speed": 25.5, "status": "ON_TIME", "delay": 0.0},
    "BUS-301": {"route_id": "ROUTE-3", "lat": 28.3692, "lon": 75.5948, "target_idx": 1, "dir": 1, "speed": 36.8, "status": "ON_TIME", "delay": 0.0},
    "BUS-401": {"route_id": "ROUTE-2", "lat": 28.3648, "lon": 75.5890, "target_idx": 1, "dir": 1, "speed": 19.2, "status": "ON_TIME", "delay": 0.0},
}


def _run_live_bus_movement_engine():
    """Background engine that continuously moves all active buses along their routes in real time."""
    logger.info("[✓] Live Bus GPS Movement Simulation Engine started.")
    est_col = firestore_client.collection("realtime_bus_estimates")

    while True:
        try:
            for bus_id, state in LIVE_FLEET_STATE.items():
                route_id = state["route_id"]
                waypoints = ROUTE_WAYPOINTS.get(route_id, ROUTE_WAYPOINTS["ROUTE-1"])
                target_idx = state["target_idx"]
                target_wp = waypoints[target_idx]

                cur_lat = state["lat"]
                cur_lon = state["lon"]
                tgt_lat = target_wp["lat"]
                tgt_lon = target_wp["lon"]

                dlat = tgt_lat - cur_lat
                dlon = tgt_lon - cur_lon
                dist = math.hypot(dlat, dlon)
                dist_meters = dist * 111000

                if dist < 0.00030 or dist_meters < 35:
                    # Bus arrived at waypoint stop, advance to next
                    next_idx = target_idx + state["dir"]
                    if next_idx >= len(waypoints):
                        state["dir"] = -1
                        state["target_idx"] = len(waypoints) - 2
                    elif next_idx < 0:
                        state["dir"] = 1
                        state["target_idx"] = 1
                    else:
                        state["target_idx"] = next_idx

                    target_wp = waypoints[state["target_idx"]]
                else:
                    # Advance bus towards waypoint
                    base_speed = 12.0 if state["status"] == "DELAYED" else 33.0
                    current_speed = max(10.0, base_speed + random.uniform(-2.0, 2.0))
                    state["speed"] = round(current_speed, 1)

                    travel_meters = (current_speed / 3.6) * 1.5
                    step_ratio = min(0.35, travel_meters / max(dist_meters, 1.0))

                    state["lat"] = cur_lat + dlat * step_ratio
                    state["lon"] = cur_lon + dlon * step_ratio

                # Calculate live ETA:
                # 1. Base transit travel time to next stop (proportional to remaining distance along route leg)
                remaining_dist_meters = math.hypot(target_wp["lat"] - state["lat"], target_wp["lon"] - state["lon"]) * 111000
                leg_progress = min(1.0, max(0.08, remaining_dist_meters / 200.0))
                # Base travel time scales between 25s (near stop) and 180s (3 mins at start of leg)
                base_transit_sec = max(25, int(180 * leg_progress))

                # 2. Add accumulated transit delay (delay_minutes * 60)
                delay_mins = float(state.get("delay", 0.0))
                delay_sec = int(delay_mins * 60)
                eta_sec = base_transit_sec + delay_sec

                # Update Firestore in-memory document
                doc_payload = {
                    "bus_id": bus_id,
                    "route_id": route_id,
                    "current_lat": round(state["lat"], 6),
                    "current_lon": round(state["lon"], 6),
                    "latitude": round(state["lat"], 6),
                    "longitude": round(state["lon"], 6),
                    "speed_kmh": state["speed"],
                    "next_stop_id": target_wp["stop_id"],
                    "next_stop_name": target_wp["name"],
                    "eta_seconds": eta_sec,
                    "delay_minutes": delay_mins,
                    "status": state["status"],
                    "updated_at": time.time()
                }
                est_col.document(bus_id).set(doc_payload)

            time.sleep(1.5)
        except Exception as e:
            logger.error(f"Error in bus movement engine: {e}")
            time.sleep(2.0)


# Start the background movement engine thread immediately
_movement_thread = threading.Thread(target=_run_live_bus_movement_engine, daemon=True)
_movement_thread.start()


def _record_metric(endpoint: str, latency_ms: float):
    REQUEST_COUNTS[endpoint] = REQUEST_COUNTS.get(endpoint, 0) + 1
    REQUEST_LATENCIES[endpoint] = REQUEST_LATENCIES.get(endpoint, 0.0) + latency_ms


def _seed_sample_transit_state(force: bool = False):
    """Seeds realistic transit telemetry into Firestore matching the registered vehicle fleet."""
    est_col = firestore_client.collection("realtime_bus_estimates")
    existing = est_col.stream()
    if force or not existing or len(existing) < 7:
        logger.info("Initializing Firestore with all 7 active transit fleet buses...")
        # 7 Active buses across ROUTE-1, ROUTE-2, ROUTE-3 (BUS-302 is in MAINTENANCE at depot)
        buses = [
            {
                "bus_id": "BUS-101",
                "route_id": "ROUTE-1",
                "current_lat": 28.3640,
                "current_lon": 75.5878,
                "latitude": 28.3640,
                "longitude": 75.5878,
                "speed_kmh": 34.2,
                "next_stop_id": "STOP-002",
                "next_stop_name": "BITS Clock Tower",
                "eta_seconds": 120,
                "delay_minutes": 0.0,
                "status": "ON_TIME",
                "updated_at": time.time()
            },
            {
                "bus_id": "BUS-102",
                "route_id": "ROUTE-1",
                "current_lat": 28.3662,
                "current_lon": 75.5910,
                "latitude": 28.3662,
                "longitude": 75.5910,
                "speed_kmh": 11.5,
                "next_stop_id": "STOP-004",
                "next_stop_name": "Hostel Gate 2",
                "eta_seconds": 450,
                "delay_minutes": 6.5,
                "status": "DELAYED",
                "updated_at": time.time()
            },
            {
                "bus_id": "BUS-103",
                "route_id": "ROUTE-1",
                "current_lat": 28.3635,
                "current_lon": 75.5865,
                "latitude": 28.3635,
                "longitude": 75.5865,
                "speed_kmh": 28.0,
                "next_stop_id": "STOP-001",
                "next_stop_name": "Pilani Bus Stand",
                "eta_seconds": 180,
                "delay_minutes": 0.0,
                "status": "ON_TIME",
                "updated_at": time.time()
            },
            {
                "bus_id": "BUS-201",
                "route_id": "ROUTE-2",
                "current_lat": 28.3670,
                "current_lon": 75.5920,
                "latitude": 28.3670,
                "longitude": 75.5920,
                "speed_kmh": 31.0,
                "next_stop_id": "STOP-005",
                "next_stop_name": "CEERI Main Gate",
                "eta_seconds": 210,
                "delay_minutes": 0.0,
                "status": "ON_TIME",
                "updated_at": time.time()
            },
            {
                "bus_id": "BUS-202",
                "route_id": "ROUTE-2",
                "current_lat": 28.3690,
                "current_lon": 75.5945,
                "latitude": 28.3690,
                "longitude": 75.5945,
                "speed_kmh": 25.5,
                "next_stop_id": "STOP-003",
                "next_stop_name": "Library Circle",
                "eta_seconds": 320,
                "delay_minutes": 0.0,
                "status": "ON_TIME",
                "updated_at": time.time()
            },
            {
                "bus_id": "BUS-301",
                "route_id": "ROUTE-3",
                "current_lat": 28.3620,
                "current_lon": 75.5850,
                "latitude": 28.3620,
                "longitude": 75.5850,
                "speed_kmh": 36.8,
                "next_stop_id": "STOP-001",
                "next_stop_name": "Pilani Bus Stand",
                "eta_seconds": 260,
                "delay_minutes": 0.0,
                "status": "ON_TIME",
                "updated_at": time.time()
            },
            {
                "bus_id": "BUS-401",
                "route_id": "ROUTE-2",
                "current_lat": 28.3655,
                "current_lon": 75.5895,
                "latitude": 28.3655,
                "longitude": 75.5895,
                "speed_kmh": 18.2,
                "next_stop_id": "STOP-002",
                "next_stop_name": "BITS Clock Tower",
                "eta_seconds": 95,
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
            "route_id": "ROUTE-1",
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

            delay_mins = float(d.get("delay_minutes", 0.0))
            eta_sec = int(d.get("eta_seconds", 180))

            # Guarantee delayed buses strictly reflect delay time in ETA
            delay_sec = int(delay_mins * 60)
            if delay_sec > 0 and eta_sec < (delay_sec + 25):
                eta_sec = delay_sec + max(25, eta_sec)

            item = {
                "bus_id": bus_id,
                "route_id": d.get("route_id", "ROUTE-PILANI-01"),
                "latitude": lat,
                "longitude": lon,
                "speed_kmh": round(speed, 1),
                "next_stop_id": d.get("next_stop_id", "STOP-001"),
                "next_stop_name": d.get("next_stop_name", "Transit Stop"),
                "eta_seconds": eta_sec,
                "delay_minutes": delay_mins,
                "status": d.get("status", "ON_TIME")
            }
            buses.append(item)

            arrivals.append({
                "bus_id": bus_id,
                "route_id": d.get("route_id", "ROUTE-PILANI-01"),
                "next_stop_id": d.get("next_stop_id", "STOP-001"),
                "next_stop_name": d.get("next_stop_name", "Transit Stop"),
                "eta_seconds": eta_sec,
                "delay_minutes": delay_mins,
                "status": d.get("status", "ON_TIME")
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
                delay_mins = float(d.get("delay_minutes", 0.0))
                eta_sec = int(d.get("eta_seconds", 180))
                delay_sec = int(delay_mins * 60)
                if delay_sec > 0 and eta_sec < (delay_sec + 25):
                    eta_sec = delay_sec + max(25, eta_sec)

                arrivals.append({
                    "bus_id": d.get("bus_id", snap.id),
                    "route_id": d.get("route_id", "ROUTE-PILANI-01"),
                    "next_stop_id": stop_id,
                    "next_stop_name": stop_name,
                    "eta_seconds": eta_sec,
                    "status": d.get("status", "ON_TIME"),
                    "delay_minutes": delay_mins
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
    _seed_sample_transit_state(force=True)
    return {"status": "SUCCESS", "message": "Demo transit telemetry successfully seeded into Firestore."}


@app.post("/api/v1/analytics/dispatch-bus")
def dispatch_new_bus(payload: Dict[str, Any] = None):
    """Dynamically adds and dispatches a new transit bus to the live operational fleet."""
    if not payload:
        payload = {}

    bus_num = len(LIVE_FLEET_STATE) + 101
    bus_id = str(payload.get("bus_id") or f"BUS-{bus_num}")
    route_id = str(payload.get("route_id") or "ROUTE-1")
    model = str(payload.get("model") or "Tata Starbus EV")
    capacity = int(payload.get("capacity") or 50)

    # Get initial waypoint coordinates for the selected route
    waypoints = ROUTE_WAYPOINTS.get(route_id, ROUTE_WAYPOINTS["ROUTE-1"])
    start_wp = waypoints[0]

    # Register in live fleet simulation
    LIVE_FLEET_STATE[bus_id] = {
        "route_id": route_id,
        "lat": start_wp["lat"],
        "lon": start_wp["lon"],
        "target_idx": 1,
        "dir": 1,
        "speed": 32.0,
        "status": "ON_TIME",
        "delay": 0.0
    }

    # Immediately write to Firestore
    est_col = firestore_client.collection("realtime_bus_estimates")
    est_col.document(bus_id).set({
        "bus_id": bus_id,
        "route_id": route_id,
        "current_lat": start_wp["lat"],
        "current_lon": start_wp["lon"],
        "latitude": start_wp["lat"],
        "longitude": start_wp["lon"],
        "speed_kmh": 32.0,
        "next_stop_id": waypoints[1]["stop_id"],
        "next_stop_name": waypoints[1]["name"],
        "eta_seconds": 120,
        "delay_minutes": 0.0,
        "status": "ON_TIME",
        "updated_at": time.time()
    })

    logger.info(f"[+] Dispatched new bus {bus_id} ({model}, cap: {capacity}) on {route_id}.")
    return {
        "status": "DEPLOYED",
        "bus_id": bus_id,
        "route_id": route_id,
        "model": model,
        "capacity": capacity,
        "message": f"Bus {bus_id} deployed and moving live on {route_id}."
    }


@app.post("/api/v1/analytics/trigger-delay")
def trigger_transit_delay(payload: Dict[str, Any] = None):
    """Simulates a severe traffic incident / roadblock causing bus delay."""
    if not payload:
        payload = {}

    bus_id = str(payload.get("bus_id") or "BUS-101")
    delay_mins = float(payload.get("delay_minutes") if payload.get("delay_minutes") is not None else 8.5)
    reason = str(payload.get("reason") or "Heavy traffic bottleneck near Library Circle.")

    est_col = firestore_client.collection("realtime_bus_estimates")
    alert_col = firestore_client.collection("delay_alerts")

    if bus_id in LIVE_FLEET_STATE:
        state = LIVE_FLEET_STATE[bus_id]
        if delay_mins > 0:
            state["status"] = "DELAYED"
            state["delay"] = delay_mins
            state["speed"] = 9.0
        else:
            state["status"] = "ON_TIME"
            state["delay"] = 0.0
            state["speed"] = 32.0

        target_wp = ROUTE_WAYPOINTS.get(state["route_id"], ROUTE_WAYPOINTS["ROUTE-1"])[state["target_idx"]]
        base_transit_sec = 120
        delay_sec = int(delay_mins * 60)
        new_eta_sec = base_transit_sec + delay_sec

        est_col.document(bus_id).set({
            "bus_id": bus_id,
            "route_id": state["route_id"],
            "current_lat": round(state["lat"], 6),
            "current_lon": round(state["lon"], 6),
            "latitude": round(state["lat"], 6),
            "longitude": round(state["lon"], 6),
            "speed_kmh": state["speed"],
            "next_stop_id": target_wp["stop_id"],
            "next_stop_name": target_wp["name"],
            "eta_seconds": new_eta_sec,
            "delay_minutes": delay_mins,
            "status": state["status"],
            "updated_at": time.time()
        })

    # Alert management in delay_alerts collection
    alert_id = f"ALERT-{bus_id}"
    if delay_mins > 0:
        alert_col.document(alert_id).set({
            "alert_id": alert_id,
            "bus_id": bus_id,
            "route_id": LIVE_FLEET_STATE.get(bus_id, {}).get("route_id", "ROUTE-1"),
            "stop_id": "STOP-003",
            "stop_name": "Library Circle",
            "delay_minutes": delay_mins,
            "severity": "CRITICAL" if delay_mins >= 10 else "HIGH",
            "message": f"Transit Alert: Bus {bus_id} is delayed by {delay_mins} mins. {reason}",
            "timestamp": time.time()
        })
    else:
        try:
            alert_col.document(alert_id).delete()
            if bus_id == "BUS-102":
                alert_col.document("ALERT-BUS-102").delete()
        except Exception:
            pass

    logger.warning(f"[!] Delay incident triggered for {bus_id}: {delay_mins}m late.")
    return {
        "status": "ALERT_DISPATCHED",
        "alert_id": alert_id,
        "bus_id": bus_id,
        "delay_minutes": delay_mins,
        "severity": "CRITICAL" if delay_mins >= 10 else "HIGH"
    }


@app.post("/api/v1/analytics/simulate-crowd")
def simulate_station_crowd(payload: Dict[str, Any] = None):
    """Simulates passenger smartcard tap surge at a campus transit stop."""
    if not payload:
        payload = {}

    stop_id = str(payload.get("stop_id") or "STOP-002")
    count = int(payload.get("passenger_count") or 145)
    level = "SURGE" if count > 130 else ("HIGH" if count > 80 else ("MODERATE" if count > 30 else "LOW"))

    demand_col = firestore_client.collection("passenger_demand")
    demand_col.document(stop_id).set({
        "stop_id": stop_id,
        "passenger_count": count,
        "crowd_level": level,
        "congestion_ratio": min(1.0, count / 150.0),
        "timestamp": time.time()
    })

    return {
        "status": "CROWD_UPDATED",
        "stop_id": stop_id,
        "passenger_count": count,
        "crowd_level": level
    }


if __name__ == "__main__":
    from services.common.compat import run_server
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Transport Analytics Public API on port {port}...")
    run_server(app, host="0.0.0.0", port=port)
