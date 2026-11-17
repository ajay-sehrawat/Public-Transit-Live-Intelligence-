variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for Cloud Function"
  type        = string
  default     = "us-central1"
}

variable "function_name" {
  description = "Name of the serverless function"
  type        = string
  default     = "delay-alert-service"
}

variable "source_bucket" {
  description = "GCS bucket containing function source zip"
  type        = string
}

variable "pubsub_topic_id" {
  description = "Pub/Sub topic ID for event-driven trigger"
  type        = string
}

