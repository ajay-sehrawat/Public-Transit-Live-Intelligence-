resource "google_compute_network" "vpc_network" {
  name                    = var.network_name
  auto_create_subnetworks = false
  description             = "Custom VPC for Real-Time Public Transportation Microservices"
  project                 = var.project_id
}

resource "google_compute_subnetwork" "subnet" {
  name                     = var.subnet_name
  ip_cidr_range            = var.subnet_cidr
  region                   = var.region
  network                  = google_compute_network.vpc_network.id
  private_ip_google_access = true
  project                  = var.project_id

  secondary_ip_range {
    range_name    = "gke-pods"
    ip_cidr_range = var.pods_cidr
  }

  secondary_ip_range {
    range_name    = "gke-services"
    ip_cidr_range = var.services_cidr
  }
}

# Firewall rule: Allow all intra-VPC communication (microservices, gRPC, ZooKeeper, Kafka)
resource "google_compute_firewall" "allow_internal" {
  name        = "${var.network_name}-allow-internal"
  network     = google_compute_network.vpc_network.name
  description = "Allow internal traffic between GKE pods, services, and Cloud SQL"
  project     = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = [
    var.subnet_cidr,
    var.pods_cidr,
    var.services_cidr
  ]
}

# Firewall rule: Allow Google Cloud Load Balancer health checks
resource "google_compute_firewall" "allow_health_checks" {
  name        = "${var.network_name}-allow-health-checks"
  network     = google_compute_network.vpc_network.name
  description = "Allow health checks from Google Cloud LBs"
  project     = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["80", "443", "8000-9000", "10250"]
  }

  source_ranges = [
    "35.191.0.0/16",
    "130.211.0.0/22"
  ]
}

# Firewall rule: Allow external HTTP/HTTPS traffic to Ingress controllers
resource "google_compute_firewall" "allow_public_web" {
  name        = "${var.network_name}-allow-public-web"
  network     = google_compute_network.vpc_network.name
  description = "Allow public inbound HTTP/HTTPS traffic to public web service"
  project     = var.project_id

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["gke-node", "ingress-controller"]
}

