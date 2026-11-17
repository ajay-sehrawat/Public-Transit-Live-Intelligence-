output "cluster_name" {
  description = "The name of the Dataproc cluster"
  value       = google_dataproc_cluster.flink_cluster.name
}

output "flink_dashboard_enabled" {
  description = "Indicates Flink Web Dashboard is accessible via Dataproc Component Gateway"
  value       = true
}

