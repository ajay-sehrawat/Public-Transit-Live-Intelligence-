# -*- coding: utf-8 -*-
"""Main Entrypoint for Service 1: Vehicle Registry Service
Runs both the FastAPI REST Server (port 8001) and gRPC Server (port 50051) concurrently.
"""

import os
import sys
import threading
import logging
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("VehicleRegistry.Main")

from grpc_server import create_grpc_server, HAS_GRPC
from rest_api import app

REST_PORT = int(os.environ.get("REST_PORT", 8001))
GRPC_PORT = int(os.environ.get("GRPC_PORT", 50051))

def run_grpc():
    """Runs the gRPC server in a dedicated thread."""
    server = create_grpc_server(port=GRPC_PORT)
    if HAS_GRPC and hasattr(server, 'start'):
        server.start()
        logger.info(f"[✓] gRPC Server running on 0.0.0.0:{GRPC_PORT}")
        server.wait_for_termination()
    else:
        logger.info("[✓] In-memory gRPC fallback servicer active.")

def run_rest():
    """Runs the FastAPI REST server."""
    logger.info(f"[✓] REST API running on 0.0.0.0:{REST_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=REST_PORT, log_level="info")

if __name__ == "__main__":
    logger.info("Starting Service 1: Vehicle Registry Service...")

    # Start gRPC server in background thread
    grpc_thread = threading.Thread(target=run_grpc, daemon=True)
    grpc_thread.start()

    # Start REST server in main thread
    run_rest()

