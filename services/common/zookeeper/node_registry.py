# -*- coding: utf-8 -*-
"""ZooKeeper Ephemeral Node Heartbeat & Service Discovery Registry
Tracks active microservice instances and detects crashes in real time.
"""

import json
import logging
from typing import Callable, List, Dict, Any, Optional
try:
    from .zk_client import ZooKeeperClient
except ImportError:
    from zk_client import ZooKeeperClient

logger = logging.getLogger("ZooKeeper.NodeRegistry")

class EphemeralNodeRegistry:
    """Manages service discovery and liveness via ephemeral ZooKeeper znodes."""

    def __init__(self, zk_client: ZooKeeperClient, registry_root: str = "/transit/live-gateways"):
        self.zk = zk_client
        self.registry_root = registry_root
        self.my_node_path: Optional[str] = None

    def register_node(self, node_id: str, metadata: Dict[str, Any]) -> str:
        """Registers the current pod/node as an ephemeral znode with heartbeat metadata."""
        if not self.zk.exists(self.registry_root):
            try:
                self.zk.create(self.registry_root, value=b"registry-root", ephemeral=False, makepath=True)
            except Exception:
                pass

        path = f"{self.registry_root}/{node_id}"
        data_bytes = json.dumps(metadata).encode("utf-8")
        self.my_node_path = self.zk.create(path, value=data_bytes, ephemeral=True, makepath=True)
        logger.info(f"💚 Registered ephemeral heartbeat node: {self.my_node_path}")
        return self.my_node_path

    def watch_nodes(self, on_topology_changed: Callable[[List[str]], None]):
        """Watches the registry root for pod join/leave events."""
        if not self.zk.exists(self.registry_root):
            try:
                self.zk.create(self.registry_root, value=b"registry-root", ephemeral=False, makepath=True)
            except Exception:
                pass

        def _children_watch(children):
            logger.info(f"📡 [Cluster Discovery] Active cluster nodes updated: {children}")
            on_topology_changed(children)

        nodes = self.zk.get_children(self.registry_root, watch=_children_watch)
        on_topology_changed(nodes)
        return nodes

    def deregister(self):
        """Cleanly removes ephemeral registration on graceful shutdown."""
        if self.my_node_path and self.zk.exists(self.my_node_path):
            try:
                self.zk.delete(self.my_node_path)
                logger.info(f"Deregistered node: {self.my_node_path}")
            except Exception:
                pass
