output "instance_name" {
  description = "The name of the Cloud SQL PostgreSQL instance"
  value       = google_sql_database_instance.postgres.name
}

output "instance_connection_name" {
  description = "The connection name of the Cloud SQL instance to be used in connection strings"
  value       = google_sql_database_instance.postgres.connection_name
}

output "db_host" {
  description = "The public IPv4 address of the master database instance"
  value       = google_sql_database_instance.postgres.public_ip_address
}

output "database_name" {
  description = "The name of the primary database"
  value       = google_sql_database.transit_db.name
}

output "db_user" {
  description = "The database user"
  value       = google_sql_user.transit_user.name
}

