output "service_account_email" {
  description = "The email address of the IAM Service Account"
  value       = google_service_account.microservices_sa.email
}

output "service_account_id" {
  description = "The unique ID of the IAM Service Account"
  value       = google_service_account.microservices_sa.unique_id
}

