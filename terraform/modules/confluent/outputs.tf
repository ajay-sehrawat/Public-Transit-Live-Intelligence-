output "bootstrap_servers" {
  description = "Kafka Bootstrap Server Endpoint"
  value       = var.kafka_bootstrap_servers
}

output "topic_raw" {
  description = "Kafka topic for raw bus GPS events"
  value       = "bus-gps-raw"
}

output "topic_normalized" {
  description = "Kafka topic for normalized telemetry events"
  value       = "bus-gps-normalized"
}

output "topic_estimates" {
  description = "Kafka topic for windowed arrival estimate results"
  value       = "bus-arrival-estimates"
}

output "topic_alerts" {
  description = "Kafka topic for disruption and delay alert events"
  value       = "bus-delay-alerts"
}

