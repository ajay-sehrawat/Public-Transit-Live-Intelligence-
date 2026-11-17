resource "google_service_account" "microservices_sa" {
  account_id   = "transit-microservices-sa"
  display_name = "Service Account for Transit Microservices on GKE"
  project      = var.project_id
}

# Grant permissions for Firestore (Storage Product 2: NoSQL)
resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.microservices_sa.email}"
}

# Grant permissions for GCS (Storage Product 3: Object Store)
resource "google_project_iam_member" "storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.microservices_sa.email}"
}

# Grant Cloud SQL Client permission (Storage Product 1: Managed SQL)
resource "google_project_iam_member" "cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.microservices_sa.email}"
}

# Grant Logging & Monitoring permissions
resource "google_project_iam_member" "log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.microservices_sa.email}"
}

resource "google_project_iam_member" "metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.microservices_sa.email}"
}

# Workload Identity binding: Connects GKE Service Account (KSA) to Google Service Account (GSA)
resource "google_service_account_iam_member" "workload_identity_user" {
  service_account_id = google_service_account.microservices_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[transit-system/transit-ksa]"
}

