variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "kafka_bootstrap_servers" {
  description = "Kafka Bootstrap Servers (e.g. Confluent Cloud or internal cluster)"
  type        = string
  default     = "kafka-service.transit-system.svc.cluster.local:9092"
}

variable "topics" {
  description = "List of required Kafka topics to manage"
  type = list(object({
    name       = string
    partitions = number
  }))
  default = [
    { name = "bus-gps-raw", partitions = 6 },
    { name = "bus-gps-normalized", partitions = 6 },
    { name = "bus-arrival-estimates", partitions = 6 },
    { name = "bus-delay-alerts", partitions = 3 }
  ]
}

