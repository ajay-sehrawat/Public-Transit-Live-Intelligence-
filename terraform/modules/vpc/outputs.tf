output "network_id" {
  description = "The ID of the created VPC network"
  value       = google_compute_network.vpc_network.id
}

output "network_name" {
  description = "The name of the created VPC network"
  value       = google_compute_network.vpc_network.name
}

output "subnet_id" {
  description = "The ID of the primary subnetwork"
  value       = google_compute_subnetwork.subnet.id
}

output "subnet_name" {
  description = "The name of the primary subnetwork"
  value       = google_compute_subnetwork.subnet.name
}

output "pods_range_name" {
  description = "Secondary range name allocated for Kubernetes Pods"
  value       = "gke-pods"
}

output "services_range_name" {
  description = "Secondary range name allocated for Kubernetes Services"
  value       = "gke-services"
}

