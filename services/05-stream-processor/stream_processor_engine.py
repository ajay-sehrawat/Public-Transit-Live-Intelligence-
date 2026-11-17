# -*- coding: utf-8 -*-
"""Stream Processor Engine (Apache Flink Semantics in Python)
Implements:
  1. Event-Time Processing with WatermarkStrategy (BoundedOutOfOrderness)
  2. Late-Event Detection & Side Output Handling
  3. Keyed Stateful 1-Minute Tumbling Window Aggregation
  4. Rolling Velocity, Dynamic ETA & Delay Calculation
  5. Publishing to Kafka Results Topics ('bus-arrival-estimates', 'bus-route-stats')
"""

import os
import sys
import time
import math
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

from services.common.kafka.kafka_client import TransitKafkaProducer, TransitKafkaConsumer

logger = logging.getLogger("FlinkStreamProcessor")

WINDOW_SIZE_MS = 60 * 1000            # 1-minute Tumbling Window (60,000 ms)
WATERMARK_LAG_MS = 20 * 1000          # 20-second Bounded Out-of-Orderness Tolerance
DELAY_THRESHOLD_SEC = 300             # 5 minutes delay threshold for alerts
NOMINAL_FLEET_SPEED_KMH = 25.0        # Default fallback speed for stationary vehicles

def iso_from_epoch_ms(epoch_ms: int) -> str:
    """Converts millisecond epoch timestamp to ISO-8601 UTC string."""
    dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

class StreamProcessorEngine:
    """Stateful stream processing engine matching Apache Flink specifications."""

    def __init__(self,
                 kafka_producer: Optional[TransitKafkaProducer] = None,
                 input_topic: str = "bus-gps-normalized",
                 results_topic: str = "bus-arrival-estimates",
                 stats_topic: str = "bus-route-stats"):
        self.producer = kafka_producer or TransitKafkaProducer()
        self.input_topic = input_topic
        self.results_topic = results_topic
        self.stats_topic = stats_topic

        # Watermark State
        self.max_event_time_seen: int = 0
        self.current_watermark: int = 0

        # Window State: (window_end, route_id, bus_id) -> list of events
        self.windows: Dict[Tuple[int, str, str], List[Dict[str, Any]]] = {}

        # Late Event Side Output
        self.late_events_side_output: List[Dict[str, Any]] = []

        # Processed Results Archive
        self.emitted_arrival_estimates: List[Dict[str, Any]] = []
        self.emitted_route_stats: List[Dict[str, Any]] = []

    def process_event(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processes a single normalized telemetry event using Flink event-time windowing."""
        event_time = int(event.get("event_timestamp", int(time.time() * 1000)))
        route_id = event.get("route_id", "ROUTE-1")
        bus_id = event.get("bus_id", "UNKNOWN")

        # 1. Update Watermark Tracking
        if event_time > self.max_event_time_seen:
            self.max_event_time_seen = event_time
            self.current_watermark = max(0, self.max_event_time_seen - WATERMARK_LAG_MS)

        # 2. Check for Late Events (Event-Time < Current Watermark)
        if self.current_watermark > 0 and event_time < self.current_watermark:
            logger.warning(
                f"⚠️ [LATE EVENT] Event {event.get('event_id')} for {bus_id} arrived late! "
                f"(EventTime: {event_time}, Watermark: {self.current_watermark}). "
                f"Diverting to Side Output."
            )
            self.late_events_side_output.append({
                "reason": "BOUNDED_OUT_OF_ORDERNESS_EXCEEDED",
                "watermark_ms": self.current_watermark,
                "event": event
            })
            return None

        # 3. Assign Event to 1-Minute Tumbling Window
        window_start = (event_time // WINDOW_SIZE_MS) * WINDOW_SIZE_MS
        window_end = window_start + WINDOW_SIZE_MS
        window_key = (window_end, route_id, bus_id)

        if window_key not in self.windows:
            self.windows[window_key] = []
        self.windows[window_key].append(event)

        # 4. Trigger Any Windows Whose End Time is Passed by Watermark
        triggered = self._check_and_trigger_windows()
        return triggered[-1] if triggered else None

    def flush_all_windows(self) -> List[Dict[str, Any]]:
        """Forces evaluation of all open windows (used on job shutdown or test checkpoints)."""
        return self._check_and_trigger_windows(force=True)

    def _check_and_trigger_windows(self, force: bool = False) -> List[Dict[str, Any]]:
        """Evaluates and fires stateful window aggregations when watermark advances past window_end."""
        triggered_results = []
        keys_to_purge = []

        for window_key, events in list(self.windows.items()):
            window_end, route_id, bus_id = window_key

            # Flink window fires when watermark advances past window_end
            if self.current_watermark >= window_end or force:
                result = self._aggregate_window(window_end, route_id, bus_id, events)
                if result:
                    triggered_results.append(result)
                    keys_to_purge.append(window_key)

        for k in keys_to_purge:
            del self.windows[k]

        return triggered_results

    def _aggregate_window(self, window_end: int, route_id: str,
                          bus_id: str, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates rolling velocity, distance to stop, and arrival ETA for a 1-min window."""
        window_start = window_end - WINDOW_SIZE_MS
        sample_count = len(events)
        if sample_count == 0:
            return None

        # 1. Compute Rolling Average Velocity over the 1-minute window
        total_speed = sum(float(e.get("speed_kmh", 0.0)) for e in events)
        rolling_avg_speed_kmh = round(total_speed / sample_count, 2)

        # 2. Extract latest spatial proximity
        latest_event = events[-1]
        next_stop_id = latest_event.get("next_stop_id", "STOP-001")
        next_stop_name = latest_event.get("next_stop_name", "Transit Stop")
        distance_meters = float(latest_event.get("distance_to_next_stop_meters", 500.0))
        inside_geofence = latest_event.get("is_inside_geofence", False)

        # 3. Dynamic ETA Calculation
        # Speed in m/s:
        speed_ms = (rolling_avg_speed_kmh * 1000.0) / 3600.0
        if speed_ms < 1.0:
            # Fallback nominal speed if bus is stopped at traffic light or station
            speed_ms = (NOMINAL_FLEET_SPEED_KMH * 1000.0) / 3600.0

        dwell_time_sec = 30  # Standard stop dwell time
        if inside_geofence:
            eta_seconds = 0
            transit_status = "ARRIVED"
        else:
            eta_seconds = int(distance_meters / speed_ms) + dwell_time_sec
            transit_status = "EN_ROUTE"

        estimated_arrival_epoch_ms = window_end + (eta_seconds * 1000)
        estimated_arrival_iso = iso_from_epoch_ms(estimated_arrival_epoch_ms)

        # 4. Delay against scheduled timetable (simulated standard segment baseline)
        nominal_travel_sec = 180
        delay_seconds = max(0, eta_seconds - nominal_travel_sec)
        delay_status = "DELAYED" if delay_seconds > DELAY_THRESHOLD_SEC else "ON_TIME"

        # 5. Build Aggregated Result Record
        arrival_estimate_result = {
            "window_start": iso_from_epoch_ms(window_start),
            "window_end": iso_from_epoch_ms(window_end),
            "window_epoch_ms": window_end,
            "route_id": route_id,
            "bus_id": bus_id,
            "sample_count": sample_count,
            "rolling_avg_speed_kmh": rolling_avg_speed_kmh,
            "next_stop_id": next_stop_id,
            "next_stop_name": next_stop_name,
            "distance_to_stop_meters": distance_meters,
            "eta_seconds": eta_seconds,
            "estimated_arrival_timestamp": estimated_arrival_iso,
            "delay_seconds": delay_seconds,
            "transit_status": transit_status,
            "status": delay_status,
            "calculated_at": iso_from_epoch_ms(int(time.time() * 1000))
        }

        # 6. Build Route-level Aggregated Statistics
        route_stats = {
            "route_id": route_id,
            "calculation_window_end": iso_from_epoch_ms(window_end),
            "active_buses_in_window": 1,
            "average_route_speed_kmh": rolling_avg_speed_kmh,
            "congestion_level": "HIGH" if rolling_avg_speed_kmh < 15.0 else "NORMAL"
        }

        # 7. Publish Results to Kafka Topics
        self.producer.send(self.results_topic, key=bus_id, value=arrival_estimate_result)
        self.producer.send(self.stats_topic, key=route_id, value=route_stats)

        self.emitted_arrival_estimates.append(arrival_estimate_result)
        self.emitted_route_stats.append(route_stats)

        logger.info(
            f"⚡ [Flink Window] Aggregated 1-min window for {bus_id} ({route_id}): "
            f"Avg Speed={rolling_avg_speed_kmh} km/h, Next Stop={next_stop_name}, "
            f"ETA={eta_seconds}s, Delay={delay_seconds}s [{delay_status}]"
        )

        return arrival_estimate_result
