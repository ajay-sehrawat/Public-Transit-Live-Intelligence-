# Create zip archive of the Cloud Function source
data "archive_file" "function_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../../services/07-delay-alert-function"
  output_path = "${path.module}/delay_alert_source.zip"
}

# Upload source zip to GCS Object Store
resource "google_storage_bucket_object" "function_archive" {
  name   = "serverless/delay_alert_source_${data.archive_file.function_zip.output_md5}.zip"
  bucket = var.source_bucket
  source = data.archive_file.function_zip.output_path
}

# Google Cloud Functions (2nd Gen) - Requirement b
resource "google_cloudfunctions2_function" "delay_alert_function" {
  name        = var.function_name
  location    = var.region
  description = "Serverless event-driven function dispatching transit delay alerts to NoSQL Firestore"
  project     = var.project_id

  build_config {
    runtime     = "python311"
    entry_point = "delay_alert_pubsub_handler"
    source {
      storage_source {
        bucket = var.source_bucket
        object = google_storage_bucket_object.function_archive.name
      }
    }
  }

  service_config {
    max_instance_count = 5
    min_instance_count = 0 # Scales to 0 for Always-Free Tier credit efficiency
    available_memory   = "256M"
    timeout_seconds    = 60
    environment_variables = {
      GCP_PROJECT_ID = var.project_id
    }
  }

  event_trigger {
    trigger_region = var.region
    event_type     = "google.cloud.pubsub.topic.v1.messagePublished"
    pubsub_topic   = var.pubsub_topic_id
    retry_policy   = "RETRY_POLICY_DO_NOT_RETRY"
  }
}

