# Demonstration & Viva Runbook
## Domain S11: Public Transportation — Real-Time Bus Arrival Estimates
**Course**: CS/SS G527 Cloud Computing (I Semester 2025–2026)  
**Total Marks**: 60 Marks (48M Project Evaluation + 12M Individual Viva)  
**Target Platform**: Google Cloud Platform (GCP) — Zero-Cost Architecture  
**Declared Distributed Concept**: ZooKeeper System  

---

## 1. Quick Reference & System Summary

| Category | Value |
|---|---|
| **Domain** | S11: Public Transportation (Real-time bus arrival estimates) |
| **Concept** | ZooKeeper System (Active-Standby Leader, Dynamic Watchers, Ephemeral Registry) |
| **Cloud Provider** | Google Cloud Platform (GCP) — Region: `asia-south1` (Mumbai) |
| **Cluster** | Google Kubernetes Engine (GKE) Zonal Cluster ($0 management fee) |
| **Namespace** | `transit-system` |
| **Microservices** | 8 Microservices (All containerized, health-checked, metric-instrumented) |
| **GitOps** | ArgoCD Automated Sync (`prune: true`, `selfHeal: true`) |
| **Storage Products** | Cloud SQL (PostgreSQL), Cloud Firestore (NoSQL), Cloud Storage (GCS) |
| **Stream Engine** | Apache Flink 1.17 on Google Cloud Dataproc |
| **Serverless** | Google Cloud Functions Gen2 (Delay Alert Service) |
| **Public Dashboard** | Leaflet Interactive Map, Live Countdown Board (`http://<INGRESS_IP>/`) |

---

## 2. Pre-Demo Setup & Environment Verification

Before presenting to the evaluators, verify your local environment and GCP credentials:

```bash
# 1. Verify GCP project & authentication
gcloud auth list
gcloud config set project <YOUR_GCP_PROJECT_ID>

# 2. Get GKE Cluster Credentials
gcloud container clusters get-credentials gke-transit-s11-prod --zone asia-south1-a

# 3. Verify namespace and all pods are running
kubectl get namespaces
kubectl get pods -n transit-system -o wide

# 4. Verify ArgoCD GitOps Application is synced and healthy
kubectl get applications -n argocd
```

---

## 3. Step-by-Step Viva Demonstration Script (Covering All 60 Marks)

Follow these sequential steps during the viva presentation. Each step explicitly demonstrates compliance with a specific requirement.

---

### Step 1: Infrastructure as Code (Requirement a — 6M)
**Objective**: Prove 100% of infrastructure is declared via Terraform.

```bash
cd terraform/

# 1. Verify syntax and configuration validity
terraform validate

# 2. Show planned cloud resources
terraform plan
```
**Key Evaluator Takeaway**:
- Show modular architecture: `vpc`, `gke`, `cloud_sql`, `firestore`, `gcs`, `iam`, `dataproc`, `cloud_functions`.
- Point out zero-cost configurations (e.g., GKE zonal cluster with zero cluster management fee, GCS lifecycle rules, Firestore native mode).

---

### Step 2: GitOps Controller & Self-Healing (Requirement d — 6M)
**Objective**: Demonstrate automated continuous delivery via ArgoCD and self-healing drift correction without `kubectl apply`.

```bash
# 1. View ArgoCD Application status
kubectl get application transit-system-prod -n argocd -o yaml | grep -A 10 "syncPolicy"

# 2. Demonstrate Self-Healing Drift Correction:
# Manually tamper with the cluster by deleting a deployment pod or tampering with replicas:
kubectl scale deployment/gps-ingestion --replicas=1 -n transit-system

# 3. Watch ArgoCD detect out-of-sync state and revert replicas back to Git-defined state:
kubectl get deployment/gps-ingestion -n transit-system -w
```
**Expected Output**:
Within 5 to 10 seconds, ArgoCD detects drift, flags the application as `OutOfSync`, triggers automatic self-healing, and scales the deployment back to Git's configured baseline (2 replicas).

---

### Step 3: ZooKeeper Distributed Concept (Requirement f — 6M)
**Objective**: Demonstrate Active-Standby Leader Election, Dynamic Watchers, and Ephemeral Node Heartbeating.

Run the interactive ZooKeeper failover demonstration script:
```bash
python3 scripts/demo_zookeeper_failover.py
```

**What the Evaluator Sees on Screen**:
1. **Three candidate pods** join the ZooKeeper ensemble: `adapter-pod-1`, `adapter-pod-2`, `adapter-pod-3`.
2. ZooKeeper assigns sequential ephemeral znodes. Pod 1 acquires the active leader lock.
3. Pod 2 and Pod 3 register watchers on preceding znodes (avoiding the herd effect).
4. **Leader Crash Simulation**: `adapter-pod-1` session terminates.
5. ZooKeeper deletes the ephemeral node, triggers `NodeDeleted` watcher, and `adapter-pod-2` automatically assumes leadership within **420ms**.
6. **Dynamic Config Watcher**: An operator updates `/transit/config/operational` with new geofence radius (80m) and delay threshold (4.0m). All connected microservices immediately log hot-reload without restarting!

---

### Step 4: Multi-Protocol Communication (Requirement b — 6M)
**Objective**: Demonstrate synchronous gRPC, high-throughput REST, and asynchronous Kafka messaging.

#### 4.1 gRPC Fleet Validation (Port 50051):
```bash
# Run gRPC integration test
python3 services/common/test_part2_integration.py
```
- Tests `ValidateVehicle(bus_id="BUS-101")` returning license plate, capacity, and active route.
- Tests `GetRouteDetails(route_id="ROUTE-PILANI-01")` and nearest stop lookup via Haversine calculation.

#### 4.2 REST Telemetry Ingestion (Port 8002):
```bash
curl -X POST http://localhost:8002/api/v1/telemetry/gps \
  -H "Content-Type: application/json" \
  -d '{
    "bus_id": "BUS-101",
    "route_id": "ROUTE-PILANI-01",
    "latitude": 28.3638,
    "longitude": 75.5872,
    "speed_kmh": 32.5,
    "heading": 90.0,
    "timestamp": 1700000000
  }'
```
**Expected Output**: `{"status": "ACCEPTED", "bus_id": "BUS-101", "partition": 0}`

#### 4.3 Kafka Topic Verification:
```bash
# Verify raw telemetry published to Kafka
python3 services/common/test_part4_pipeline.py
```

---

### Step 5: Three Distinct Cloud Storage Tiers (Requirement g — 6M)
**Objective**: Inspect the 3 distinct storage products in GCP.

#### Tier 1: Cloud SQL (PostgreSQL):
```bash
# Connect to Cloud SQL and verify relational schema
gcloud sql connect cloudsql-transit-s11-prod --user=transit_admin --database=transit_db

# Inside psql:
SELECT vehicle_id, license_plate, assigned_route_id, operational_status FROM vehicles;
SELECT route_id, route_short_name, total_distance_km FROM routes;
SELECT * FROM route_stops WHERE route_id = 'ROUTE-PILANI-01';
```

#### Tier 2: Cloud Firestore (NoSQL):
```bash
# Inspect real-time arrival estimates and delay alerts in Firestore
python3 -c "
from services.common.firestore.firestore_client import TransitFirestoreClient
client = TransitFirestoreClient()
docs = client.collection('realtime_bus_estimates').stream()
for d in docs:
    print(d.id, d.to_dict())
"
```

#### Tier 3: Google Cloud Storage (Object Store):
```bash
# List historical parquet archives and incident blobs
gsutil ls -lh gs://transit-s11-historical-archives/
gsutil ls -lh gs://transit-s11-delay-incidents/
```

---

### Step 6: Stream Processing with Apache Flink (Requirement e — 6M)
**Objective**: Demonstrate 1-minute tumbling window aggregation, watermarks, and ETA calculation.

```bash
# Run the Flink streaming engine verification test
python3 services/05-stream-processor/test_stream_processor.py
```
**Key Highlights for Evaluator**:
- Demonstrates `BoundedOutOfOrderness` watermark handling (out-of-order GPS coordinates within 10s window are properly processed).
- Calculates average speed from coordinate delta and updates real-time bus arrivals in Firestore.

---

### Step 7: Serverless Cloud Function (Requirement b — 6M)
**Objective**: Demonstrate event-driven delay alert triggering and incident report archival.

```bash
# Run serverless function test suite
python3 services/07-delay-alert-function/test_delay_alert_function.py
```
**What Happens**:
- An alert event with `delay_minutes = 7.5` (> 5 min threshold) triggers the Cloud Function.
- Function writes a high-severity alert to Firestore `delay_alerts` collection.
- Function generates an immutable JSON incident report and uploads it to GCS bucket `gs://transit-s11-delay-incidents/`.
- Buses with `delay_minutes < 5.0` are safely ignored (no false alerts).

---

### Step 8: Autoscaling (HPA) & k6 Load Testing (Requirement c — 6M)
**Objective**: Show automatic scaling of critical microservices (`gps-ingestion` and `event-adapter`) under sustained load.

```bash
# 1. View HPA configuration in Kubernetes
kubectl get hpa -n transit-system

# 2. Run the HPA simulation test suite
python3 load-testing/test_hpa_simulation.py

# 3. For live cluster load test with k6:
./load-testing/run_load_test.sh
```
**Evaluator Observation**:
- k6 ramps up to 800 Virtual Users (VUs) sending 500+ requests/second.
- Pod CPU utilization crosses the 60% threshold.
- HPA scales `gps-ingestion` replicas from 2 to 7 pods.
- Replicas scale down gracefully following the 300s stabilization window once load ceases.

---

### Step 9: Public Web Service & Live Map Dashboard (Requirement: Public Service)
**Objective**: Present the interactive web dashboard accessible over public HTTP/HTTPS.

1. Open a browser and navigate to:
   ```
   http://<INGRESS_PUBLIC_IP>/
   ```
   (Or run locally: `python3 services/08-transport-analytics/main.py` and open `http://localhost:8080/`)

2. **Features to Demonstrate to Evaluators**:
   - **Interactive Leaflet Map**: Pan and zoom around the BITS Pilani campus area.
   - **Live Transit Buses**: Blue bus markers displaying current speed, route ID, and next stop.
   - **Transit Stops & Geofences**: Red stop markers surrounded by light blue geofence arrival radii (60m–90m).
   - **Live Arrivals Countdown Board**: Real-time arrival minutes countdown with `ON_TIME` (green) and `DELAYED` (red) indicators.
   - **Delay Alert Banners**: Highlighted warning banners for buses delayed > 5 minutes.
   - **Stop Crowd Densities**: Stop capacity indicators (`LOW`, `HIGH`).
   - **Interactive Swagger Docs**: Open `http://<INGRESS_PUBLIC_IP>:8008/docs` for OpenAPI explorer.

---

### Step 10: Observability Stack (Requirement h — 6M)
**Objective**: Demonstrate Prometheus metrics scraping, Loki log streams, and Grafana dashboards.

```bash
# 1. Run observability verification
python3 scripts/verify_observability_stack.py

# 2. Forward Grafana port to inspect live dashboard:
kubectl port-forward svc/grafana-service 3000:3000 -n transit-system
```
- Open `http://localhost:3000` (User: `admin`, Password: `transit2026bits`).
- Navigate to dashboard: **"S11: Public Transit Operations & Telemetry Dashboard"**.
- Point out the 5 pre-provisioned panels:
  1. *Ingestion Throughput (RPS)*
  2. *p95 API Latencies by Service*
  3. *HPA Dynamic Replica Scaling*
  4. *Active Tracked Fleet & Average Velocity*
  5. *Active Transit Delay Incidents*

---

## 4. Individual Viva Preparation Questions & Answers

Each student will be evaluated individually (12 Marks). Here are specific viva questions and answers tailored to each member's tasks.

---

### Member 1: IaC (Task a), Communication (Task b), Services 1 & 2
- **Q1: Why did you choose gRPC over REST for communication between GPS Ingestion (S2) and Vehicle Registry (S1)?**
  - **A**: GPS Ingestion processes high-frequency coordinate packets (thousands per second). REST/JSON introduces significant serialization overhead and HTTP header bloat. gRPC uses Protocol Buffers (binary serialization) and HTTP/2 multiplexing, reducing payload size by ~60% and latency by ~4x, allowing GPS Ingestion to validate vehicle active status with sub-millisecond overhead.
- **Q2: How does Terraform enforce immutability and state consistency in GCP?**
  - **A**: Terraform stores the desired state in declarative HCL files. During `terraform apply`, it compares real-world GCP resource configurations with `terraform.tfstate` (stored remotely in a GCS bucket with state locking). If a resource has drifted or is missing, Terraform generates a deterministic execution graph to reconcile it without side effects.
- **Q3: What happens if Cloud SQL PostgreSQL becomes unavailable?**
  - **A**: Vehicle Registry implements connection pooling with retry backoff and an in-memory LRU read cache for active vehicle metadata. If the database experiences a momentary failover, cached vehicle statuses are used to validate incoming GPS frames, preventing ingestion pipeline failure.

---

### Member 2: Kubernetes & HPA (Task c), GitOps (Task d), Services 3 & 4
- **Q4: Why is direct `kubectl apply` prohibited in your GitOps pipeline?**
  - **A**: Manual `kubectl apply` introduces configuration drift, bypasses peer code reviews, eliminates audit trails, and causes "works on my machine" discrepancies. In our GitOps setup, Git is the single source of truth. ArgoCD continuously reconciles the cluster state against Git. Any manual changes made via `kubectl` are automatically detected and reverted by ArgoCD's `selfHeal: true` policy.
- **Q5: How does your HPA algorithm prevent thrashing (rapid scaling up and down)?**
  - **A**: We configured Kubernetes HPA `behavior` with stabilization windows. Scale-up is fast (15s stabilization) to quickly handle traffic spikes, while scale-down has a conservative 300-second (5-minute) stabilization window. This prevents flapping when transit traffic fluctuates.
- **Q6: In Service 4 (Event Adapter), how do you calculate the nearest stop?**
  - **A**: We use the Haversine formula implemented in `geometry.py`. It computes the great-circle distance between the bus coordinate $(\text{lat}_1, \text{lon}_1)$ and all stop coordinates on the assigned route, identifying the closest stop within the stop's geofence radius.

---

### Member 3: Stream Processing (Task e), ZooKeeper (Task f), Services 5 & 6
- **Q7: Why use Apache Flink over Apache Spark Streaming for real-time bus arrivals?**
  - **A**: Spark Streaming operates on micro-batches (e.g., 500ms to 2s intervals), which adds artificial latency to coordinate processing. Apache Flink is a true event-driven streaming engine with native event-time processing, low-latency stateful windowing, and fine-grained watermarks. Flink allows us to handle out-of-order GPS arrivals accurately and compute 1-minute tumbling window speeds without buffering delay.
- **Q8: How does your ZooKeeper leader election avoid the "herd effect"?**
  - **A**: Rather than having all candidate pods watch a single master znode, candidates create sequential ephemeral znodes (e.g., `candidate-0000000001`, `candidate-0000000002`). Each candidate only watches the znode with the immediate preceding sequence number. When the leader dies, only the single next candidate is notified, preventing a thundering herd storm across the ZooKeeper ensemble.
- **Q9: How do you handle out-of-order GPS coordinates in Flink?**
  - **A**: We configure a `BoundedOutOfOrderness` watermark generator with a 10-second bounded delay. Flink buffers events within the watermark window. If a packet arrives with timestamp older than `current_watermark - 10s`, it is considered late and redirected to a side output for batch auditing rather than corrupting the live speed calculation.

---

### Member 4: Storage Tiers (Task g), Observability (Task h), Services 7 & 8
- **Q10: Why did you use three distinct storage products instead of putting everything into Cloud SQL?**
  - **A**: Storage workloads in transit systems have divergent access patterns:
    1. *Cloud SQL (RDBMS)*: Ideal for relational, ACID-critical fleet registration and route stop geometries.
    2. *Firestore (NoSQL)*: Ideal for millisecond, high-concurrency public queries (hundreds of commuters looking up ETAs simultaneously) without relational query locks.
    3. *GCS (Object Storage)*: Millions of high-frequency GPS raw logs and incident blobs stored in RDBMS would explode storage costs. GCS stores Snappy-compressed Parquet files with Coldline lifecycle rules at a fraction of the cost.
- **Q11: Why is Service 7 (Delay Alert) implemented as a Cloud Function instead of a continuous container?**
  - **A**: Delay alerts are event-driven and sporadic. Buses usually run on schedule, so a dedicated container would idle 90% of the day. Cloud Functions scale to zero, costing ₹0 when idle, and scale up instantly to 1,000 parallel instances during a sudden city-wide transit disruption.
- **Q12: How does your Prometheus scraping setup distinguish between services?**
  - **A**: Prometheus scrapes each Kubernetes service via DNS targets on dedicated metric ports (e.g., `vehicle-registry:8001/metrics`, `gps-ingestion:8002/metrics`). We attach uniform labels (`service`, `endpoint`, `environment`) to every metric counter and gauge using our shared metrics utility (`services/common/metrics.py`), enabling granular filtering and alerts in Grafana.

---

## 5. Master Regression Test Script

To verify all components end-to-end with a single command before the presentation:

```bash
# Run the complete test suite across all 8 microservices, ZooKeeper, Flink, HPA, and GitOps
python3 services/01-vehicle-registry/test_vehicle_registry.py && \
python3 services/03-route-service/test_route_service.py && \
python3 services/common/test_part2_integration.py && \
python3 services/common/zookeeper/test_zookeeper_coordination.py && \
python3 services/02-gps-ingestion/test_gps_ingestion.py && \
python3 services/04-event-adapter/test_event_adapter.py && \
python3 services/common/test_part4_pipeline.py && \
python3 services/05-stream-processor/test_stream_processor.py && \
python3 services/07-delay-alert-function/test_delay_alert_function.py && \
python3 services/06-passenger-demand/test_passenger_demand.py && \
python3 load-testing/test_hpa_simulation.py && \
python3 scripts/verify_gitops_pipeline.py && \
python3 services/08-transport-analytics/test_transport_analytics.py && \
python3 scripts/verify_observability_stack.py
```
**Expected Outcome**: **ALL 14 TEST SUITES PASS WITH ZERO ERRORS.**
