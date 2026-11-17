resource "google_container_cluster" "primary" {
  name     = var.cluster_name
  location = var.zone # Zonal cluster qualifies for Google Cloud's $0 cluster fee
  project  = var.project_id

  # Remove default pool immediately to use a managed custom node pool
  remove_default_node_pool = true
  initial_node_count       = 1

  network    = var.network_name
  subnetwork = var.subnet_name

  # VPC-Native Cluster configuration (alias IP routing)
  ip_allocation_policy {
    cluster_secondary_range_name  = var.pods_range_name
    services_secondary_range_name = var.services_range_name
  }

  # Addons required for Assignment Requirements:
  addons_config {
    # Requirement c: Horizontal Pod Autoscaler (HPA)
    horizontal_pod_autoscaling {
      disabled = false
    }

    # Public Web Service: Ingress HTTP(S) Load Balancing
    http_load_balancing {
      disabled = false
    }

    # CSI Driver for ZooKeeper StatefulSet Volumes
    gce_persistent_disk_csi_driver_config {
      enabled = true
    }
  }

  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  release_channel {
    channel = "REGULAR"
  }

  deletion_protection = false # Allows seamless student teardown with terraform destroy
}

resource "google_container_node_pool" "primary_nodes" {
  name       = "${var.cluster_name}-node-pool"
  location   = var.zone
  cluster    = google_container_cluster.primary.name
  project    = var.project_id
  node_count = var.node_count

  # Autoscaling configuration to support sustained load testing scale-outs
  autoscaling {
    min_node_count = var.min_nodes
    max_node_count = var.max_nodes
  }

  node_config {
    machine_type = var.machine_type # e2-medium (2 vCPU, 4GB RAM)
    disk_size_gb = 30
    disk_type    = "pd-standard"

    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
      "https://www.googleapis.com/auth/logging.write",
      "https://www.googleapis.com/auth/monitoring"
    ]

    tags = ["gke-node", "transit-service-node", "ingress-controller"]

    metadata = {
      disable-legacy-endpoints = "true"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}

