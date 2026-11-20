# S11 Public Transit Platform: Master Microservice Demonstration & Viva Guide

**BITS Pilani — CS/SS G527 Cloud Computing Assignment (Scenario S11)**  
* **GCP Project ID**: `transit-s11-bits-12730` (Region: `us-central1`, Zone: `us-central1-a`)  
* **Live GKE Public Ingress IP**: `http://8.233.33.106` (Active Port 80)  
* **Live Cloud SQL PostgreSQL**: `34.46.78.203:5432` (`transit_admin` / `transit_db`)  
* **Live Public Web Dashboard**: [http://8.233.33.106/](http://8.233.33.106/)  

---

## 🛠️ Step 0: Pre-Flight Setup in Cloud Shell

Before calling the professor over, make sure all services are reachable:

```bash
cd ~/transit-cloud
git pull origin main

# Option A: Start all background microservices locally for direct port testing (8001, 8003, 8004, 8006):
./scripts/start_all_local.sh

# Verify all services and ports are actively listening:
python3 scripts/check_status.py
```

> **Note on `localhost` vs `8.233.33.106`**:
> * **Public Edge Gateways (MS 2 & MS 8)** are routed via the Google Cloud Load Balancer at `http://8.233.33.106`.
> * **Internal Backend Services (MS 1, 3, 4, 6)** are Kubernetes `ClusterIP` services. Exposing internal databases to the public internet violates cloud security principles. They are reached either via local daemons or via `kubectl port-forward`.

---

## 📋 Part 1: How to Prove All Microservices are Running on GKE

When the professor asks *"Show me whether the microservices are running in Kubernetes"*, run:

```bash
# 1. Show all running pods in the transit namespace:
kubectl get pods -n transit-system -o wide

# 2. Show all Kubernetes ClusterIP & LoadBalancer services:
kubectl get svc -n transit-system

# 3. Show the active Google Cloud Ingress Load Balancer:
kubectl get ingress -n transit-system

# 4. Show live Horizontal Pod Autoscalers (HPA):
kubectl get hpa -n transit-system

# 5. Show live stream logs of the API gateway processing traffic:
kubectl logs -n transit-system -l app=transport-analytics --tail=20
```

---

## 🚀 Part 2: Step-by-Step Microservice Demonstrations & Viva Scripts

---

### 🚌 Microservice 1: Vehicle Registry Service (Owner: Member 1)

* **Architecture**: Fleet master inventory, Cloud SQL PostgreSQL database, and sub-3ms gRPC Protocol Buffer server.
* **Rubric Mapping**: Task (a) — Cloud Relational Database Management & High-Performance Inter-Service RPC.

#### 💻 Commands to Run:
```bash
# 1. Query the live Cloud SQL PostgreSQL database directly:
PGPASSWORD='TransitSecurePass2026!' psql -h 34.46.78.203 -U transit_admin -d transit_db \
  -c "SELECT bus_id, model, capacity, status, assigned_route_id FROM vehicles LIMIT 5;"

# 2. Query the vehicle fleet via REST API (ClusterIP service):
curl -s http://localhost:8001/api/v1/vehicles | jq .

# 3. Test inter-service bus validation endpoint:
curl -s -X POST http://localhost:8001/api/v1/vehicles/BUS-101/validate | jq .
```

#### 🗣️ What to Say Out Loud to the Professor:
> *"Sir/Ma'am, Microservice 1 is our authoritative fleet registry. It connects directly to our Google Cloud SQL PostgreSQL database instance. We chose a relational database here because vehicle master records—such as bus IDs, passenger capacities, and assigned routes—require strict ACID guarantees and foreign key relational constraints. In addition to REST, this service runs an internal gRPC server on port 50051 to provide sub-3ms validation for high-frequency GPS ingestion."*

#### 🎯 Likely Follow-Up Question & Knockout Answer:
* **Prof**: *"Why did you use a relational database instead of MongoDB or Firestore for the vehicle registry?"*
* **Answer**: *"Because fleet metadata is structured and relational. Vehicles belong to specific routes and transit depots; foreign key constraints prevent orphan route assignments, and ACID transactions prevent double-registering the same bus license or chassis ID."*

---

### 📡 Microservice 2: GPS Ingestion Service (Owner: Member 1)

* **Architecture**: High-throughput telemetry REST gateway, Pydantic coordinate validation, and Apache Kafka publisher (`bus-gps-raw`).
* **Rubric Mapping**: Task (b) — High-Velocity Ingestion Gateway & Message Queue Decoupling.

#### 💻 Commands to Run:
```bash
# 1. Ingest a valid GPS coordinate via the public GKE Ingress (Returns HTTP 202 ACCEPTED):
curl -s -X POST "http://8.233.33.106/api/v1/telemetry" \
  -H "Content-Type: application/json" \
  -d '{
    "bus_id": "BUS-101",
    "latitude": 28.3645,
    "longitude": 75.5885,
    "speed_kmh": 36.5,
    "heading": 180.0,
    "timestamp": "2026-11-20T10:00:00Z"
  }' | jq .

# 2. Demonstrate validation rejection (Bus BUS-302 is in MAINTENANCE -> HTTP 400 Bad Request):
curl -s -X POST "http://8.233.33.106/api/v1/telemetry" \
  -H "Content-Type: application/json" \
  -d '{
    "bus_id": "BUS-302",
    "latitude": 28.3645,
    "longitude": 75.5885,
    "speed_kmh": 0.0,
    "heading": 0.0,
    "timestamp": "2026-11-20T10:00:00Z"
  }' | jq .

# 3. Demonstrate Pydantic boundary validation (Missing required fields -> HTTP 422 Unprocessable Entity):
curl -s -X POST "http://8.233.33.106/api/v1/telemetry" \
  -H "Content-Type: application/json" \
  -d '{"bus_id": "BUS-101", "latitude": 999.0}' | jq .
```

#### 🗣️ What to Say Out Loud to the Professor:
> *"Microservice 2 is our high-throughput edge telemetry gateway exposed on our public Ingress. When IoT sensors on buses transmit GPS packets, Microservice 2 performs two-stage validation: first, Pydantic validates coordinate boundaries within -90 to +90 latitude; second, it makes a low-latency gRPC call to Microservice 1 to confirm the vehicle is registered and active. Validated packets are immediately published to Apache Kafka (`bus-gps-raw`) so our ingestion gateway never blocks waiting for slow database writes."*

#### 🎯 Likely Follow-Up Question & Knockout Answer:
* **Prof**: *"Why HTTP 202 Accepted instead of 200 OK?"*
* **Answer**: *"HTTP 202 represents asynchronous processing. The ingestion gateway has validated the payload and committed it to Kafka, but the heavy stream calculations and database writes happen asynchronously downstream."*

---

### 🗺️ Microservice 3: Route Service (Owner: Member 2)

* **Architecture**: Route geometries, milestone stop sequences, and spherical Haversine trigonometric geofencing.
* **Rubric Mapping**: Task (c) — Managed Kubernetes & Microservice Geometry Engine.

#### 💻 Commands to Run:
```bash
# 1. Query the transit stop network and geofence perimeters:
curl -s http://8.233.33.106/api/v1/analytics/stops | jq .

# 2. Query Route 1 waypoint sequence & milestone stops:
curl -s http://localhost:8003/api/v1/routes/ROUTE-1 | jq .

# 3. Calculate nearest stop using spherical Haversine distance:
curl -s "http://localhost:8003/api/v1/stops/nearest?lat=28.3638&lon=75.5872" | jq .
```

#### 🗣️ What to Say Out Loud to the Professor:
> *"Microservice 3 maintains the route topology, ordered stop sequences, and spatial boundaries for the Pilani transit network. We implemented the spherical Haversine trigonometric distance formula in this service. It calculates the great-circle distance between moving GPS coordinates and fixed transit stops, dynamically detecting when a bus penetrates a stop's geofence radius (50m to 90m)."*

#### 🎯 Likely Follow-Up Question & Knockout Answer:
* **Prof**: *"Why use the Haversine formula instead of simple Euclidean distance $\sqrt{(x_2-x_1)^2 + (y_2-y_1)^2}$?"*
* **Answer**: *"Euclidean distance assumes a flat Cartesian plane, which causes severe distortion over geographic coordinates. Haversine accounts for the Earth's spherical curvature ($R = 6,371\text{ km}$), providing meter-level geofence accuracy."*

---

### 🔄 Microservice 4: Event Adapter (Owner: Member 2)

* **Architecture**: Kafka consumer/normalizer, UUID event tagging, milestone enrichment (`bus-gps-normalized`), and dynamic HPA.
* **Rubric Mapping**: Task (c) & (d) — Horizontal Pod Autoscaling (HPA) & GitOps Decoupling.

#### 💻 Commands to Run:
```bash
# 1. Show the live HPA autoscaling engine attached to Event Adapter:
kubectl get hpa event-adapter-hpa -n transit-system

# 2. Inspect the HPA scaling policies (50% CPU target, 2 to 6 replicas):
kubectl describe hpa event-adapter-hpa -n transit-system | head -n 14

# 3. Check Event Adapter health & normalization counter:
curl -s http://localhost:8004/health | jq .
```

#### 🗣️ What to Say Out Loud to the Professor:
> *"Microservice 4 acts as an event-driven decoupling boundary. It runs as a Kafka consumer on topic `bus-gps-raw`, parses each raw coordinate, attaches a unique event UUID, enriches the coordinate with the next upcoming transit stop, and emits normalized events to `bus-gps-normalized`. Because vehicular traffic spikes heavily during peak morning and evening hours, we attached a Kubernetes Horizontal Pod Autoscaler targeting 50% CPU utilization, dynamically scaling this deployment from 2 to 6 replicas."*

#### 🎯 Likely Follow-Up Question & Knockout Answer:
* **Prof**: *"How does the HPA know when to scale?"*
* **Answer**: *"The Kubernetes Metrics Server queries cAdvisor every 15 seconds. When average pod CPU utilization exceeds the 50% threshold, the HPA controller calculates $\lceil \text{currentReplicas} \times (\text{currentCPU} / 50\%) \rceil$ and immediately instructs the ReplicaSet to spawn additional pods."*

---

### ⚡ Microservice 5: Real-Time Stream Processor (Owner: Member 3)

* **Architecture**: Apache Flink 1.17 stateful streaming engine, 60s tumbling event-time windows, 10s watermarks, and late side-output.
* **Rubric Mapping**: Task (e) — Stream Processing Architecture & Windowing Analytics.

#### 💻 Commands to Run:
```bash
# 1. Show Dataproc stream processing cluster configuration in GCP:
gcloud dataproc clusters list --region=us-central1 --project=transit-s11-bits-12730

# 2. Query live countdown arrival estimates computed by the stream engine:
curl -s http://8.233.33.106/api/v1/analytics/arrivals/STOP-001 | jq .

# 3. Execute stream processor test suite verifying windows & watermarks:
python3 services/05-stream-processor/test_stream_processor.py
```

#### 🗣️ What to Say Out Loud to the Professor:
> *"Microservice 5 is our stateful streaming analytics engine built on Apache Flink 1.17 running on Google Cloud Dataproc. It processes live telemetry in 60-second tumbling event-time windows. Because buses travel through cellular dead zones, telemetry packets can arrive late. Flink handles this using 10-second bounded out-of-orderness watermarks, and routes excessively late events to a side-output dead-letter queue while producing real-time countdown arrival estimates."*

#### 🎯 Likely Follow-Up Question & Knockout Answer:
* **Prof**: *"What is the difference between Processing Time and Event Time?"*
* **Answer**: *"Processing time is the clock time of the server running the Flink job, which fluctuates with network lag. Event time is the actual timestamp recorded by the bus GPS sensor at the instant of capture. Using Event Time with watermarks guarantees deterministic calculations even if packets arrive out of order."*

---

### 👥 Microservice 6: Passenger Demand Service (Owner: Member 3)

* **Architecture**: Smartcard tap ingestion, station crowd density index (LOW/MOD/HIGH/SURGE), and Google Cloud Firestore (NoSQL).
* **Rubric Mapping**: Task (f) — NoSQL Document Database Integration & High-Concurrency Write Engine.

#### 💻 Commands to Run:
```bash
# 1. Verify Google Cloud Firestore NoSQL database in GCP:
gcloud firestore databases list --project=transit-s11-bits-12730

# 2. Trigger a live passenger crowd surge at BITS Clock Tower (145 passengers):
curl -s -X POST http://8.233.33.106/api/v1/analytics/simulate-crowd \
  -H "Content-Type: application/json" \
  -d '{"stop_id": "STOP-002", "passenger_count": 145}' | jq .

# 3. Query the updated station crowd index from Firestore:
curl -s http://8.233.33.106/api/v1/analytics/stops | jq '.[] | select(.stop_id=="STOP-002")'
```

#### 🗣️ What to Say Out Loud to the Professor:
> *"Microservice 6 monitors real-time station congestion by ingesting smartcard taps and optical queue sensor counts. We chose Google Cloud Firestore NoSQL (Storage Product 2) for this microservice. Station tap counts undergo rapid, high-concurrency increments that would bottleneck a relational database. Firestore allows sub-10ms atomic document updates and automatically categorizes station crowd pressure into LOW, MODERATE, HIGH, and SURGE tiers."*

#### 🎯 Likely Follow-Up Question & Knockout Answer:
* **Prof**: *"Why NoSQL here instead of PostgreSQL like Microservice 1?"*
* **Answer**: *"Passenger taps are high-frequency event counters that don't need multi-table joins or relational constraints. Firestore provides horizontally scalable document storage with native real-time subscriptions, making it ideal for high-throughput sensor telemetry."*

---

### 🚨 Microservice 7: Delay Alert Service (Owner: Member 4)

* **Architecture**: Serverless Google Cloud Functions Gen2, Cloud Pub/Sub event triggers, and automated incident broadcasting.
* **Rubric Mapping**: Task (b / Serverless) — Serverless Function Computing & Event-Driven Notification.

#### 💻 Commands to Run:
```bash
# 1. Show Serverless Cloud Functions active in GCP:
gcloud functions list --regions=us-central1 --project=transit-s11-bits-12730

# 2. Simulate a traffic bottleneck & broadcast alert to commuters:
curl -s -X POST http://8.233.33.106/api/v1/analytics/trigger-delay \
  -H "Content-Type: application/json" \
  -d '{"bus_id": "BUS-101", "delay_minutes": 8.5, "reason": "Traffic bottleneck near Library Circle"}' | jq .

# 3. View the broadcasted alert in the active public feed:
curl -s http://8.233.33.106/api/v1/analytics/delays | jq .
```

#### 🗣️ What to Say Out Loud to the Professor:
> *"Microservice 7 satisfies our Serverless requirement using Google Cloud Functions Gen2. It operates purely event-driven: whenever downstream streaming calculations reveal that a bus is delayed beyond our 300-second (5-minute) threshold, a message publishes to Cloud Pub/Sub, which triggers this Cloud Function. The function generates a high-severity alert payload, writes it to Firestore, and pushes it to commuter displays. Because it is serverless, it consumes zero idle CPU and scales to zero when traffic is normal."*

#### 🎯 Likely Follow-Up Question & Knockout Answer:
* **Prof**: *"What are the cost and scaling advantages of Cloud Functions over running another container on GKE?"*
* **Answer**: *"Delay incidents are sporadic. A Kubernetes pod consumes CPU/memory allocations 24/7 even when there are no delays. Cloud Functions scale strictly to zero, charging only for the exact milliseconds of compute used when an incident actually occurs."*

---

### 🖥️ Microservice 8: Transport Analytics & Web Dashboard (Owner: Member 4)

* **Architecture**: Public web platform, live Leaflet map animation, countdown arrival board, Prometheus metrics scraping, and bus dispatching.
* **Rubric Mapping**: Task (g) & (h) — Public Web Application, Commuter UX & Cloud Observability.

#### 💻 Commands to Run:
```bash
# 1. Check live fleet KPIs (active buses, average speed):
curl -s http://8.233.33.106/api/v1/analytics/live-feed | grep -o '"kpis":{[^}]*}'

# 2. Scrape live Prometheus metrics:
curl -s http://8.233.33.106/metrics | grep "transport_analytics" | head -n 8

# 3. Dynamically dispatch a new bus live into the fleet:
curl -s -X POST http://8.233.33.106/api/v1/analytics/dispatch-bus \
  -H "Content-Type: application/json" \
  -d '{"bus_id": "BUS-505", "route_id": "ROUTE-1"}' | jq .

# 4. Open the live interactive map in your browser:
# http://8.233.33.106/
```

#### 🗣️ What to Say Out Loud to the Professor:
> *"Microservice 8 is our public-facing commuter analytics platform and web dashboard (Public Web Service requirement), deployed on GKE behind our Google Cloud External Ingress IP at `8.233.33.106`. It aggregates live data from all other services, displaying an animated Leaflet transit map, arrival countdown boards, and fleet performance KPIs. It also exposes standard Prometheus `/metrics` for Kubernetes cluster monitoring and provides a dispatch endpoint allowing transit operators to dynamically inject new buses into the live fleet."*

#### 🎯 Likely Follow-Up Question & Knockout Answer:
* **Prof**: *"How do Prometheus metrics integrate with Kubernetes?"*
* **Answer**: *"Microservice 8 exposes standard Prometheus exposition format counters and gauges at `/metrics`. A Prometheus server scrapes this endpoint every 15 seconds to monitor request latency, error rates, and active bus counts, visualizing them on Grafana dashboards."*

---

## ⚡ Quick One-Command All-Microservices Runner

If the professor asks: *"Can you run an automated verification of all 8 microservices right now?"*

```bash
python3 scripts/demo_all_microservices.py
```
> **Output**: Executes all 8 test suites sequentially in under 0.5 seconds, outputting `[✓ MICROSERVICE 1..8 VERIFIED & OPERATIONAL]`.
