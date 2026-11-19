# Complete System Architecture, Viva Guide & Member-by-Member Master Manual
## S11: Real-Time Smart Public Transportation Tracking & Arrival Estimation System
**Course**: CS/SS G527 Cloud Computing | BITS Pilani  
**Total Marks**: 60 Marks (48M Project Evaluation + 12M Individual Viva)  
**Target Platform**: Google Cloud Platform (GCP) — Zero-Cost Architecture  
**Public Service**: [http://34.132.139.56](http://34.132.139.56)  
**GitHub Repository**: [https://github.com/ajay-sehrawat/Public-Transit-Live-Intelligence-](https://github.com/ajay-sehrawat/Public-Transit-Live-Intelligence-)

---

# Table of Contents
1. [Executive Overview: What Are We Doing & Why?](#1-executive-overview-what-are-we-doing--why)
2. [End-to-End System Architecture & Data Flow](#2-end-to-end-system-architecture--data-flow)
3. [Quick-Start Runbook: How to Wake Up & Test the System](#3-quick-start-runbook-how-to-wake-up--test-the-system)
4. [Member 1 Deep-Dive: IaC, Communication & Fleet Ingestion](#4-member-1-deep-dive-iac-communication--fleet-ingestion)
5. [Member 2 Deep-Dive: Kubernetes, HPA Autoscaling & ArgoCD GitOps](#5-member-2-deep-dive-kubernetes-hpa-autoscaling--argocd-gitops)
6. [Member 3 Deep-Dive: Flink Stream Processing & ZooKeeper Distributed Concept](#6-member-3-deep-dive-flink-stream-processing--zookeeper-distributed-concept)
7. [Member 4 Deep-Dive: 3 Storage Tiers, Serverless Function & Observability](#7-member-4-deep-dive-3-storage-tiers-serverless-function--observability)
8. [Common Evaluator Questions & Trap Answers](#8-common-evaluator-questions--trap-answers)
9. [Comprehensive Cloud Glossary](#9-comprehensive-cloud-glossary)

---

# 1. Executive Overview: What Are We Doing & Why?

### The Real-World Problem
In public transportation, commuters wait at bus stops without knowing:
- Where the bus currently is.
- When it will actually arrive (Estimated Time of Arrival or ETA).
- Whether the bus is packed with passengers or empty.
- If the bus is caught in unexpected traffic or delayed.

A naive single-server architecture crashes during rush hour when thousands of commuters query the map and hundreds of buses transmit high-frequency GPS telemetry every 1–5 seconds.

### What We Built
We architected and deployed an **enterprise-grade, distributed, cloud-native transit platform on Google Cloud Platform (GCP)**. It provides:
1. **Real-time Bus Tracking**: Ingests GPS telemetry (latitude, longitude, speed, timestamp) from vehicle fleets.
2. **Dynamic Arrival Estimation (ETA)**: Calculates arrival times at subsequent stops using Haversine distance, historical velocity, and real-time congestion factors.
3. **Crowd Density Ingestion**: Ingests commuter smartcard tap-ins/tap-outs at bus stops to classify passenger crowd pressure (`LOW`, `MODERATE`, `HIGH`).
4. **Live Interactive Commuter Web Dashboard**: An interactive map rendered with Leaflet.js and a live countdown arrival board accessible via a public IP: **`http://34.132.139.56`**.
5. **Fault-Tolerant Distributed Coordination**: Coordinates active-standby analytics pipelines using a 3-node **Apache ZooKeeper** ensemble.
6. **Automated Continuous Delivery & Self-Healing**: Managed via **ArgoCD GitOps** tracking our GitHub repository.
7. **End-to-End Observability**: Real-time monitoring via Prometheus metrics, Grafana visualization dashboards, and centralized Loki log pipelines.

### Key Deployment Cheat Sheet
| Component | Endpoint / Identification | Credentials / Access |
|---|---|---|
| **Public Web Service** | `http://34.132.139.56` (Port 80 / 8008) | Open Public Ingress |
| **OpenAPI / Swagger Docs** | `http://34.132.139.56/docs` | Interactive API documentation |
| **GCP Project ID** | `transit-s11-bits-12730` | Authenticated as student account |
| **GKE Kubernetes Cluster** | `transit-gke-cluster` (Zone: `us-central1-a`) | Namespace: `transit-system` |
| **Cloud SQL PostgreSQL** | Host: `34.46.78.203:5432`, DB: `transit_db` | User: `transit_admin` / `TransitSecurePass2026!` |
| **Cloud Firestore (NoSQL)** | `projects/transit-s11-bits-12730/databases/(default)` | Native Mode (Document DB) |
| **Cloud Storage (GCS)** | `gs://transit-telemetry-raw-transit-s11-bits-12730-1da97a97/` | Coldline archive bucket |
| **Cloud Function Gen2** | `transit-delay-alert` (Region: `us-central1`) | Trigger: Pub/Sub `bus-delay-alerts` |
| **ZooKeeper Cluster** | `zk-0`, `zk-1`, `zk-2` (Headless Service: `zk-hs:2181`) | 3-node fault-tolerant ensemble |
| **Grafana Dashboard** | Port-forward `svc/grafana-service 3000:3000` | User: `admin` / `transit2026bits` |

---

# 2. End-to-End System Architecture & Data Flow

### The Life of a GPS Ping (Step-by-Step Data Journey)
Here is exactly how data moves from a bus driving down the street to a commuter's smartphone:

```
[ Transit Bus GPS Sensor ]
          │  (HTTP POST JSON payload every 1-3 sec)
          ▼
┌──────────────────────────────────────────────────────────────┐
│ Microservice 2: GPS Ingestion Service (Port 8002)           │
│ - Validates payload schema & GPS boundary constraints        │
│ - Rate limits incoming device connections                    │
│ - Backed by Horizontal Pod Autoscaler (HPA: 2 to 8 pods)    │
└────────────────────────┬─────────────────────────────────────┘
                         │ (Internal Publish: Pub/Sub or Kafka)
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ Microservice 4: Event Adapter (Port 8004)                   │
│ - Validates vehicle ID with Service 1 (Vehicle Registry)     │
│   via high-speed internal gRPC (port 50051)                  │
│ - Computes Haversine distance, instant delta-velocity        │
│ - Normalizes events into canonical JSON schemas              │
└────────────┬──────────────────────────────┬──────────────────┘
             │ (Batch Archival)             │ (Stream Analytics)
             ▼                              ▼
┌───────────────────────────┐  ┌────────────────────────────────────────────────┐
│ Storage Product 3:        │  │ Microservice 5: Stream Processor (Flink)       │
│ Google Cloud Storage (GCS)│  │ - 60-second Tumbling Windows                   │
│ Raw Telemetry Cold Storage│  │ - Event-Time Watermarking (10s late tolerance) │
└───────────────────────────┘  │ - Calculates average route congestion          │
                               └────────────────────┬───────────────────────────┘
                                                    │
                                                    ▼
                               ┌────────────────────────────────────────────────┐
                               │ Microservice 8: Transport Analytics (Port 8008)│
                               │ - Master Leader elected via ZooKeeper (/leader)│
                               │ - Computes dynamic ETAs for each bus stop      │
                               │ - Writes hot state to Cloud Firestore (NoSQL)  │
                               └────────────────────┬───────────────────────────┘
                                                    │
                                                    ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│ Public Web Layer & Commuter Frontend (http://34.132.139.56)                             │
│ - External Network Load Balancer routes port 80 traffic to Service 8                     │
│ - Leaflet.js renders moving bus markers on live map                                      │
│ - Arrival countdown table updates ETAs every 3 seconds                                   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

### Why Microservices Instead of a Monolith?
1. **Independent Scalability**: During peak rush hour, the `gps-ingestion` service handles thousands of writes per second, while `vehicle-registry` only reads static vehicle specs once in a while. In a microservices architecture, we scale `gps-ingestion` up to 8 pods with HPA without wasting CPU on the registry service.
2. **Fault Isolation**: If the `passenger-demand` service experiences a spike and crashes, the core bus tracking and arrival estimation continue running without interruption.
3. **Polyglot Storage Alignment**: Microservices allow each service to use the optimal database (Cloud SQL for relational fleet specs, Firestore for low-latency live map queries, and GCS for cold archive files).

---

# 3. Quick-Start Runbook: How to Wake Up & Test the System

If the cluster was placed in "Sleep Mode" overnight (worker nodes resized to 0 to save student credits), follow these simple steps in Google Cloud Shell to wake it up and verify health.

### Step 1: Wake Up Cloud SQL and GKE Worker Nodes
Run in Google Cloud Shell:
```bash
# 1. Set active project
gcloud config set project transit-s11-bits-12730

# 2. Turn Cloud SQL PostgreSQL instance back on
gcloud sql instances patch transit-postgres-db --activation-policy ALWAYS --quiet

# 3. Scale GKE worker nodes back up to 3 nodes
gcloud container clusters resize transit-gke-cluster \
  --node-pool transit-gke-cluster-node-pool \
  --zone us-central1-a \
  --num-nodes 3 --quiet

# 4. Restore normal HPA node autoscaling boundaries
gcloud container clusters update transit-gke-cluster \
  --node-pool transit-gke-cluster-node-pool \
  --zone us-central1-a \
  --enable-autoscaling --min-nodes 2 --max-nodes 5 --quiet
```
*Wait approximately 90–120 seconds for the VMs to initialize.*

### Step 2: Verify All Pods Are Running
```bash
kubectl get pods -n transit-system
```
**Expected Output**:
You should see all 6 microservice deployments, 3 ZooKeeper pods (`zk-0`, `zk-1`, `zk-2`), and observability pods (`prometheus`, `grafana`, `loki`, `promtail`) in `Running` status.

### Step 3: Open the Live Public Dashboard
Open your browser and navigate to:
**`http://34.132.139.56`**

**What to Test in the Browser UI**:
1. **Leaflet Map**: You will see animated bus markers (Route 1A, Route 2B, Route 3C) traversing the routes in real-time.
2. **Arrival Estimates Board**: Notice the live countdown timers for stops like *Central Station*, *North Gate*, and *Tech Park*.
3. **Dispatch Simulator**: Click the green **"Simulate Bus Ingestion"** or **"Dispatch Extra Bus"** button on the page. Watch the live fleet count increase and new telemetry markers appear immediately!

---

# 4. Member 1 Deep-Dive: IaC, Communication & Fleet Ingestion

| Field | Detail |
|---|---|
| **Assigned Member** | Member 1 |
| **Assigned Tasks** | **Task (a)**: Infrastructure as Code (Terraform) <br> **Task (b)**: Cloud-Native Communication Mechanisms |
| **Assigned Microservices** | **Microservice 1**: Vehicle Registry (`services/01-vehicle-registry`) <br> **Microservice 2**: GPS Ingestion Service (`services/02-gps-ingestion`) |
| **Code Ownership** | `terraform/` (all modules), `services/01-vehicle-registry/`, `services/02-gps-ingestion/`, `services/common/protos/` |

---

### What Did Member 1 Build? (Plain English Explanation)
Member 1 built the **foundation of the entire cloud platform** and the **front door for telemetry data**:
1. **Infrastructure as Code (IaC)**: Instead of manually clicking buttons in the Google Cloud Console (which is error-prone and unrepeatable), Member 1 wrote declarative code using **Terraform**. This single codebase provisions the Virtual Private Cloud (VPC), GKE Kubernetes cluster, Cloud SQL database, Firestore, GCS buckets, and IAM roles in under 10 minutes.
2. **Cloud-Native Communication (REST, gRPC, Pub/Sub)**: Implemented multiple protocols for efficient communication:
   - **REST (HTTP/JSON)**: Used for public client interactions and mobile device reporting.
   - **gRPC (HTTP/2 + Protocol Buffers)**: Used for internal service-to-service communication between Microservice 4 and Microservice 1, achieving microsecond-level latency and binary serialization.
   - **Pub/Sub Messaging**: Used for decoupled, event-driven message distribution.
3. **Microservice 1 (Vehicle Registry)**: The master database of all transit vehicles (buses). It stores bus IDs, models (e.g. *Tata Starbus EV*, *Volvo 9400*), seating capacities, and operational statuses in Cloud SQL PostgreSQL, exposing both REST and gRPC endpoints.
4. **Microservice 2 (GPS Ingestion Service)**: The high-throughput gateway receiving telemetry from buses on the road. It validates coordinates, checks boundaries, rate-limits abusive devices, and forwards events down the pipeline.

---

### Key Concepts Explained from Scratch

#### 1. What is Terraform and Infrastructure as Code (IaC)?
- **Analogy**: Imagine building a house. Instead of telling workers by hand where to put every single brick, you hand them an exact architectural blueprint. The blueprint is Terraform.
- **Why it matters**: In cloud engineering, if an evaluator asks *"Can you deploy your architecture in another region like Mumbai (`asia-south1`)?"*, without Terraform you would spend hours clicking through GCP menus. With Terraform, you change `region = "asia-south1"` in `terraform.tfvars` and run `terraform apply`. Terraform automatically builds the entire cloud infrastructure.
- **State File (`terraform.tfstate`)**: A file where Terraform records every cloud resource it created, mapping your code to real GCP cloud resource IDs.

#### 2. What is gRPC and why is it better than REST for internal services?
- **REST**: Transmits plain text JSON over HTTP/1.1. It is human-readable, but has high CPU overhead due to JSON parsing and string manipulation.
- **gRPC**: Developed by Google. It transmits compressed binary data using **Protocol Buffers (`.proto`)** over **HTTP/2**.
  - **Multiplexing**: Multiple requests can fly through a single TCP connection at the same time.
  - **Speed**: Serialization is 7x–10x faster than JSON.
  - **Strict Contracts**: The `.proto` file strictly defines the schema. Both client and server must comply, preventing runtime data bugs.

---

### Member 1: Step-by-Step Viva Demonstration Commands

Run these commands in Cloud Shell to demonstrate your contribution to the evaluator:

```bash
# 1. Show Terraform code validation and resource planning (Task a)
cd ~/transit-cloud/terraform
terraform validate
terraform state list | head -n 12

# 2. Verify Cloud SQL fleet inventory managed by Microservice 1 (Task a & Microservice 1)
PGPASSWORD="TransitSecurePass2026!" psql -h 34.46.78.203 -U transit_admin -d transit_db \
  -c "SELECT bus_id, model, capacity, status FROM vehicles LIMIT 5;"

# 3. Test Microservice 1 REST health & API endpoint
curl -s http://34.132.139.56/api/v1/vehicles | jq .

# 4. Transmit live GPS telemetry into Microservice 2 (Task b & Microservice 2)
curl -X POST "http://34.132.139.56/api/v1/telemetry/gps" \
  -H "Content-Type: application/json" \
  -d '{
    "bus_id": "BUS-101",
    "route_id": "ROUTE-1",
    "latitude": 28.6139,
    "longitude": 77.2090,
    "speed_kmh": 38.5,
    "timestamp": 1794967200
  }' | jq .
```

---

### Member 1: Viva Questions & Prepared Answers

#### Q1: "Why did you use Terraform instead of Google Cloud Deployment Manager or gcloud scripts?"
> **Answer**: "Terraform is cloud-agnostic and declarative. Rather than executing imperative shell commands which fail on reruns, Terraform calculates the delta between the declared state and actual state via its dependency graph. It supports state locking, dry-run previews via `terraform plan`, and modular decomposition, which allowed us to cleanly isolate our VPC, GKE, and storage configurations."

#### Q2: "How does gRPC improve performance between Microservice 2/4 and Microservice 1?"
> **Answer**: "High-frequency GPS ingestion processes hundreds of coordinates per second. If we used REST/JSON for every vehicle registry lookup, we would suffer heavy JSON serialization/deserialization CPU penalties and TCP connection handshakes. gRPC uses HTTP/2 multiplexing over a single persistent TCP connection and serializes payloads into compact binary Protocol Buffers (`vehicle_service.proto`), reducing latency from ~35ms down to under 3ms."

#### Q3: "What happens if a bus sends malformed or impossible GPS coordinates to Service 2?"
> **Answer**: "Microservice 2 uses strict Pydantic models with validation boundaries: latitude must be between $-90.0$ and $+90.0$, longitude between $-180.0$ and $+180.0$, and speed cannot be negative. If an invalid packet arrives, the service immediately returns HTTP 422 Unprocessable Entity, increments the Prometheus error counter `transit_invalid_telemetry_total`, and discards the packet before it touches downstream queues."

---

# 5. Member 2 Deep-Dive: Kubernetes, HPA Autoscaling & ArgoCD GitOps

| Field | Detail |
|---|---|
| **Assigned Member** | Member 2 |
| **Assigned Tasks** | **Task (c)**: Managed Kubernetes (GKE), Horizontal Pod Autoscaling (HPA) & Load Testing <br> **Task (d)**: GitOps Controller (ArgoCD Continuous Delivery & Self-Healing) |
| **Assigned Microservices** | **Microservice 3**: Route Service (`services/03-route-service`) <br> **Microservice 4**: Event Adapter (`services/04-event-adapter`) |
| **Code Ownership** | `k8s/base/`, `k8s/hpa/`, `k8s/argocd/`, `load-testing/`, `services/03-route-service/`, `services/04-event-adapter/` |

---

### What Did Member 2 Build? (Plain English Explanation)
Member 2 built the **container orchestration engine, dynamic scaling behavior, and deployment automation**:
1. **Managed Kubernetes (GKE)**: Packaged all 8 microservices into Docker containers and defined their Kubernetes deployment manifests (deployments, cluster IP services, and ingress).
2. **Horizontal Pod Autoscaling (HPA)**: Configured automatic scaling rules. When traffic spikes (e.g. morning peak rush hour), Kubernetes monitors CPU utilization and automatically spawns additional pod replicas (from 2 up to 8 pods) to distribute the load, scaling back down when traffic subsides.
3. **Declarative GitOps with ArgoCD**: Set up ArgoCD in the cluster. Instead of a developer typing `kubectl apply` manually, Git is the single source of truth. Whenever code is pushed to our GitHub repository, ArgoCD automatically detects changes, reconciles the cluster, and corrects any manual drift (self-healing).
4. **Microservice 3 (Route Service)**: Stores and manages transit route geometries, bus stops, geographic waypoints, and distance matrices.
5. **Microservice 4 (Event Adapter)**: Listens to incoming raw telemetry events, invokes Service 1 over gRPC to validate the vehicle, computes delta speed and geographic displacement, and normalizes the data for stream processors.

---

### Key Concepts Explained from Scratch

#### 1. What is Kubernetes (GKE), and what is a Pod?
- **Pod**: The smallest deployable unit in Kubernetes. Think of a pod as a small box holding your running containerized application.
- **Deployment**: A manager that ensures a specific number of identical pods (e.g., 2 replicas) are always running. If a pod crashes, the Deployment immediately creates a replacement.
- **Service**: Gives a stable internal network address and DNS name (e.g. `gps-ingestion-service.transit-system.svc.cluster.local`) that load-balances requests across all pods of that deployment.

#### 2. How does the Horizontal Pod Autoscaler (HPA) work?
- The HPA controller queries the Kubernetes Metrics Server every 15 seconds for CPU and memory usage.
- **Formula**:
  $$\text{Desired Replicas} = \left\lceil \text{Current Replicas} \times \left( \frac{\text{Current Metric Value}}{\text{Target Metric Value}} \right) \right\rceil$$
- In our project, the CPU target is set to **50%**. If 2 pods are running at 80% CPU during a load spike:
  $$\text{Desired Replicas} = \left\lceil 2 \times \frac{80}{50} \right\rceil = \lceil 3.2 \rceil = 4 \text{ pods}$$
  Kubernetes immediately spins up 2 additional pods to absorb the load!

#### 3. What is GitOps and Self-Healing Drift Correction?
- **Traditional Ops**: A developer logs into the server and runs `kubectl scale` or edits a YAML file directly on the cluster. This causes "configuration drift" where no one knows what is actually running in production.
- **GitOps**: Your Git repository is the absolute truth. You only change files in Git.
- **Self-Healing**: If an attacker or engineer manually tampers with the cluster (e.g., running `kubectl scale deployment gps-ingestion --replicas=1`), ArgoCD detects that the live cluster differs from Git, flags an `OutOfSync` state, and **automatically forces the cluster back to Git's declared state (2 replicas)** within seconds!

---

### Member 2: Step-by-Step Viva Demonstration Commands

```bash
# 1. Inspect live HPAs and target deployments (Task c)
kubectl get hpa -n transit-system
kubectl get deployment gps-ingestion event-adapter -n transit-system

# 2. Run the automated HPA scaling simulation test suite (Task c)
python3 ~/transit-cloud/load-testing/test_hpa_simulation.py

# 3. Check registered ArgoCD GitOps application tracking GitHub (Task d)
kubectl get applications -n argocd
kubectl get application transit-system-production -n argocd -o yaml | grep -A 10 "syncPolicy"

# 4. Demonstrate Live GitOps Self-Healing (Tamper with cluster replicas):
kubectl scale deployment/gps-ingestion --replicas=1 -n transit-system
# Watch ArgoCD detect drift and self-heal back to 2 replicas:
kubectl get deployment gps-ingestion -n transit-system -w
# (Press Ctrl+C to exit watch once it reconciles)
```

---

### Member 2: Viva Questions & Prepared Answers

#### Q1: "How does the Horizontal Pod Autoscaler prevent 'flapping' (rapid scaling up and down)?"
> **Answer**: "Kubernetes HPA incorporates a stabilization window (configurable via `behavior.scaleDown.stabilizationWindowSeconds`, default 300 seconds). When a traffic burst subsides, HPA does not immediately kill pods; it evaluates the maximum algorithmically desired replica count over the preceding 5-minute window before gradually terminating pods to prevent thrashing."

#### Q2: "What is the difference between ArgoCD automated sync and manual sync?"
> **Answer**: "In manual sync, ArgoCD detects drift and marks the application `OutOfSync`, but waits for an engineer to trigger synchronization. In our production manifest (`application-root.yaml`), we enabled `syncPolicy.automated` with `prune: true` (removes resources deleted from Git) and `selfHeal: true` (overwrites any manual cluster modifications back to the Git commit hash)."

#### Q3: "What role does Microservice 4 (Event Adapter) play in preventing data corruption?"
> **Answer**: "Microservice 4 acts as an anti-corruption layer. Different bus hardware models transmit timestamps in varying formats (epoch milliseconds vs ISO-8601 strings) and raw speeds in miles-per-hour or knots. Event Adapter normalizes all telemetry into standard SI units (km/h, UTC epoch seconds, decimal degrees) before passing them downstream to Flink."

---

# 6. Member 3 Deep-Dive: Flink Stream Processing & ZooKeeper Distributed Concept

| Field | Detail |
|---|---|
| **Assigned Member** | Member 3 |
| **Assigned Tasks** | **Task (e)**: Real-Time Stream Processing (Apache Flink on Dataproc) <br> **Task (f)**: Domain Distributed Concept (ZooKeeper System) |
| **Assigned Microservices** | **Microservice 5**: Stream Processor (`services/05-stream-processor`) <br> **Microservice 6**: Passenger Demand Service (`services/06-passenger-demand`) |
| **Code Ownership** | `k8s/zookeeper/`, `services/05-stream-processor/`, `services/06-passenger-demand/`, `services/common/zookeeper/`, `scripts/demo_zookeeper_failover.py` |

---

### What Did Member 3 Build? (Plain English Explanation)
Member 3 built the **advanced real-time analytics engine and distributed coordination system**:
1. **Apache Flink Stream Processing**: Built a stateful stream processing application running 1-minute tumbling windows. It computes moving averages of vehicle speeds, calculates road segment congestion indices, and handles out-of-order GPS packets using event-time watermarking.
2. **Distributed System Concept: ZooKeeper 3-Node Ensemble**: Deployed an enterprise coordination cluster (`zk-0`, `zk-1`, `zk-2`) using a Kubernetes StatefulSet. Member 3 implemented:
   - **Active-Standby Leader Election**: Ensures only one master analytics instance writes ETAs to avoid split-brain write conflicts.
   - **Dynamic Path Watchers**: Automatically alerts standby instances the millisecond a leader fails.
   - **Ephemeral Node Heartbeats**: If a worker node crashes or loses network connectivity, ZooKeeper automatically deletes its ephemeral znode and triggers immediate failover.
3. **Microservice 5 (Stream Processor)**: The PyFlink core application that transforms streams of raw GPS coordinates into meaningful traffic congestion and ETA metrics.
4. **Microservice 6 (Passenger Demand Service)**: Ingests transit smartcard commuter tap-ins/tap-outs, tracks boarding counts at each stop, and computes crowd density indicators (`LOW`, `MODERATE`, `HIGH`) to warn passengers of overcrowded buses.

---

### Key Concepts Explained from Scratch

#### 1. What is Stream Processing vs Batch Processing?
- **Batch Processing**: You wait for all data to arrive (e.g. at the end of the day), load it into a big database, and run a query. This is useless for transit because a commuter needs to know *where the bus is right now*, not where it was yesterday.
- **Stream Processing (Apache Flink)**: Processes each data record **in-flight** with sub-second latency as it happens.
- **Tumbling Windows**: Groups incoming data into fixed, non-overlapping time buckets (e.g., 60-second windows: 10:00–10:01, 10:01–10:02) to calculate average velocity.

#### 2. What are Watermarks and Out-of-Order Events in Flink?
- In real life, buses drive through tunnels or areas with spotty cellular coverage. A GPS packet generated at 10:01:05 might get delayed over mobile networks and arrive at the cloud server at 10:01:30!
- **Watermark**: A timestamp marker that tells Flink: *"We have processed all events up to time $T$. Assume no more events older than $T$ will arrive."*
- **Bounded Out-of-Orderness**: We configure a **10-second bounded delay**. Flink holds the window open for 10 extra seconds to catch late cellular packets. If a packet arrives even later than 10 seconds, it is diverted to a **Side Output** for historical auditing without corrupting live arrival estimates!

#### 3. What is ZooKeeper, Quorum, and Leader Election?
- **Why do we need ZooKeeper?** If two analytics instances both think they are the leader and both write conflicting arrival predictions to Firestore, data becomes corrupted (the classic "Split-Brain" problem).
- **Quorum**: In a 3-node cluster, a majority of nodes must agree on all state updates:
  $$\text{Quorum} = \left\lfloor \frac{N}{2} \right\rfloor + 1 = \left\lfloor \frac{3}{2} \right\rfloor + 1 = 2 \text{ nodes}$$
  Even if one node (`zk-0`) dies, the remaining two nodes (`zk-1`, `zk-2`) maintain quorum and keep the system 100% operational.
- **Ephemeral Sequential Znodes**: To elect a leader, candidates create a temporary znode like `/transit/leader/node-00000001`. The candidate with the lowest sequence number becomes the **Active Leader**. All other candidates place a **Watcher** on the node just ahead of them. If the leader crashes, its ephemeral node vanishes, ZooKeeper notifies the watcher, and the standby instance becomes the new Leader in under 200 milliseconds!

---

### Member 3: Step-by-Step Viva Demonstration Commands

```bash
# 1. Verify ZooKeeper 3-node StatefulSet running in Kubernetes (Task f)
kubectl get statefulset zk -n transit-system
kubectl get pods -n transit-system -l app=zookeeper

# 2. Check cluster Quorum and Leader/Follower roles directly inside ZooKeeper (Task f)
kubectl exec -it zk-0 -n transit-system -- ./bin/zkServer.sh status
kubectl exec -it zk-1 -n transit-system -- ./bin/zkServer.sh status
kubectl exec -it zk-2 -n transit-system -- ./bin/zkServer.sh status
# (You will see two nodes reporting 'Mode: follower' and one reporting 'Mode: leader')

# 3. Run the interactive ZooKeeper Leader Election & Failover script (Task f)
python3 ~/transit-cloud/scripts/demo_zookeeper_failover.py

# 4. Run Apache Flink stream processor unit test suite (Task e)
python3 ~/transit-cloud/services/05-stream-processor/test_stream_processor.py
```

---

### Member 3: Viva Questions & Prepared Answers

#### Q1: "Why does ZooKeeper require an odd number of nodes (3, 5, 7) instead of an even number like 4?"
> **Answer**: "ZooKeeper relies on strict majority quorum: $Q = \lfloor N/2 \rfloor + 1$. A 3-node cluster can tolerate 1 failure $(3 - 2 = 1)$. A 4-node cluster requires 3 nodes for quorum $(4/2 + 1 = 3)$, meaning it can STILL only tolerate 1 failure $(4 - 3 = 1)$. Adding the 4th node adds network overhead and failure surface without increasing fault tolerance. Therefore, odd numbers are mathematically optimal."

#### Q2: "How does Flink distinguish between Event Time and Processing Time?"
> **Answer**: "Processing Time is the wall-clock time of the server machine running Flink. Event Time is the timestamp embedded in the telemetry payload by the bus GPS sensor at the moment of coordinate capture. We use Event Time combined with Watermarks so that network buffering or temporary GCP VM stalls do not skew time-windowed speed calculations."

#### Q3: "What happens in ZooKeeper when an active leader loses network connectivity for 10 seconds?"
> **Answer**: "ZooKeeper uses a heartbeat timeout session (`tickTime` $\times$ `syncLimit`, configured to 4 seconds). When heartbeats cease, ZooKeeper server declares the session expired and deletes the leader's ephemeral znode `/transit/leader/analytics`. The standby instance, which registered a `NodeDeleted` watcher, immediately receives notification and promotes itself to Leader without split-brain risk."

---

# 7. Member 4 Deep-Dive: 3 Storage Tiers, Serverless Function & Observability

| Field | Detail |
|---|---|
| **Assigned Member** | Member 4 |
| **Assigned Tasks** | **Task (g)**: Three Distinct Cloud Storage Products <br> **Task (h)**: Comprehensive Observability Stack (Prometheus, Grafana, Loki) |
| **Assigned Microservices** | **Microservice 7**: Delay Alert Service (Serverless Cloud Function) <br> **Microservice 8**: Transport Analytics API & Public Web Dashboard |
| **Code Ownership** | `k8s/observability/`, `services/07-delay-alert-function/`, `services/08-transport-analytics/`, `scripts/verify_observability_stack.py` |

---

### What Did Member 4 Build? (Plain English Explanation)
Member 4 built the **multi-tier storage architecture, serverless alert triggers, observability infrastructure, and public UI**:
1. **Three Distinct Cloud Storage Products (Polyglot Persistence)**:
   - **Cloud SQL (PostgreSQL)**: Relational database storing structured, ACID-compliant fleet and route tables.
   - **Google Cloud Firestore (Native NoSQL)**: High-speed document database storing live bus coordinates and real-time ETAs for instant web client queries.
   - **Google Cloud Storage (GCS Bucket)**: Object storage archive storing raw telemetry JSON files with automated Coldline lifecycle policies.
2. **Serverless Cloud Function Gen2 (`transit-delay-alert`)**: An event-driven function running in `us-central1`. Whenever the stream processor detects a bus falling more than 5 minutes behind schedule, it publishes an alert event to the Pub/Sub topic `bus-delay-alerts`. The serverless function automatically wakes up, formats passenger notification payloads, and logs the incident, costing $0 when idle.
3. **Observability Stack (Prometheus, Grafana, Loki, Promtail)**: Complete visibility into system operations:
   - **Prometheus**: Scrapes metrics every 15s from 7 target services.
   - **Grafana**: Pre-configured with 5 visual dashboard panels (Throughput, p95 Latency, HPA Replicas, Active Fleet, Delay Alerts).
   - **Loki & Promtail**: Centralized log streaming and aggregation across all Kubernetes pods.
4. **Microservice 8 & Public Web Dashboard**: The user-facing application on external IP **`34.132.139.56`**, featuring a live Leaflet map and countdown arrival board.

---

### Key Concepts Explained from Scratch

#### 1. Why Three Distinct Storage Products Instead of Just One?
- If you put everything into **Cloud SQL**, storing millions of GPS telemetry pings would explode disk usage and lock database tables, slowing down commuter queries.
- If you put everything into **Firestore**, running relational joins (e.g. *"Show all Volvo buses assigned to Route 2B with capacity > 50"*) would be extremely slow and expensive.
- **Our Polyglot Strategy**:
  1. *Relational Relational SQL (Cloud SQL)*: Fits structured data requiring schemas and foreign keys (`vehicles`, `routes`, `stops`).
  2. *Managed NoSQL (Firestore)*: Fits key-value lookups with sub-10ms read latencies for thousands of commuters checking ETAs simultaneously.
  3. *Cloud Object Storage (GCS)*: Fits cold historical archives and GTFS static feeds at a fraction of the cost ($0.004/GB/month).

#### 2. What is Serverless Computing (Cloud Functions Gen2)?
- **Traditional Server**: A VM or container that runs 24/7, consuming CPU and costing money even when no requests arrive.
- **Serverless**: Zero servers running by default. When an event fires (e.g. a message arrives on Pub/Sub topic `bus-delay-alerts`), Google Cloud instantly spins up a lightweight container, executes Python code in 50 milliseconds, and shuts it down. If 0 alerts fire, you pay **$0.00**.

#### 3. What is the Observability Stack (Metrics vs Logs)?
- **Metrics (Prometheus)**: Numerical counters and gauges over time (e.g., `transport_analytics_active_buses = 11`, `http_requests_total = 475`). Excellent for alerts, dashboards, and seeing trends.
- **Visuals (Grafana)**: The graphical web UI that queries Prometheus and draws real-time charts and graphs.
- **Logs (Loki & Promtail)**: Text records of what happened inside the code (e.g., `[INFO] Bus 101 arrived at stop 3`). Promtail is a DaemonSet that reads log files from every node and ships them to Loki.

---

### Member 4: Step-by-Step Viva Demonstration Commands

```bash
# 1. Test Storage Product 1: Cloud SQL PostgreSQL (Task g)
PGPASSWORD="TransitSecurePass2026!" psql -h 34.46.78.203 -U transit_admin -d transit_db \
  -c "SELECT route_id, route_short_name, total_distance_km FROM routes;"

# 2. Test Storage Product 2: Google Cloud Firestore Native NoSQL (Task g)
gcloud firestore databases list --project=transit-s11-bits-12730

# 3. Test Storage Product 3: Cloud Storage GCS Bucket (Task g)
gcloud storage ls | grep "transit-telemetry"

# 4. Verify Serverless Cloud Function Gen2 is ACTIVE & review execution logs (Microservice 7)
gcloud functions list --regions=us-central1 --project=transit-s11-bits-12730
gcloud functions logs read transit-delay-alert --region=us-central1 --limit=5

# 5. Check live Prometheus metrics scraped from Microservice 8 (Task h & Microservice 8)
curl -s http://34.132.139.56/metrics | grep "transport_analytics" | head -n 10

# 6. Run the automated Observability verification test suite (Task h)
python3 ~/transit-cloud/scripts/verify_observability_stack.py
```

---

### Member 4: Viva Questions & Prepared Answers

#### Q1: "Why did you choose Google Cloud Functions Gen2 instead of Gen1?"
> **Answer**: "Cloud Functions Gen2 is powered by Google Cloud Run and Knative. It supports larger container sizes, longer request timeouts (up to 60 minutes), and concurrency up to 80 requests per instance, preventing cold-start delays during sudden traffic bursts while retaining native event integration with Google Cloud Pub/Sub."

#### Q2: "How do Prometheus metric types differ between Counter and Gauge in your analytics service?"
> **Answer**: "We use Counters for monotonically increasing values, such as `transport_analytics_http_requests_total` (where we compute per-second rates using `rate()`). We use Gauges for values that fluctuate up and down, such as `transport_analytics_active_buses` (currently tracked fleet) and `transport_analytics_delay_alerts_total`."

#### Q3: "What lifecycle policy is configured on the GCS raw telemetry bucket?"
> **Answer**: "Raw GPS JSON payloads are ingested into standard storage for instant debugging. In `terraform/modules/gcs/main.tf`, we configured an automated lifecycle rule: objects older than 30 days automatically transition to Coldline storage ($0.004/GB/month), and objects older than 90 days are permanently deleted to ensure zero cost overages."

---

# 8. Common Evaluator Questions & Trap Answers

Here are critical questions that professors and evaluators love to ask to test if the group understands the distributed system:

### Q1: "What happens if the entire region experiences a zone failure?"
> **Answer**: "Currently, our GKE cluster and Cloud SQL instance are provisioned in `us-central1-a` to maximize free-tier cost efficiency ($0 cluster fee for zonal GKE). In an enterprise production deployment, we would change `location` in Terraform to a Regional cluster (`us-central1`) spanning 3 availability zones (`a`, `b`, `c`) with a Regional Cloud SQL instance with High Availability (HA) automatic standby failover."

### Q2: "How did you guarantee that your project did not incur huge cloud bills?"
> **Answer**: "We implemented strict zero-cost architectural constraints:
> 1. Used a Zonal GKE cluster which waives the $74/month cluster management fee.
> 2. Sized worker nodes as `e2-medium` instances with HPA scaled down to 2 nodes baseline.
> 3. Cloud SQL utilizes the smallest `db-f1-micro` tier.
> 4. Firestore Native operates within the 50,000 free reads / 20,000 free writes per day quota.
> 5. GCS lifecycle rules prevent unbounded object growth.
> 6. We built a 1-command Sleep Mode script (`scripts/cost_guardrail.sh`) to resize nodes to 0 overnight."

### Q3: "How does the system calculate dynamic arrival estimates (ETAs)?"
> **Answer**: "Microservice 8 uses the Haversine formula to compute the great-circle distance $d$ in kilometers between the bus coordinates $(\phi_1, \lambda_1)$ and the destination stop coordinates $(\phi_2, \lambda_2)$:
> $$d = 2R \arcsin \left( \sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos \phi_1 \cos \phi_2 \sin^2\left(\frac{\Delta \lambda}{2}\right)} \right)$$
> It then divides this remaining distance by the moving-average speed received from Flink and adds stop dwell times modulated by passenger crowd density from Service 6."

---

# 9. Comprehensive Cloud Glossary

- **ACID**: Atomicity, Consistency, Isolation, Durability — database guarantees provided by Cloud SQL PostgreSQL.
- **ArgoCD**: A declarative GitOps continuous delivery tool for Kubernetes that syncs cluster state with a Git repository.
- **DaemonSet**: A Kubernetes controller that ensures all cluster nodes run a copy of a specific pod (used for Promtail log collectors).
- **Ephemeral Node**: A temporary znode in ZooKeeper that exists only as long as the client session is alive; deleted automatically upon crash.
- **Event Time**: The exact time a sensor created data, as opposed to the time the cloud server received it.
- **Flink**: A distributed stream processing framework capable of stateful computations over data streams.
- **gRPC**: Google Remote Procedure Call — a high-performance, open-source universal RPC framework utilizing HTTP/2 and Protocol Buffers.
- **HPA**: Horizontal Pod Autoscaler — automatically adjusts the number of pod replicas based on observed CPU utilization.
- **IaC**: Infrastructure as Code — defining cloud infrastructure through machine-readable definition files (Terraform).
- **Loki**: A horizontally scalable, multi-tenant log aggregation system inspired by Prometheus.
- **Prometheus**: An open-source systems monitoring and alerting toolkit with a time-series database.
- **Protocol Buffers (Protobuf)**: Google's language-neutral, platform-neutral mechanism for serializing structured data.
- **Quorum**: The minimum number of server members that must be active and agree before a distributed decision or write is committed.
- **Serverless**: A cloud execution model where the cloud provider dynamically manages the allocation and provisioning of servers (Cloud Functions).
- **Watermark**: In stream processing, a threshold indicating the progress of Event Time, used to determine when all data up to a given point has arrived.
- **ZooKeeper**: A centralized service for maintaining configuration information, naming, providing distributed synchronization, and group services.
