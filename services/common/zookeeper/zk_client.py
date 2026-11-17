# -*- coding: utf-8 -*-
"""ZooKeeper Client & In-Memory Distributed Tree Simulator
Provides real ZooKeeper integration via 'kazoo' and an in-memory fallback simulator.
"""

import os
import time
import logging
import threading
from typing import Callable, Dict, List, Optional, Any

logger = logging.getLogger("ZooKeeperClient")

try:
    from kazoo.client import KazooClient
    from kazoo.recipe.election import Election
    from kazoo.recipe.watchers import DataWatch, ChildrenWatch
    HAS_KAZOO = True
except ImportError:
    HAS_KAZOO = False


class ZNode:
    """Represents a ZooKeeper znode with data, metadata, and watchers."""

    def __init__(self, path: str, data: bytes = b"", ephemeral: bool = False, session_id: Optional[str] = None):
        self.path = path
        self.data = data
        self.ephemeral = ephemeral
        self.session_id = session_id
        self.version = 0
        self.ctime = time.time()
        self.mtime = time.time()
        self.children: Dict[str, "ZNode"] = {}
        self.data_watchers: List[Callable] = []
        self.child_watchers: List[Callable] = []

    def notify_data_changed(self):
        for watcher in list(self.data_watchers):
            try:
                watcher(self.data, self)
            except Exception as e:
                logger.error(f"Error in data watcher for {self.path}: {e}")

    def notify_children_changed(self):
        child_names = list(self.children.keys())
        for watcher in list(self.child_watchers):
            try:
                watcher(child_names)
            except Exception as e:
                logger.error(f"Error in child watcher for {self.path}: {e}")


class InMemoryZooKeeper:
    """In-Memory ZooKeeper Tree supporting Ephemeral nodes, Sequential counters, and Watchers."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(InMemoryZooKeeper, cls).__new__(cls)
                cls._instance._init_tree()
            return cls._instance

    def _init_tree(self):
        self.root = ZNode("/")
        self.sequence_counters: Dict[str, int] = {}
        self.sessions: Dict[str, List[str]] = {}  # session_id -> list of ephemeral paths
        self.lock = threading.RLock()

    def reset(self):
        with self.lock:
            self._init_tree()

    def _normalize_path(self, path: str) -> str:
        return "/" + "/".join([p for p in path.split("/") if p])

    def _find_node(self, path: str) -> Optional[ZNode]:
        path = self._normalize_path(path)
        if path == "/":
            return self.root

        parts = path.strip("/").split("/")
        curr = self.root
        for part in parts:
            if part not in curr.children:
                return None
            curr = curr.children[part]
        return curr

    def create(self, path: str, value: bytes = b"", ephemeral: bool = False,
               sequence: bool = False, makepath: bool = True, session_id: str = "default") -> str:
        with self.lock:
            path = self._normalize_path(path)
            parts = path.strip("/").split("/")
            parent_path = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"
            node_name = parts[-1]

            parent = self._find_node(parent_path)
            if not parent:
                if makepath:
                    self.create(parent_path, value=b"", ephemeral=False, sequence=False, makepath=True, session_id=session_id)
                    parent = self._find_node(parent_path)
                else:
                    raise KeyError(f"Parent path {parent_path} does not exist")

            if sequence:
                counter = self.sequence_counters.get(parent_path, 0) + 1
                self.sequence_counters[parent_path] = counter
                node_name = f"{node_name}{counter:010d}"

            final_path = self._normalize_path(f"{parent_path}/{node_name}")
            node = ZNode(final_path, data=value, ephemeral=ephemeral, session_id=session_id)
            parent.children[node_name] = node

            if ephemeral:
                if session_id not in self.sessions:
                    self.sessions[session_id] = []
                self.sessions[session_id].append(final_path)

            parent.notify_children_changed()
            return final_path

    def get(self, path: str) -> tuple:
        with self.lock:
            node = self._find_node(path)
            if not node:
                raise KeyError(f"ZNode {path} does not exist")
            return (node.data, node)

    def set(self, path: str, value: bytes):
        with self.lock:
            node = self._find_node(path)
            if not node:
                raise KeyError(f"ZNode {path} does not exist")
            node.data = value
            node.version += 1
            node.mtime = time.time()
            node.notify_data_changed()

    def delete(self, path: str, recursive: bool = False):
        with self.lock:
            path = self._normalize_path(path)
            parts = path.strip("/").split("/")
            if not parts or path == "/":
                return

            parent_path = "/" + "/".join(parts[:-1]) if len(parts) > 1 else "/"
            node_name = parts[-1]

            parent = self._find_node(parent_path)
            if not parent or node_name not in parent.children:
                return

            node = parent.children[node_name]
            if node.children and not recursive:
                raise ValueError(f"ZNode {path} has children")

            del parent.children[node_name]
            parent.notify_children_changed()

    def get_children(self, path: str, watch: Optional[Callable] = None) -> List[str]:
        with self.lock:
            node = self._find_node(path)
            if not node:
                raise KeyError(f"ZNode {path} does not exist")
            if watch and watch not in node.child_watchers:
                node.child_watchers.append(watch)
            return sorted(list(node.children.keys()))

    def exists(self, path: str, watch: Optional[Callable] = None) -> bool:
        with self.lock:
            node = self._find_node(path)
            if node and watch and watch not in node.data_watchers:
                node.data_watchers.append(watch)
            return node is not None

    def close_session(self, session_id: str):
        """Simulates client disconnect or node crash: removes all ephemeral nodes created by session."""
        with self.lock:
            paths_to_delete = list(self.sessions.get(session_id, []))
            for path in sorted(paths_to_delete, reverse=True):
                try:
                    self.delete(path)
                except Exception as e:
                    logger.debug(f"Error cleaning ephemeral node {path}: {e}")
            if session_id in self.sessions:
                del self.sessions[session_id]


class ZooKeeperClient:
    """Unified ZooKeeper client providing clean APIs for election, config, and registry."""

    def __init__(self, hosts: Optional[str] = None, session_id: Optional[str] = None):
        self.hosts = hosts or os.environ.get("ZOOKEEPER_HOSTS", "localhost:2181")
        self.session_id = session_id or f"session-{os.getpid()}-{int(time.time()*1000)}"
        self.kazoo = None
        self.in_memory = None

        if HAS_KAZOO and "localhost" not in self.hosts:
            try:
                self.kazoo = KazooClient(hosts=self.hosts, timeout=5.0)
                self.kazoo.start(timeout=3.0)
                logger.info(f"[✓] Connected to live ZooKeeper ensemble at {self.hosts}")
            except Exception as e:
                logger.warning(f"Failed to connect to live ZooKeeper at {self.hosts}: {e}. Using in-memory engine.")
                self.in_memory = InMemoryZooKeeper()
        else:
            self.in_memory = InMemoryZooKeeper()

    def create(self, path: str, value: bytes = b"", ephemeral: bool = False,
               sequence: bool = False, makepath: bool = True) -> str:
        if self.kazoo:
            return self.kazoo.create(path, value, ephemeral=ephemeral, sequence=sequence, makepath=makepath)
        return self.in_memory.create(path, value, ephemeral=ephemeral, sequence=sequence,
                                     makepath=makepath, session_id=self.session_id)

    def get(self, path: str) -> tuple:
        if self.kazoo:
            data, stat = self.kazoo.get(path)
            return data, stat
        return self.in_memory.get(path)

    def set(self, path: str, value: bytes):
        if self.kazoo:
            return self.kazoo.set(path, value)
        return self.in_memory.set(path, value)

    def get_children(self, path: str, watch: Optional[Callable] = None) -> List[str]:
        if self.kazoo:
            return self.kazoo.get_children(path, watch=watch)
        return self.in_memory.get_children(path, watch=watch)

    def exists(self, path: str, watch: Optional[Callable] = None) -> bool:
        if self.kazoo:
            return self.kazoo.exists(path, watch=watch) is not None
        return self.in_memory.exists(path, watch=watch)

    def delete(self, path: str, recursive: bool = False):
        if self.kazoo:
            return self.kazoo.delete(path, recursive=recursive)
        return self.in_memory.delete(path, recursive=recursive)

    def close(self):
        """Closes the client session, cleaning up ephemeral znodes."""
        if self.kazoo:
            try:
                self.kazoo.stop()
                self.kazoo.close()
            except Exception:
                pass
        if self.in_memory:
            self.in_memory.close_session(self.session_id)

