variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for Cloud SQL"
  type        = string
}

variable "db_instance_name" {
  description = "Base name for Cloud SQL PostgreSQL instance"
  type        = string
  default     = "transit-postgres-db"
}

variable "db_tier" {
  description = "Machine tier for Cloud SQL PostgreSQL"
  type        = string
  default     = "db-f1-micro"
}

variable "db_user" {
  description = "Master database user"
  type        = string
  default     = "transit_admin"
}

variable "db_password" {
  description = "Master database password"
  type        = string
  sensitive   = true
}

