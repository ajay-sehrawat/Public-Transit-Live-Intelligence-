# -*- coding: utf-8 -*-
"""ZooKeeper Dynamic Configuration Management & Watchers
Enables zero-downtime runtime configuration updates across microservice clusters.
"""

import json
import logging
from typing import Callable, Dict, Any, Optional
try:
    from .zk_client import ZooKeeperClient
except ImportError:
    from zk_client import ZooKeeperClient

logger = logging.getLogger("ZooKeeper.ConfigWatcher")

class DistributedConfigManager:
    """Manages distributed configurations with atomic updates and automatic watcher propagation."""

    def __init__(self, zk_client: ZooKeeperClient, config_root: str = "/transit/config"):
        self.zk = zk_client
        self.config_root = config_root
        self._cache: Dict[str, Any] = {}
        self._callbacks: Dict[str, List[Callable]] = {}

    def set_config(self, key: str, value: Any):
        """Sets or updates a dynamic configuration key in ZooKeeper."""
        path = f"{self.config_root}/{key}"
        data_bytes = json.dumps(value).encode("utf-8")

        if not self.zk.exists(path):
            self.zk.create(path, value=data_bytes, ephemeral=False, makepath=True)
            logger.info(f"Published initial distributed config: {path}")
        else:
            self.zk.set(path, data_bytes)
            logger.info(f"Updated distributed config: {path}")

    def get_config(self, key: str, default: Any = None) -> Any:
        """Retrieves config from local cache, falling back to ZooKeeper."""
        if key in self._cache:
            return self._cache[key]

        path = f"{self.config_root}/{key}"
        if self.zk.exists(path):
            data_bytes, _ = self.zk.get(path)
            try:
                val = json.loads(data_bytes.decode("utf-8"))
                self._cache[key] = val
                return val
            except Exception as e:
                logger.error(f"Error parsing config {path}: {e}")
        return default

    def watch_config(self, key: str, callback: Callable[[Any], None]):
        """Registers a distributed watcher that executes whenever the configuration key updates."""
        path = f"{self.config_root}/{key}"

        if key not in self._callbacks:
            self._callbacks[key] = []
        self._callbacks[key].append(callback)

        def _data_watcher(data, node=None):
            if data is not None:
                try:
                    val = json.loads(data.decode("utf-8") if isinstance(data, bytes) else str(data))
                    self._cache[key] = val
                    logger.info(f"🔄 [Distributed Watcher] Config '{key}' updated in ZooKeeper! Value: {val}")
                    for cb in self._callbacks.get(key, []):
                        cb(val)
                except Exception as e:
                    logger.error(f"Watcher callback error for '{key}': {e}")

        # Ensure node exists before placing watch
        if not self.zk.exists(path):
            self.zk.create(path, value=json.dumps({}).encode("utf-8"), ephemeral=False, makepath=True)

        # Place watch on the znode
        self.zk.exists(path, watch=_data_watcher)

        # Prime initial value
        initial_val = self.get_config(key)
        if initial_val is not None:
            callback(initial_val)
