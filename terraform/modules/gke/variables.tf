variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
}

variable "zone" {
  description = "GCP Zone for the Zonal Cluster ($0 management fee)"
  type        = string
}

variable "cluster_name" {
  description = "Name of the GKE Cluster"
  type        = string
  default     = "transit-gke-cluster"
}

variable "network_name" {
  description = "VPC network name"
  type        = string
}

variable "subnet_name" {
  description = "Subnet name"
  type        = string
}

variable "pods_range_name" {
  description = "Secondary IP range name for Pods"
  type        = string
}

variable "services_range_name" {
  description = "Secondary IP range name for Services"
  type        = string
}

variable "node_count" {
  description = "Initial number of nodes"
  type        = number
  default     = 2
}

variable "min_nodes" {
  description = "Minimum nodes for cluster autoscaler"
  type        = number
  default     = 2
}

variable "max_nodes" {
  description = "Maximum nodes for cluster autoscaler"
  type        = number
  default     = 5
}

variable "machine_type" {
  description = "GCE machine type for worker nodes"
  type        = string
  default     = "e2-medium"
}

