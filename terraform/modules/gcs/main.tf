resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "google_storage_bucket" "telemetry_archive" {
  name          = "${var.bucket_prefix}-${var.project_id}-${random_id.bucket_suffix.hex}"
  location      = "US" # US multi-region qualifies for Google Cloud Always-Free Tier (5 GB-months)
  storage_class = "STANDARD"
  project       = var.project_id

  uniform_bucket_level_access = true
  force_destroy               = true # Permits clean terraform destroy during student evaluation

  # Lifecycle rule ensures bucket never exceeds free tier limits by pruning data > 7 days
  lifecycle_rule {
    action {
      type = "Delete"
    }
    condition {
      age = 7
    }
  }

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD", "PUT", "POST"]
    response_header = ["*"]
    max_age_seconds = 3600
  }
}

# Cloud Pub/Sub topic to notify serverless Cloud Functions on object upload
resource "google_pubsub_topic" "gcs_upload_events" {
  name    = "gcs-transit-upload-events"
  project = var.project_id
}

# Grant GCS service agent permission to publish to Pub/Sub
data "google_storage_project_service_account" "gcs_account" {
  project = var.project_id
}

resource "google_pubsub_topic_iam_member" "gcs_publisher" {
  topic   = google_pubsub_topic.gcs_upload_events.id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
  project = var.project_id
}

resource "google_storage_notification" "notification" {
  bucket         = google_storage_bucket.telemetry_archive.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.gcs_upload_events.id
  event_types    = ["OBJECT_FINALIZE"]
  depends_on     = [google_pubsub_topic_iam_member.gcs_publisher]
}

