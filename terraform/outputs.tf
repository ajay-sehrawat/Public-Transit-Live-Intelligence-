# ==============================================================================
# Outputs for Inter-Service Configuration & Evaluation Verification
# ==============================================================================

output "vpc_network_name" {
  description = "The name of the VPC network"
  value       = module.vpc.network_name
}

output "gke_cluster_name" {
  description = "The name of the GKE Managed Kubernetes Cluster"
  value       = module.gke.cluster_name
}

output "gke_cluster_endpoint" {
  description = "The public endpoint IP of the GKE cluster master"
  value       = module.gke.cluster_endpoint
}

# ------------------------------------------------------------------------------
# 3 Storage Products Outputs (Requirement g)
# ------------------------------------------------------------------------------
output "storage_1_sql_connection_name" {
  description = "Storage Product 1: Cloud SQL PostgreSQL instance connection name"
  value       = module.cloud_sql.instance_connection_name
}

output "storage_1_sql_host" {
  description = "Storage Product 1: Cloud SQL PostgreSQL host IP"
  value       = module.cloud_sql.db_host
}

output "storage_1_sql_database" {
  description = "Storage Product 1: PostgreSQL database name"
  value       = module.cloud_sql.database_name
}

output "storage_2_nosql_firestore_id" {
  description = "Storage Product 2: Firestore Database ID (NoSQL)"
  value       = module.firestore.database_id
}

output "storage_3_object_store_gcs_bucket" {
  description = "Storage Product 3: Google Cloud Storage telemetry archive bucket"
  value       = module.gcs.bucket_name
}

# ------------------------------------------------------------------------------
# Messaging & IAM Outputs
# ------------------------------------------------------------------------------
output "kafka_bootstrap_servers" {
  description = "Kafka Bootstrap Servers"
  value       = module.confluent.bootstrap_servers
}

output "workload_service_account_email" {
  description = "IAM Service Account email configured with Workload Identity"
  value       = module.iam.service_account_email
}

output "kubectl_connect_command" {
  description = "Command to configure local kubectl to connect to the GKE cluster"
  value       = "gcloud container clusters get-credentials ${module.gke.cluster_name} --zone ${var.zone} --project ${var.project_id}"
}

