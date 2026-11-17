# Google Cloud Firestore Collections Schema (Storage Product 2: NoSQL)
## Requirement (g): Managed NoSQL Database for High-Throughput Semi-Structured Data

Firestore runs in Native Mode under Google Cloud's Always-Free Tier (1 GiB storage, 50,000 reads/day, 20,000 writes/day free).

---

### Collection 1: `realtime_bus_estimates`
Stores high-frequency, dynamic arrival estimates computed by Apache Flink (Service 5) and queried by Transport Analytics API (Service 8).

- **Document ID**: `{route_id}_{bus_id}` (e.g., `ROUTE-1_BUS-101`)
- **Fields**:
  ```json
  {
    "route_id": "ROUTE-1",
    "bus_id": "BUS-101",
    "current_latitude": 28.3664,
    "current_longitude": 75.5921,
    "speed_kmh": 32.5,
    "heading": 185.0,
    "next_stop_id": "STOP-004",
    "next_stop_name": "BITS Main Gate",
    "distance_to_stop_meters": 620,
    "eta_seconds": 125,
    "estimated_arrival_timestamp": "2026-11-18T01:55:00Z",
    "delay_seconds": 95,
    "status": "ON_TIME", // ON_TIME, DELAYED, EARLY
    "updated_at": "2026-11-18T01:52:55Z"
  }
  ```
- **Indexes**: Composite index on `route_id` (Ascending) + `updated_at` (Descending).

---

### Collection 2: `passenger_demand`
Powers Service 6 (Passenger Demand Service). Maintains live crowd levels and waiting passenger estimations per stop.

- **Document ID**: `{stop_id}` (e.g., `STOP-004`)
- **Fields**:
  ```json
  {
    "stop_id": "STOP-004",
    "stop_name": "BITS Main Gate",
    "waiting_passenger_count": 34,
    "crowd_level": "MODERATE", // LOW, MODERATE, HIGH, SURGE
    "rolling_hourly_boardings": 128,
    "rolling_hourly_alightings": 42,
    "last_tap_timestamp": "2026-11-18T01:52:10Z",
    "forecasted_demand_next_30m": 45
  }
  ```

---

### Collection 3: `delay_alerts`
Written by Service 7 (Delay Alert Service - Serverless Cloud Function). Stores active transit disruptions and dispatch warnings.

- **Document ID**: `ALT_{timestamp}_{bus_id}` (e.g., `ALT_20261118_BUS101`)
- **Fields**:
  ```json
  {
    "alert_id": "ALT-20261118-0101",
    "bus_id": "BUS-101",
    "route_id": "ROUTE-1",
    "stop_id": "STOP-004",
    "delay_minutes": 6.5,
    "severity": "MODERATE", // MINOR (3-5m), MODERATE (5-15m), SEVERE (>15m)
    "trigger_reason": "CONGESTION_NEAR_CIRCLE",
    "alert_message": "BUS-101 on Route 1A delayed by 6.5 minutes approaching BITS Main Gate.",
    "is_active": true,
    "created_at": "2026-11-18T01:53:00Z"
  }
  ```
- **Indexes**: Composite index on `is_active` (Ascending) + `created_at` (Descending).

