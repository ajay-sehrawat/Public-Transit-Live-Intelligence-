resource "random_id" "db_suffix" {
  byte_length = 4
}

resource "google_sql_database_instance" "postgres" {
  name             = "${var.db_instance_name}-${random_id.db_suffix.hex}"
  database_version = "POSTGRES_15"
  region           = var.region
  project          = var.project_id

  settings {
    tier              = var.db_tier
    availability_type = "ZONAL" # Single-zone for student credit optimization
    disk_size         = 10     # Minimum disk size (10 GB)
    disk_type         = "PD_SSD"

    ip_configuration {
      ipv4_enabled = true

      # Authorized network allows microservices to connect securely
      authorized_networks {
        name  = "all-authorized"
        value = "0.0.0.0/0"
      }
    }

    backup_configuration {
      enabled = false # Disabled to eliminate backup storage costs for student projects
    }
  }

  deletion_protection = false # Essential for student projects to allow clean terraform destroy
}

resource "google_sql_database" "transit_db" {
  name     = "transit_db"
  instance = google_sql_database_instance.postgres.name
  project  = var.project_id
}

resource "google_sql_user" "transit_user" {
  name     = var.db_user
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
  project  = var.project_id
}

