output "function_name" {
  description = "Name of the deployed Cloud Function"
  value       = google_cloudfunctions2_function.delay_alert_function.name
}

output "function_uri" {
  description = "URI of the deployed Cloud Function service"
  value       = google_cloudfunctions2_function.delay_alert_function.service_config[0].uri
}

