variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for the Subnetwork"
  type        = string
}

variable "network_name" {
  description = "Name of the VPC Network"
  type        = string
  default     = "transit-vpc"
}

variable "subnet_name" {
  description = "Name of the primary Subnet"
  type        = string
  default     = "transit-subnet-us-central1"
}

variable "subnet_cidr" {
  description = "Primary CIDR block for GKE nodes and database instances"
  type        = string
  default     = "10.10.0.0/20"
}

variable "pods_cidr" {
  description = "Secondary CIDR range for Kubernetes Pods (VPC-native GKE)"
  type        = string
  default     = "10.20.0.0/16"
}

variable "services_cidr" {
  description = "Secondary CIDR range for Kubernetes Services (ClusterIPs)"
  type        = string
  default     = "10.30.0.0/20"
}

