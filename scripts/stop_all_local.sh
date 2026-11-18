#!/usr/bin/env bash
# ==============================================================================
# S11 Public Transportation — Stop All Local Services
# Cleanly terminates all background transit microservices
# ==============================================================================

LOG_DIR="/tmp/transit_logs"
PID_FILE="$LOG_DIR/transit.pids"

echo "======================================================================"
echo "  STOPPING ALL LOCAL S11 TRANSIT SERVICES"
echo "======================================================================"

if [ -f "$PID_FILE" ]; then
    while read -r pid; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo -n "[*] Stopping PID $pid... "
            kill "$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
            echo "Terminated."
        fi
    done < "$PID_FILE"
    rm -f "$PID_FILE"
fi

# Clean up any lingering transit port bindings (8080, 8001, 8002, 8003, 8004, 8006)
for port in 8080 8001 8002 8003 8004 8006; do
    pid=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        echo -n "[*] Cleaning up lingering process on port $port (PID: $pid)... "
        kill -9 "$pid" 2>/dev/null || true
        echo "Done."
    fi
done

echo ""
echo "[✓] All local transit microservices stopped cleanly."
echo "======================================================================"
