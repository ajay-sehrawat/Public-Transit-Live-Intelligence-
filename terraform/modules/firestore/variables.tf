variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "Location for Firestore (e.g. us-central1)"
  type        = string
  default     = "us-central1"
}

