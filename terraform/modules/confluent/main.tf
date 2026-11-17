# Managed Kafka Topics and Configuration Descriptor
# Supports both Confluent Cloud ($400 free trial) and internal GKE Strimzi Kafka

locals {
  topic_map = { for t in var.topics : t.name => t.partitions }
}

# ConfigMap descriptor for microservices to discover Kafka topics
resource "google_pubsub_topic" "kafka_deadletter" {
  name    = "transit-kafka-deadletter-events"
  project = var.project_id
}

