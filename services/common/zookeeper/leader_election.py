# -*- coding: utf-8 -*-
"""ZooKeeper Distributed Leader Election Recipe
Implements Active-Standby coordination with sequential ephemeral znodes and failure recovery.
"""

import logging
import threading
from typing import Callable, Optional
try:
    from .zk_client import ZooKeeperClient
except ImportError:
    from zk_client import ZooKeeperClient

logger = logging.getLogger("ZooKeeper.LeaderElection")

class LeaderElection:
    """Manages active-standby leader election for a distributed microservice instance."""

    def __init__(self,
                 zk_client: ZooKeeperClient,
                 election_path: str = "/transit/election",
                 node_id: Optional[str] = None,
                 on_elected: Optional[Callable] = None,
                 on_revoked: Optional[Callable] = None):
        self.zk = zk_client
        self.election_path = election_path
        self.node_id = node_id or f"node-{id(self)}"
        self.on_elected = on_elected
        self.on_revoked = on_revoked

        self.my_znode_path: Optional[str] = None
        self.my_znode_name: Optional[str] = None
        self.is_leader: bool = False
        self.is_running: bool = False
        self.lock = threading.Lock()

    def start(self):
        """Enters the leader election race."""
        with self.lock:
            self.is_running = True

            # Ensure election root znode exists
            if not self.zk.exists(self.election_path):
                try:
                    self.zk.create(self.election_path, value=b"election-root", ephemeral=False, makepath=True)
                except Exception:
                    pass

            # Create ephemeral sequential znode
            candidate_prefix = f"{self.election_path}/guid-{self.node_id}_"
            self.my_znode_path = self.zk.create(
                candidate_prefix,
                value=self.node_id.encode("utf-8"),
                ephemeral=True,
                sequence=True
            )
            self.my_znode_name = self.my_znode_path.split("/")[-1]
            logger.info(f"[{self.node_id}] Registered election candidate node: {self.my_znode_name}")

            self._evaluate_election()

    def _evaluate_election(self):
        """Inspects all candidate znodes to determine leadership or set standby watch."""
        if not self.is_running:
            return

        children = self.zk.get_children(self.election_path, watch=self._on_children_changed)
        children.sort()

        if not children:
            return

        leader_node = children[0]
        if leader_node == self.my_znode_name:
            if not self.is_leader:
                self.is_leader = True
                logger.info(f"🏆 [{self.node_id}] ELECTED AS ACTIVE LEADER! (ZNode: {self.my_znode_name})")
                if self.on_elected:
                    try:
                        self.on_elected()
                    except Exception as e:
                        logger.error(f"Error in on_elected callback: {e}")
        else:
            # Standby mode
            if self.is_leader:
                self.is_leader = False
                logger.warning(f"[{self.node_id}] Leadership revoked.")
                if self.on_revoked:
                    try:
                        self.on_revoked()
                    except Exception as e:
                        logger.error(f"Error in on_revoked callback: {e}")

            # Watch the node immediately preceding this node to avoid herd effect
            my_index = children.index(self.my_znode_name)
            preceding_node = children[my_index - 1]
            preceding_path = f"{self.election_path}/{preceding_node}"

            logger.info(f"⏳ [{self.node_id}] STANDBY REPLICA. Watching preceding node: {preceding_node}")
            self.zk.exists(preceding_path, watch=self._on_preceding_node_deleted)

    def _on_children_changed(self, children):
        """Triggered when nodes join or leave the election."""
        if self.is_running:
            self._evaluate_election()

    def _on_preceding_node_deleted(self, data, node=None):
        """Triggered when the preceding node in sequence fails or leaves."""
        logger.info(f"🔔 [{self.node_id}] Preceding node deleted! Re-evaluating leadership...")
        if self.is_running:
            self._evaluate_election()

    def stop(self):
        """Leaves the election and releases leadership if held."""
        with self.lock:
            self.is_running = False
            was_leader = self.is_leader
            self.is_leader = False

            if was_leader and self.on_revoked:
                try:
                    self.on_revoked()
                except Exception:
                    pass

            if self.my_znode_path and self.zk.exists(self.my_znode_path):
                try:
                    self.zk.delete(self.my_znode_path)
                except Exception:
                    pass
            logger.info(f"[{self.node_id}] Left leader election.")
