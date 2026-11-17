variable "project_id" {
  description = "The Google Cloud Platform (GCP) Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for resource deployment (us-central1 is eligible for Free Tier)"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP Zone for the Zonal GKE cluster ($0 cluster management fee)"
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Environment identifier (e.g., production, development, demo)"
  type        = string
  default     = "production"
}

variable "cluster_name" {
  description = "Name of the GKE Managed Kubernetes Cluster"
  type        = string
  default     = "transit-gke-cluster"
}

variable "gke_node_count" {
  description = "Initial number of GKE worker nodes per zone"
  type        = number
  default     = 2
}

variable "gke_min_nodes" {
  description = "Minimum number of worker nodes for HPA scale-in"
  type        = number
  default     = 2
}

variable "gke_max_nodes" {
  description = "Maximum number of worker nodes for HPA scale-out"
  type        = number
  default     = 5
}

variable "gke_machine_type" {
  description = "Machine type for GKE worker nodes (e2-medium balances performance and credit efficiency)"
  type        = string
  default     = "e2-medium"
}

variable "db_instance_name" {
  description = "Instance identifier for Cloud SQL PostgreSQL"
  type        = string
  default     = "transit-postgres-db"
}

variable "db_tier" {
  description = "Machine tier for Cloud SQL PostgreSQL (db-f1-micro is lowest cost)"
  type        = string
  default     = "db-f1-micro"
}

variable "db_user" {
  description = "Master database username for Cloud SQL"
  type        = string
  default     = "transit_admin"
}

variable "db_password" {
  description = "Master database password for Cloud SQL"
  type        = string
  sensitive   = true
  default     = "TransitSecurePass2026!"
}

variable "gcs_bucket_prefix" {
  description = "Prefix for the raw telemetry and GTFS archive GCS bucket"
  type        = string
  default     = "transit-telemetry-raw"
}

variable "enable_dataproc_cluster" {
  description = "Whether to provision the managed Dataproc Flink cluster (enable for demo/viva)"
  type        = bool
  default     = false
}

variable "enable_cloud_functions" {
  description = "Whether to deploy the Serverless Cloud Function via Terraform"
  type        = bool
  default     = false
}

