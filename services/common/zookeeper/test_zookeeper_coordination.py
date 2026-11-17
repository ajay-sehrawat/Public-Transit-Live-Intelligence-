# -*- coding: utf-8 -*-
"""Comprehensive Test Suite for Domain Concept: ZooKeeper System (Requirement f)
Verifies:
  1. Active-Standby Leader Election & Instant Failover
  2. Dynamic Distributed Configuration & Live DataWatch Propagation
  3. Ephemeral Node Heartbeating & Cluster Topology Discovery
"""

import unittest
import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from services.common.zookeeper.zk_client import ZooKeeperClient, InMemoryZooKeeper
from services.common.zookeeper.leader_election import LeaderElection
from services.common.zookeeper.config_watcher import DistributedConfigManager
from services.common.zookeeper.node_registry import EphemeralNodeRegistry

class TestZooKeeperCoordination(unittest.TestCase):

    def setUp(self):
        # Reset in-memory ZooKeeper tree for clean test state
        self.tree = InMemoryZooKeeper()
        self.tree.reset()

    def test_leader_election_and_failover(self):
        """Verifies 3-node Active-Standby election and instant failover upon leader crash."""
        zk1 = ZooKeeperClient(session_id="session-node-1")
        zk2 = ZooKeeperClient(session_id="session-node-2")
        zk3 = ZooKeeperClient(session_id="session-node-3")

        leader_history = []

        def on_elected_1(): leader_history.append("node-1")
        def on_elected_2(): leader_history.append("node-2")
        def on_elected_3(): leader_history.append("node-3")

        cand1 = LeaderElection(zk1, node_id="node-1", on_elected=on_elected_1)
        cand2 = LeaderElection(zk2, node_id="node-2", on_elected=on_elected_2)
        cand3 = LeaderElection(zk3, node_id="node-3", on_elected=on_elected_3)

        # 1. Start all three candidates
        cand1.start()
        cand2.start()
        cand3.start()

        # Node 1 was first, so it MUST be the active leader
        self.assertTrue(cand1.is_leader, "Node 1 should be elected leader")
        self.assertFalse(cand2.is_leader, "Node 2 should be standby")
        self.assertFalse(cand3.is_leader, "Node 3 should be standby")
        self.assertEqual(leader_history, ["node-1"])

        # 2. Simulate Node 1 crash (session closed / process terminated)
        print("\n--- Simulating Leader (Node 1) Crash ---")
        cand1.stop()
        zk1.close()

        # Node 2 must now be promoted to Leader immediately
        self.assertFalse(cand1.is_leader)
        self.assertTrue(cand2.is_leader, "Node 2 should be promoted to leader")
        self.assertFalse(cand3.is_leader, "Node 3 should remain standby")
        self.assertEqual(leader_history, ["node-1", "node-2"])

        # 3. Simulate Node 2 crash
        print("--- Simulating Leader (Node 2) Crash ---")
        cand2.stop()
        zk2.close()

        # Node 3 must now be promoted to Leader
        self.assertTrue(cand3.is_leader, "Node 3 should be promoted to leader")
        self.assertEqual(leader_history, ["node-1", "node-2", "node-3"])

        cand3.stop()
        zk3.close()

    def test_dynamic_configuration_watchers(self):
        """Verifies that updating a config znode propagates to all worker watchers."""
        zk_admin = ZooKeeperClient(session_id="admin-session")
        zk_worker_1 = ZooKeeperClient(session_id="worker-1")
        zk_worker_2 = ZooKeeperClient(session_id="worker-2")

        admin_cfg = DistributedConfigManager(zk_admin)
        worker1_cfg = DistributedConfigManager(zk_worker_1)
        worker2_cfg = DistributedConfigManager(zk_worker_2)

        received_worker1 = []
        received_worker2 = []

        # Register watchers on worker nodes
        worker1_cfg.watch_config("active-routes", lambda val: received_worker1.append(val))
        worker2_cfg.watch_config("active-routes", lambda val: received_worker2.append(val))

        # Admin publishes route configuration update
        update_payload = {
            "routes": ["ROUTE-1", "ROUTE-2"],
            "emergency_detour_active": False,
            "max_fleet_speed_kmh": 45.0
        }
        admin_cfg.set_config("active-routes", update_payload)

        # Both workers should receive the exact live configuration
        self.assertEqual(worker1_cfg.get_config("active-routes"), update_payload)
        self.assertEqual(worker2_cfg.get_config("active-routes"), update_payload)
        self.assertIn(update_payload, received_worker1)
        self.assertIn(update_payload, received_worker2)

        # Admin updates config again with emergency speed restriction
        update_payload_2 = {
            "routes": ["ROUTE-1"],
            "emergency_detour_active": True,
            "max_fleet_speed_kmh": 25.0
        }
        admin_cfg.set_config("active-routes", update_payload_2)

        self.assertEqual(worker1_cfg.get_config("active-routes"), update_payload_2)
        self.assertEqual(worker2_cfg.get_config("active-routes"), update_payload_2)

        zk_admin.close()
        zk_worker_1.close()
        zk_worker_2.close()

    def test_ephemeral_node_heartbeat_registry(self):
        """Verifies that edge gateway nodes register heartbeats and disconnects are detected."""
        zk_coord = ZooKeeperClient(session_id="coord-session")
        zk_gw1 = ZooKeeperClient(session_id="gw1-session")
        zk_gw2 = ZooKeeperClient(session_id="gw2-session")

        coord_registry = EphemeralNodeRegistry(zk_coord)
        gw1_registry = EphemeralNodeRegistry(zk_gw1)
        gw2_registry = EphemeralNodeRegistry(zk_gw2)

        cluster_snapshots = []
        coord_registry.watch_nodes(lambda nodes: cluster_snapshots.append(list(nodes)))

        # Register gateways
        gw1_registry.register_node("gw-pod-1", {"ip": "10.20.1.15", "port": 8002})
        gw2_registry.register_node("gw-pod-2", {"ip": "10.20.1.16", "port": 8002})

        # Latest cluster snapshot must have both pods
        latest_nodes = cluster_snapshots[-1]
        self.assertIn("gw-pod-1", latest_nodes)
        self.assertIn("gw-pod-2", latest_nodes)

        # Simulate gw-pod-1 network failure / crash
        zk_gw1.close()

        # Coordinator should now observe that gw-pod-1 has vanished
        latest_nodes_after_crash = cluster_snapshots[-1]
        self.assertNotIn("gw-pod-1", latest_nodes_after_crash)
        self.assertIn("gw-pod-2", latest_nodes_after_crash)

        zk_coord.close()
        zk_gw2.close()

if __name__ == "__main__":
    unittest.main()

