# -*- coding: utf-8 -*-
"""Database repository for Service 3: Route Service"""

import os
import sys
import sqlite3
from typing import List, Optional, Dict, Any

sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from geometry import haversine_distance

DATABASE_URL = os.environ.get("DATABASE_URL")

class RouteRepository:
    """Manages transit route geometry, stops, and segment matrices."""

    def __init__(self, db_path: str = ":memory:"):
        self.use_sqlite = DATABASE_URL is None or "sqlite" in DATABASE_URL
        if self.use_sqlite:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._init_sqlite()
        else:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            self.pg_conn_str = DATABASE_URL
            self.RealDictCursor = RealDictCursor

    def _init_sqlite(self):
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS routes (
                    route_id TEXT PRIMARY KEY,
                    route_short_name TEXT NOT NULL,
                    route_long_name TEXT NOT NULL,
                    start_terminal TEXT NOT NULL,
                    end_terminal TEXT NOT NULL,
                    total_distance_km REAL NOT NULL,
                    nominal_transit_time_min INTEGER NOT NULL,
                    is_active INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS stops (
                    stop_id TEXT PRIMARY KEY,
                    stop_name TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    geofence_radius_meters INTEGER DEFAULT 60,
                    has_shelter INTEGER DEFAULT 1,
                    passenger_capacity INTEGER DEFAULT 50
                );

                CREATE TABLE IF NOT EXISTS route_stops (
                    route_id TEXT,
                    stop_id TEXT,
                    stop_sequence INTEGER NOT NULL,
                    expected_travel_sec_from_prev INTEGER DEFAULT 180,
                    distance_meters_from_prev INTEGER DEFAULT 1000,
                    scheduled_dwell_time_sec INTEGER DEFAULT 30,
                    PRIMARY KEY (route_id, stop_sequence)
                );
            """)

            cursor = self.conn.execute("SELECT COUNT(*) FROM routes")
            if cursor.fetchone()[0] == 0:
                # Seed Routes
                self.conn.executemany("""
                    INSERT INTO routes VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    ('ROUTE-1', '1A', 'Pilani Railway Station to BITS Main Campus', 'Pilani Station', 'BITS Clock Tower', 4.5, 15, 1),
                    ('ROUTE-2', '2B', 'Vidya Vihar Loop to Nutan Market', 'Vidya Vihar Terminal', 'Nutan Market Terminal', 8.2, 25, 1),
                    ('ROUTE-3', '3C', 'BITS Campus Express to CEERI Colony', 'BITS Student Activity Centre', 'CEERI Main Gate', 6.0, 20, 1),
                ])

                # Seed Stops
                self.conn.executemany("""
                    INSERT INTO stops VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    ('STOP-001', 'Pilani Railway Station', 28.3752, 75.6021, 60, 1, 100),
                    ('STOP-002', 'Bus Stand Circle', 28.3711, 75.5985, 50, 1, 80),
                    ('STOP-003', 'Birla Museum Stop', 28.3664, 75.5921, 50, 1, 60),
                    ('STOP-004', 'BITS Main Gate', 28.3638, 75.5872, 70, 1, 120),
                    ('STOP-005', 'BITS Clock Tower', 28.3591, 75.5879, 60, 1, 150),
                    ('STOP-006', 'Vidya Vihar Terminal', 28.3550, 75.5930, 80, 1, 100),
                    ('STOP-007', 'VFAST Guest House', 28.3580, 75.5910, 50, 1, 40),
                    ('STOP-008', 'Shiv Ganga Park', 28.3615, 75.5840, 50, 1, 50),
                    ('STOP-009', 'Nutan Market Terminal', 28.3690, 75.6050, 70, 1, 90),
                    ('STOP-010', 'CEERI Main Gate', 28.3730, 75.5810, 60, 1, 70),
                ])

                # Seed Route 1 Stops
                self.conn.executemany("""
                    INSERT INTO route_stops VALUES (?, ?, ?, ?, ?, ?)
                """, [
                    ('ROUTE-1', 'STOP-001', 1, 0, 0, 60),
                    ('ROUTE-1', 'STOP-002', 2, 240, 1100, 30),
                    ('ROUTE-1', 'STOP-003', 3, 210, 950, 30),
                    ('ROUTE-1', 'STOP-004', 4, 180, 850, 45),
                    ('ROUTE-1', 'STOP-005', 5, 150, 700, 60),
                    ('ROUTE-2', 'STOP-006', 1, 0, 0, 60),
                    ('ROUTE-2', 'STOP-007', 2, 180, 800, 30),
                    ('ROUTE-2', 'STOP-005', 3, 200, 900, 45),
                    ('ROUTE-2', 'STOP-004', 4, 150, 700, 30),
                    ('ROUTE-2', 'STOP-009', 5, 450, 2400, 60),
                ])

    def list_routes(self, active_only: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM routes WHERE 1=1"
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY route_id ASC"

        if self.use_sqlite:
            cursor = self.conn.execute(query)
            return [dict(r) for r in cursor.fetchall()]
        else:
            import psycopg2
            with psycopg2.connect(self.pg_conn_str) as conn:
                with conn.cursor(cursor_factory=self.RealDictCursor) as cur:
                    cur.execute(query)
                    return [dict(r) for r in cur.fetchall()]

    def get_route(self, route_id: str) -> Optional[Dict[str, Any]]:
        query = "SELECT * FROM routes WHERE route_id = ?" if self.use_sqlite else "SELECT * FROM routes WHERE route_id = %s"
        if self.use_sqlite:
            cursor = self.conn.execute(query, (route_id,))
            row = cursor.fetchone()
            if not row:
                return None
            route_dict = dict(row)
            route_dict["stops"] = self.get_route_stops(route_id)
            return route_dict
        else:
            import psycopg2
            with psycopg2.connect(self.pg_conn_str) as conn:
                with conn.cursor(cursor_factory=self.RealDictCursor) as cur:
                    cur.execute(query, (route_id,))
                    row = cur.fetchone()
                    if not row:
                        return None
                    route_dict = dict(row)
                    route_dict["stops"] = self.get_route_stops(route_id)
                    return route_dict

    def get_route_stops(self, route_id: str) -> List[Dict[str, Any]]:
        query = """
            SELECT rs.route_id, rs.stop_id, rs.stop_sequence, rs.expected_travel_sec_from_prev,
                   rs.distance_meters_from_prev, rs.scheduled_dwell_time_sec,
                   s.stop_name, s.latitude, s.longitude, s.geofence_radius_meters
            FROM route_stops rs
            JOIN stops s ON rs.stop_id = s.stop_id
            WHERE rs.route_id = ?
            ORDER BY rs.stop_sequence ASC
        """ if self.use_sqlite else """
            SELECT rs.route_id, rs.stop_id, rs.stop_sequence, rs.expected_travel_sec_from_prev,
                   rs.distance_meters_from_prev, rs.scheduled_dwell_time_sec,
                   s.stop_name, s.latitude, s.longitude, s.geofence_radius_meters
            FROM route_stops rs
            JOIN stops s ON rs.stop_id = s.stop_id
            WHERE rs.route_id = %s
            ORDER BY rs.stop_sequence ASC
        """
        if self.use_sqlite:
            cursor = self.conn.execute(query, (route_id,))
            return [dict(r) for r in cursor.fetchall()]
        else:
            import psycopg2
            with psycopg2.connect(self.pg_conn_str) as conn:
                with conn.cursor(cursor_factory=self.RealDictCursor) as cur:
                    cur.execute(query, (route_id,))
                    return [dict(r) for r in cur.fetchall()]

    def list_stops(self) -> List[Dict[str, Any]]:
        if self.use_sqlite:
            cursor = self.conn.execute("SELECT * FROM stops ORDER BY stop_id ASC")
            return [dict(r) for r in cursor.fetchall()]
        else:
            import psycopg2
            with psycopg2.connect(self.pg_conn_str) as conn:
                with conn.cursor(cursor_factory=self.RealDictCursor) as cur:
                    cur.execute("SELECT * FROM stops ORDER BY stop_id ASC")
                    return [dict(r) for r in cur.fetchall()]

    def find_nearest_stop(self, lat: float, lon: float, max_radius: float = 1000.0) -> Dict[str, Any]:
        stops = self.list_stops()
        if not stops:
            return {"found": False, "distance_meters": -1.0, "within_geofence": False}

        nearest_stop = None
        min_dist = float("inf")

        for s in stops:
            dist = haversine_distance(lat, lon, s["latitude"], s["longitude"])
            if dist < min_dist:
                min_dist = dist
                nearest_stop = s

        if nearest_stop and min_dist <= max_radius:
            within_geofence = min_dist <= nearest_stop.get("geofence_radius_meters", 60)
            return {
                "found": True,
                "stop_id": nearest_stop["stop_id"],
                "stop_name": nearest_stop["stop_name"],
                "distance_meters": round(min_dist, 2),
                "within_geofence": within_geofence
            }

        return {
            "found": False,
            "stop_id": nearest_stop["stop_id"] if nearest_stop else None,
            "stop_name": nearest_stop["stop_name"] if nearest_stop else None,
            "distance_meters": round(min_dist, 2) if nearest_stop else -1.0,
            "within_geofence": False
        }

repo = RouteRepository()
