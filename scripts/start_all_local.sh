#!/usr/bin/env bash
# ==============================================================================
# S11 Public Transportation — Local Multi-Microservice Runner
# Starts all transit services locally in the background and logs to /tmp/transit_logs
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="/tmp/transit_logs"
PID_FILE="$LOG_DIR/transit.pids"

mkdir -p "$LOG_DIR"
rm -f "$PID_FILE"

echo "======================================================================"
echo "  STARTING S11 PUBLIC TRANSIT INTELLIGENCE PLATFORM (LOCAL MODE)"
echo "======================================================================"

# Function to launch a service
launch_service() {
    local name="$1"
    local entrypoint="$2"
    local port="$3"
    local logfile="$LOG_DIR/$name.log"

    echo -n "[*] Starting $name on port $port... "
    python3 "$PROJECT_ROOT/$entrypoint" > "$logfile" 2>&1 &
    local pid=$!
    echo "$pid" >> "$PID_FILE"
    echo "Started (PID: $pid, Log: $logfile)"
}

# 1. Service 1: Vehicle Registry (Port 8001 & gRPC 50051)
launch_service "01-vehicle-registry" "services/01-vehicle-registry/main.py" "8001"

# 2. Service 3: Route Service (Port 8003 & gRPC 50053)
launch_service "03-route-service" "services/03-route-service/main.py" "8003"

# 3. Service 2: GPS Ingestion Service (Port 8002)
launch_service "02-gps-ingestion" "services/02-gps-ingestion/main.py" "8002"

# 4. Service 4: Event Adapter (Port 8004)
launch_service "04-event-adapter" "services/04-event-adapter/main.py" "8004"

# 5. Service 6: Passenger Demand Service (Port 8006)
launch_service "06-passenger-demand" "services/06-passenger-demand/main.py" "8006"

# 6. Service 8: Transport Analytics Public Web Dashboard (Port 8080)
launch_service "08-transport-analytics" "services/08-transport-analytics/main.py" "8080"

sleep 1.5

echo ""
echo "======================================================================"
echo "  [✓] ALL LOCAL SERVICES STARTED SUCCESSFULLY!"
echo "======================================================================"
echo "  🌐 Public Web Dashboard:    http://localhost:8080/"
echo "  🚗 Vehicle Registry API:    http://localhost:8001/api/v1/vehicles"
echo "  📍 GPS Ingestion API:       http://localhost:8002/health"
echo "  🗺️  Route Service API:        http://localhost:8003/api/v1/routes"
echo "  ⚙️  Event Adapter API:        http://localhost:8004/health"
echo "  👥 Passenger Demand API:    http://localhost:8006/health"
echo "======================================================================"
echo "  To check live health:       python3 scripts/check_status.py"
echo "  To stop all services:       ./scripts/stop_all_local.sh"
echo "======================================================================"
