output "bucket_name" {
  description = "Name of the created GCS bucket"
  value       = google_storage_bucket.telemetry_archive.name
}

output "bucket_url" {
  description = "The URI of the created GCS bucket"
  value       = google_storage_bucket.telemetry_archive.url
}

output "pubsub_topic_id" {
  description = "The ID of the Pub/Sub topic receiving upload notifications"
  value       = google_pubsub_topic.gcs_upload_events.id
}

