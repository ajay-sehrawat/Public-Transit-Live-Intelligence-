variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for Cloud Storage"
  type        = string
  default     = "us-central1"
}

variable "bucket_prefix" {
  description = "Prefix for the GCS telemetry and GTFS bucket"
  type        = string
  default     = "transit-telemetry-raw"
}

