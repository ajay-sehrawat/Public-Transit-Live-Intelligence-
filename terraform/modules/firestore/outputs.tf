output "database_id" {
  description = "The ID of the Firestore database"
  value       = google_firestore_database.database.id
}

output "database_name" {
  description = "The name of the Firestore database"
  value       = google_firestore_database.database.name
}

output "location_id" {
  description = "The location in which the Firestore database resides"
  value       = google_firestore_database.database.location_id
}

