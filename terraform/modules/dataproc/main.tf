resource "google_dataproc_cluster" "flink_cluster" {
  name     = var.cluster_name
  region   = var.region
  project  = var.project_id

  cluster_config {
    staging_bucket = var.staging_bucket

    master_config {
      num_instances = 1
      machine_type  = var.master_machine_type
      disk_config {
        boot_disk_type    = "pd-standard"
        boot_disk_size_gb = 30
      }
    }

    worker_config {
      num_instances = var.num_workers
      machine_type  = var.worker_machine_type
      disk_config {
        boot_disk_type    = "pd-standard"
        boot_disk_size_gb = 30
      }
    }

    software_config {
      image_version       = "2.1-debian11"
      optional_components = ["FLINK"]
    }

    endpoint_config {
      enable_http_port_access = true # Enables Flink Web Dashboard access via Dataproc Component Gateway
    }
  }

  graceful_decommission_timeout = "60s"
}

