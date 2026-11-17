variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for Dataproc"
  type        = string
  default     = "us-central1"
}

variable "cluster_name" {
  description = "Name of the managed Dataproc Flink cluster"
  type        = string
  default     = "transit-dataproc-cluster"
}

variable "staging_bucket" {
  description = "GCS bucket for Dataproc job staging"
  type        = string
}

variable "master_machine_type" {
  description = "Machine type for Dataproc master node"
  type        = string
  default     = "e2-standard-2"
}

variable "worker_machine_type" {
  description = "Machine type for Dataproc worker nodes"
  type        = string
  default     = "e2-standard-2"
}

variable "num_workers" {
  description = "Number of worker nodes in the cluster"
  type        = number
  default     = 2
}

