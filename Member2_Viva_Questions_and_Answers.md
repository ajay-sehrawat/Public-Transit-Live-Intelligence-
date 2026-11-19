# BITS Pilani — CS/SS G527 Cloud Computing
## Member 2 Viva Voce Preparation Manual: Questions & In-Depth Explanations
**Student Responsibility Area:**
- **Task (c) [8M]:** Managed Kubernetes (GKE), Horizontal Pod Autoscaling (HPA), and k6 Load Testing
- **Task (d) [6M]:** GitOps Controller (ArgoCD Continuous Delivery & Self-Healing)
- **Microservice 3:** Route Service (Route geometry, stops, geofences, gRPC 50053 & REST 8003)
- **Microservice 4:** Event Adapter (Kafka consumer/producer, telemetry normalization, UUID tagging, geospatial enrichment)
**Total Evaluation Weight:** **14 Marks Implementation + Individual Viva (12M Pool)**

---

## TABLE OF CONTENTS
1. [Category 1: Task (c) — Kubernetes Engine & HPA Autoscaling](#category-1-task-c--kubernetes-engine--hpa-autoscaling)
2. [Category 2: Task (d) — GitOps Architecture & ArgoCD Self-Healing](#category-2-task-d--gitops-architecture--argocd-self-healing)
3. [Category 3: Microservice 3 — Route Service Architecture](#category-3-microservice-3--route-service-architecture)
4. [Category 4: Microservice 4 — Event Adapter & Kafka Pipeline](#category-4-microservice-4--event-adapter--kafka-pipeline)
5. [Category 5: Advanced & Tricky Viva Scenarios](#category-5-advanced--tricky-viva-scenarios)

---

## CATEGORY 1: Task (c) — Kubernetes Engine & HPA Autoscaling

### Q1. What is Horizontal Pod Autoscaling (HPA) and how does its mathematical algorithm work?
* **30-Second Punchy Answer:**  
  "HPA automatically scales the number of pod replicas up or down based on observed resource utilization, such as CPU. The core algorithm calculates desired replicas using the ratio of the currently observed metric to the target metric:  
  $$\text{Desired Replicas} = \left\lceil \text{Current Replicas} \times \left( \frac{\text{Current Metric Value}}{\text{Target Metric Value}} \right) \right\rceil$$  
  In our project, we target 50% CPU utilization across a replica range of 2 to 10 pods."
* **In-Depth Explanation:**  
  - Kubernetes checks metrics every 15 seconds (the `horizontal-pod-autoscaler-sync-period`).
  - If our deployment has 2 replicas running at an average of 85% CPU, and our target is 50%, HPA computes:  
    $$\text{Desired Replicas} = \lceil 2 \times (85 / 50) \rceil = \lceil 3.4 \rceil = 4 \text{ pods}$$
  - HPA then updates the `spec.replicas` field of the Deployment.
  - If the computed ratio is within a 10% tolerance band (0.90 to 1.10 of target), HPA skips scaling to avoid unnecessary thrashing.
* **Live Command to Prove It:**
  ```bash
  kubectl get hpa event-adapter-hpa -n transit-system
  kubectl describe hpa event-adapter-hpa -n transit-system
  ```

---

### Q2. Where does HPA get its CPU and memory metrics from? What happens if `resources.requests` is missing?
* **30-Second Punchy Answer:**  
  "HPA fetches metrics from the **Kubernetes Metrics Server** via the `metrics.k8s.io` API. If `resources.requests.cpu` is omitted from the pod specification, HPA **fails completely** and stays in an `<unknown>` state because percentage CPU utilization is mathematically defined as $\frac{\text{Actual Usage}}{\text{Requested CPU}}$. Without a baseline request, percentage cannot be calculated."
* **In-Depth Explanation:**  
  - In each cluster node, the `cAdvisor` agent embedded inside the `kubelet` collects raw container CPU and memory usage from Linux cgroups.
  - The cluster-level `Metrics Server` scrapes these nodes periodically and exposes them via the aggregated API (`metrics.k8s.io`).
  - In our `deployment.yaml`, we explicitly defined:
    ```yaml
    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 256Mi
    ```
    100m equals 0.1 vCPU (100 millicores). When container usage hits 50m CPU, that corresponds exactly to 50% target utilization, triggering HPA logic.
* **Live Command to Prove It:**
  ```bash
  kubectl top pods -n transit-system -l app=event-adapter
  ```

---

### Q3. What is the difference between HPA, VPA, and Cluster Autoscaler (CA)?
* **30-Second Punchy Answer:**  
  - **HPA (Horizontal Pod Autoscaler):** Scales *out/in* by adding or removing pod instances (e.g. 2 pods $\to$ 6 pods).
  - **VPA (Vertical Pod Autoscaler):** Scales *up/down* by increasing or decreasing the CPU/memory allocated to an existing pod (requires restarting the pod).
  - **Cluster Autoscaler (CA):** Scales the underlying *Google Compute Engine VM nodes* when pods cannot be scheduled due to insufficient cluster capacity.
* **In-Depth Explanation:**  
  - In cloud-native microservices, HPA is preferred for stateless workloads like `event-adapter` because scaling horizontally provides zero downtime and handles traffic spikes instantly.
  - When HPA scales `event-adapter` from 2 to 10 pods, if the existing 2 GKE nodes run out of allocatable CPU, the pods go to `Pending` status with `0/2 nodes available: Insufficient cpu`.
  - That event signals the **Cluster Autoscaler (CA)** to provision a 3rd GCE VM instance in `us-central1-a` to host the pending pods.

---

### Q4. How does HPA prevent "flapping" or "thrashing" when traffic fluctuates rapidly?
* **30-Second Punchy Answer:**  
  "Kubernetes implements **Stabilization Windows** and cooldown periods. While scale-up happens rapidly (within seconds) to maintain SLA, scale-down enforces a default **300-second (5-minute) stabilization window**. The autoscaler evaluates the maximum recommendation across that entire window before terminating any pods."
* **In-Depth Explanation:**  
  - "Flapping" occurs when a burst of load causes replicas to jump from 2 $\to$ 8, then traffic drops for 10 seconds, causing scale down to 2, and then immediately spikes again.
  - The stabilization window ensures that pods remain alive for at least 5 minutes after traffic normalizes, absorbing secondary surges without continuous pod recreation overhead.

---

### Q5. How did you simulate load and verify the HPA autoscaling behavior in Task (c)?
* **30-Second Punchy Answer:**  
  "We wrote both a JavaScript load generator using **k6** (`load-testing/load_test_hpa.js`) and a standalone Python simulation test suite (`load-testing/test_hpa_simulation.py`). The suite ramps simulated concurrent commuter telemetry up to 500 Virtual Users (VUs), injecting hundreds of requests per second into the Event Adapter endpoint to drive CPU past 50%, verifying scale-up and scale-down thresholds."
* **Live Command to Prove It:**
  ```bash
  python3 ~/transit-cloud/load-testing/test_hpa_simulation.py
  ```

---

## CATEGORY 2: Task (d) — GitOps Architecture & ArgoCD Self-Healing

### Q6. What is GitOps and why is it superior to traditional Push-based CI/CD (like Jenkins or raw `kubectl apply`)?
* **30-Second Punchy Answer:**  
  "GitOps is an operational model where **Git is the single source of truth** for declarative infrastructure and applications. Instead of external CI/CD pipelines pushing changes using broad cluster-admin credentials, an in-cluster GitOps agent (ArgoCD) continuously pulls from Git, reconciles differences, and enforces automated self-healing."
* **In-Depth Explanation:**  
  | Feature | Traditional CI/CD (Push) | GitOps with ArgoCD (Pull) |
  | :--- | :--- | :--- |
  | **Cluster Credentials** | Stored in external CI runner (high security risk) | Stay strictly inside the cluster (zero external access) |
  | **Configuration Drift** | Undetected if someone manually modifies cluster | Instantly detected and overwritten back to Git state |
  | **Rollback Mechanism** | Complex multi-stage rerun of build scripts | Instant `git revert <commit>` triggers rollback |
  | **Auditability** | Scatted across CI build logs | Complete history in `git log` with author signatures |

---

### Q7. What is "Self-Healing" in ArgoCD and how did you demonstrate it?
* **30-Second Punchy Answer:**  
  "Self-healing means that if an operator or malicious actor manually alters or deletes a cluster resource (e.g. running `kubectl scale deployment route-service --replicas=0` or deleting a service), the ArgoCD controller immediately detects the drift during its reconciliation loop and **automatically reinstates the desired state declared in Git**."
* **In-Depth Explanation:**  
  - In our `k8s/argocd/application-root.yaml`, we declared:
    ```yaml
    syncPolicy:
      automated:
        prune: true
        selfHeal: true
    ```
  - `selfHeal: true` tells ArgoCD: whenever the live state diverges from Git, immediately apply Git state.
  - `prune: true` ensures that if a file is deleted from Git, the corresponding Kubernetes resource is cleanly removed from the cluster.
* **Live Command to Prove It:**
  ```bash
  python3 ~/transit-cloud/scripts/verify_gitops_pipeline.py
  ```

---

### Q8. What is the role of Kustomize in your GitOps deployment?
* **30-Second Punchy Answer:**  
  "Kustomize provides **template-free declarative configuration management**. It allows us to maintain a clean `k8s/base/` directory holding common deployments and services, while using `k8s/production/kustomization.yaml` to apply environment-specific overlays (namespaces, ingress rules, resource quotas) without duplication."
* **In-Depth Explanation:**  
  - Unlike Helm, Kustomize uses pure Kubernetes YAML without `{{ .Values.foo }}` template syntax.
  - ArgoCD natively understands Kustomize: when pointing to `k8s/production`, ArgoCD automatically runs `kustomize build` to render the final manifest tree before applying.

---

## CATEGORY 3: Microservice 3 — Route Service Architecture

### Q9. What does Microservice 3 (Route Service) do and why does it expose BOTH gRPC and REST APIs?
* **30-Second Punchy Answer:**  
  "Route Service manages transit route geometry, waypoint coordinates, bus stops, and geofence perimeters. It exposes **gRPC (port 50053)** for low-latency, binary inter-service communication with Event Adapter and Stream Processor (<3ms response time), while offering **REST (port 8003)** for HTTP clients, OpenAPI documentation, and web frontends."
* **In-Depth Explanation:**  
  - Inter-service queries happen dozens of times per second as GPS coordinates stream in. Using gRPC avoids HTTP/1.1 header overhead and JSON parsing costs.
  - The gRPC contract is defined in `services/common/proto/transit.proto` under service `RouteGeometryService`:
    - `GetRouteDetails(RouteDetailsRequest) returns (RouteDetailsResponse)`
    - `GetNearestStop(NearestStopRequest) returns (NearestStopResponse)`
  - REST endpoints (`/api/v1/routes`, `/api/v1/routes/{id}`) allow browser inspection and standard curl testing.
* **Live Command to Prove It:**
  ```bash
  kubectl exec -n transit-system deployment/route-service -- curl -s http://localhost:8003/api/v1/routes/ROUTE-1
  ```

---

### Q10. How does Route Service calculate whether a bus is inside a transit stop? What is a geofence?
* **30-Second Punchy Answer:**  
  "A geofence is a virtual circular perimeter around a geographic stop coordinate (e.g. 60m radius around BITS Clock Tower). When GPS coordinates arrive, Route Service computes the distance using the **Haversine formula**. If distance $\le \text{geofence\_radius\_meters}$, the vehicle is flagged as `ARRIVED` at that stop."
* **In-Depth Explanation:**  
  - Haversine computes great-circle distance between two points on a sphere given latitude and longitude ($\phi_1, \lambda_1$) and ($\phi_2, \lambda_2$):
    $$d = 2R \arcsin \left( \sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)} \right)$$
  - Where $R = 6371000\text{ meters}$ (Earth radius).
  - Stop thresholds used in our code:
    - Pilani Bus Stand (`STOP-001`): 80m
    - BITS Clock Tower (`STOP-002`): 60m
    - Library Circle (`STOP-003`): 50m

---

## CATEGORY 4: Microservice 4 — Event Adapter & Kafka Pipeline

### Q11. What is the role of Microservice 4 (Event Adapter)? Why not feed GPS data directly into the database?
* **30-Second Punchy Answer:**  
  "Event Adapter acts as a **decoupling and enrichment boundary**. Raw GPS pings from onboard bus trackers are often messy, unvalidated, and lack transit context. Event Adapter consumes raw telemetry from Kafka topic `bus-gps-raw`, validates schemas, tags a unique UUID `event_id`, calculates distance to the next stop, and publishes a clean schema to `bus-gps-normalized`."
* **In-Depth Explanation:**  
  - Writing raw GPS pings directly to a database causes lock contention and fills tables with unindexed, unnormalized coordinates.
  - By placing Event Adapter between raw Kafka ingestion and downstream stream processing:
    1. Downstream consumers (Flink, Firestore, Analytics) receive clean, validated schemas.
    2. Any malformed GPS packets are caught and sent to error queues without crashing downstream engines.
* **Live Command to Prove It:**
  ```bash
  kubectl exec -n transit-system deployment/event-adapter -- curl -s http://localhost:8004/health
  ```

---

### Q12. How does Event Adapter handle Kafka consumer offsets and prevent data loss if a pod crashes?
* **30-Second Punchy Answer:**  
  "Event Adapter belongs to the consumer group `event-adapter-group`. In Kafka, committed offsets track how far the consumer has processed. If a pod crashes, Kafka triggers a **consumer group rebalance**, allowing another pod replica to pick up processing from the last committed offset, guaranteeing **at-least-once processing semantics**."
* **In-Depth Explanation:**  
  - We use manual offset commits after successful enrichment and publication to `bus-gps-normalized`.
  - If a crash occurs mid-flight before the commit, the replacement pod re-reads that record. Because all normalized records contain a deterministic UUID `event_id`, downstream consumers can deduplicate safely (idempotency).

---

## CATEGORY 5: Advanced & Tricky Viva Scenarios

### Q13. Professor asks: "If traffic suddenly surges by 500%, what happens across your microservices?"
* **Step-by-Step Response:**
  1. **Ingestion & Buffering:** Raw GPS pings flood into Kafka topic `bus-gps-raw`. Kafka acts as a shock absorber; partitions buffer the spike without dropping packets.
  2. **HPA Scaling:** Event Adapter's CPU consumption increases as it drains messages. When CPU exceeds 50%, HPA triggers and scales the Deployment from 2 pods up to 10 pods.
  3. **Cluster Autoscaling:** If GKE nodes cannot schedule the new pods, GKE Cluster Autoscaler provisions additional `e2-medium` nodes in `us-central1-a`.
  4. **Downstream Isolation:** Because Route Service handles queries in under 3ms via gRPC and caches stop coordinates in memory, it does not become a bottleneck.
  5. **Cool-down:** When traffic subsides, HPA waits 300 seconds before gradually scaling replicas back to 2.

---

### Q14. Professor asks: "What is the difference between a Kubernetes `readinessProbe` and `livenessProbe`?"
* **Punchy Answer:**
  - **`livenessProbe`:** Checks if the container is **alive**. If it fails (e.g. application deadlock or infinite loop), Kubernetes **kills and restarts the container**.
  - **`readinessProbe`:** Checks if the container is **ready to receive network traffic**. If it fails (e.g. database still connecting), Kubernetes **removes the pod from the Service load balancer**, but does *not* kill it.

---

### Q15. Summary of Key Ports & Services for Member 2

| Service / Resource | Internal Port | Protocol | Purpose |
| :--- | :--- | :--- | :--- |
| **Microservice 3 (Route Service)** | `8003` | HTTP / REST | Route details, stop queries, health |
| **Microservice 3 (Route Service)** | `50053` | gRPC / HTTP2 | Low-latency binary inter-service RPC |
| **Microservice 4 (Event Adapter)** | `8004` | HTTP / REST | Event normalization API, health, metrics |
| **Kafka Broker** | `9092` | TCP | Telemetry message queue (`bus-gps-raw`) |
| **ArgoCD Server** | `443` | HTTPS | Declarative GitOps synchronization web UI |
| **Kubernetes Metrics API** | `443` | HTTPS | CPU usage aggregation feeding HPA |
