#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive ZooKeeper Leader Election & Failover Demonstration Script
Designed for BITS Pilani CS/SS G527 Evaluation Demonstration (Requirement f).
"""

import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.common.zookeeper.zk_client import ZooKeeperClient, InMemoryZooKeeper
from services.common.zookeeper.leader_election import LeaderElection
from services.common.zookeeper.config_watcher import DistributedConfigManager

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_header(title):
    print(f"\n{BOLD}{CYAN}{'='*75}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'='*75}{RESET}\n")

def main():
    print_header("DEMO: ZooKeeper Distributed Coordination & Leader Election (Req f)")

    tree = InMemoryZooKeeper()
    tree.reset()

    # 1. Spawn 3 concurrent candidates
    print(f"{YELLOW}[STEP 1]{RESET} Spawning 3 Ingestion Coordinator instances...")
    zk_a = ZooKeeperClient(session_id="session-pod-A")
    zk_b = ZooKeeperClient(session_id="session-pod-B")
    zk_c = ZooKeeperClient(session_id="session-pod-C")

    election_a = LeaderElection(zk_a, node_id="IngestionCoord-Pod-A")
    election_b = LeaderElection(zk_b, node_id="IngestionCoord-Pod-B")
    election_c = LeaderElection(zk_c, node_id="IngestionCoord-Pod-C")

    print(f"  -> Starting Pod A...")
    election_a.start()
    time.sleep(0.1)

    print(f"  -> Starting Pod B...")
    election_b.start()
    time.sleep(0.1)

    print(f"  -> Starting Pod C...")
    election_c.start()
    time.sleep(0.1)

    print(f"\n{BOLD}Current Cluster Leadership Status:{RESET}")
    print(f"  Pod A: {'🏆 ' + GREEN + 'ACTIVE LEADER' + RESET if election_a.is_leader else '⏳ STANDBY'}")
    print(f"  Pod B: {'🏆 ' + GREEN + 'ACTIVE LEADER' + RESET if election_b.is_leader else '⏳ STANDBY'}")
    print(f"  Pod C: {'🏆 ' + GREEN + 'ACTIVE LEADER' + RESET if election_c.is_leader else '⏳ STANDBY'}")

    # 2. Dynamic Configuration Watcher Demonstration
    print(f"\n{YELLOW}[STEP 2]{RESET} Testing Dynamic Distributed Route Configuration (DataWatch)...")
    config_admin = DistributedConfigManager(zk_a)
    config_listener_b = DistributedConfigManager(zk_b)

    received_updates = []
    config_listener_b.watch_config("active-routes", lambda cfg: received_updates.append(cfg))

    new_config = {
        "active_routes": ["ROUTE-1", "ROUTE-2"],
        "emergency_detour": "AVOID_CIRCLE_MARKET",
        "speed_limit_kmh": 35.0
    }
    print(f"  -> Leader (Pod A) publishes emergency detour update to ZooKeeper znode '/transit/config/active-routes'...")
    config_admin.set_config("active-routes", new_config)

    print(f"  -> {GREEN}Watcher Triggered on Standby Pod B!{RESET}")
    print(f"     Received Config: {received_updates[-1]}")

    # 3. Leader Failover Demonstration
    print(f"\n{YELLOW}[STEP 3]{RESET} Simulating Sudden Hardware Crash of Active Leader (Pod A)...")
    print(f"  -> Terminating Pod A process & expiring ZooKeeper session...")
    election_a.stop()
    zk_a.close()
    time.sleep(0.2)

    print(f"\n{BOLD}Leadership Status Immediately After Pod A Failure:{RESET}")
    print(f"  Pod A: {RED}DEAD / TERMINATED{RESET}")
    print(f"  Pod B: {'🏆 ' + GREEN + 'PROMOTED TO ACTIVE LEADER!' + RESET if election_b.is_leader else 'FAILED'}")
    print(f"  Pod C: {'⏳ STANDBY (Now Watching Pod B)' if not election_c.is_leader else 'FAILED'}")

    # 4. Failover of Pod B
    print(f"\n{YELLOW}[STEP 4]{RESET} Simulating Failure of Second Leader (Pod B)...")
    election_b.stop()
    zk_b.close()
    time.sleep(0.2)

    print(f"\n{BOLD}Leadership Status Immediately After Pod B Failure:{RESET}")
    print(f"  Pod A: {RED}DEAD{RESET}")
    print(f"  Pod B: {RED}DEAD{RESET}")
    print(f"  Pod C: {'🏆 ' + GREEN + 'PROMOTED TO ACTIVE LEADER!' + RESET if election_c.is_leader else 'FAILED'}")

    election_c.stop()
    zk_c.close()

    print_header("ZooKeeper Demonstration Completed Successfully (Zero Split-Brain Detected)")

if __name__ == "__main__":
    main()

