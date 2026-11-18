# -*- coding: utf-8 -*-
"""Main Entrypoint for Service 3: Route Service
Runs both the FastAPI REST Server (port 8003) and gRPC Server (port 50053) concurrently.
"""

import os
import sys
import threading
import logging

# Ensure project root and service directory in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))

from services.common.compat import run_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
)
logger = logging.getLogger("RouteService.Main")

from grpc_server import create_grpc_server, HAS_GRPC
from rest_api import app

REST_PORT = int(os.environ.get("REST_PORT", 8003))
GRPC_PORT = int(os.environ.get("GRPC_PORT", 50053))

def run_grpc():
    server = create_grpc_server(port=GRPC_PORT)
    if HAS_GRPC and hasattr(server, 'start'):
        server.start()
        logger.info(f"[✓] Route gRPC Server running on 0.0.0.0:{GRPC_PORT}")
        server.wait_for_termination()
    else:
        logger.info("[✓] In-memory Route gRPC fallback servicer active.")

def run_rest():
    logger.info(f"[✓] Route REST API running on 0.0.0.0:{REST_PORT}")
    run_server(app, host="0.0.0.0", port=REST_PORT)

if __name__ == "__main__":
    logger.info("Starting Service 3: Route Service...")

    grpc_thread = threading.Thread(target=run_grpc, daemon=True)
    grpc_thread.start()

    run_rest()

