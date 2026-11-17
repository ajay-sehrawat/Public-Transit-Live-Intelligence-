# ==============================================================================
# S11: Real-Time Public Transportation Tracking & Arrival Estimation System
# Primary Infrastructure as Code (IaC) Root Module
# ==============================================================================

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# 1. Custom VPC & Subnets with secondary ranges for GKE
module "vpc" {
  source     = "./modules/vpc"
  project_id = var.project_id
  region     = var.region
}

# 2. Managed Kubernetes (GKE Zonal Cluster with $0 Management Fee)
module "gke" {
  source              = "./modules/gke"
  project_id          = var.project_id
  region              = var.region
  zone                = var.zone
  cluster_name        = var.cluster_name
  network_name        = module.vpc.network_name
  subnet_name         = module.vpc.subnet_name
  pods_range_name     = module.vpc.pods_range_name
  services_range_name = module.vpc.services_range_name
  node_count          = var.gke_node_count
  min_nodes           = var.gke_min_nodes
  max_nodes           = var.gke_max_nodes
  machine_type        = var.gke_machine_type
}

# 3. Storage Product 1: Managed Relational Database (Cloud SQL PostgreSQL)
module "cloud_sql" {
  source           = "./modules/cloud_sql"
  project_id       = var.project_id
  region           = var.region
  db_instance_name = var.db_instance_name
  db_tier          = var.db_tier
  db_user          = var.db_user
  db_password      = var.db_password
}

# 4. Storage Product 2: Managed NoSQL Database (Google Cloud Firestore Always-Free Tier)
module "firestore" {
  source     = "./modules/firestore"
  project_id = var.project_id
  region     = var.region
}

# 5. Storage Product 3: Object Store (Google Cloud Storage 5 GB Free Tier)
module "gcs" {
  source        = "./modules/gcs"
  project_id    = var.project_id
  region        = var.region
  bucket_prefix = var.gcs_bucket_prefix
}

# 6. Managed Kafka Event Broker Topics & Configuration
module "confluent" {
  source     = "./modules/confluent"
  project_id = var.project_id
}

# 7. IAM & Workload Identity Bindings
module "iam" {
  source          = "./modules/iam"
  project_id      = var.project_id
  gcs_bucket_name = module.gcs.bucket_name
}

# 8. Managed Flink Stream Processing Cluster (Google Dataproc - Requirement e)
module "dataproc" {
  count          = var.enable_dataproc_cluster ? 1 : 0
  source         = "./modules/dataproc"
  project_id     = var.project_id
  region         = var.region
  staging_bucket = module.gcs.bucket_name
}

# 9. Serverless Function: Delay Alert Service (Google Cloud Functions - Requirement b)
module "cloud_functions" {
  count           = var.enable_cloud_functions ? 1 : 0
  source          = "./modules/cloud_functions"
  project_id      = var.project_id
  region          = var.region
  source_bucket   = module.gcs.bucket_name
  pubsub_topic_id = module.gcs.pubsub_topic_id
}

