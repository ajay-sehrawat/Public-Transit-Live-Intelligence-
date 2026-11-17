# -*- coding: utf-8 -*-
"""Database connection and repository for Service 1: Vehicle Registry"""

import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any

# PostgreSQL connection string from environment (e.g., from Cloud SQL or Docker Compose)
DATABASE_URL = os.environ.get("DATABASE_URL")

class VehicleRepository:
    """Repository managing vehicle fleet records with PostgreSQL/SQLite support."""

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
            self._init_postgres()

    def _init_sqlite(self):
        """Initializes SQLite tables and seeds baseline fleet data."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS vehicles (
                    bus_id TEXT PRIMARY KEY,
                    license_plate TEXT NOT NULL UNIQUE,
                    model TEXT NOT NULL,
                    capacity INTEGER NOT NULL,
                    propulsion_type TEXT DEFAULT 'ELECTRIC',
                    status TEXT DEFAULT 'ACTIVE',
                    assigned_route_id TEXT,
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Insert baseline seed data if empty
            cursor = self.conn.execute("SELECT COUNT(*) FROM vehicles")
            if cursor.fetchone()[0] == 0:
                self.conn.executemany("""
                    INSERT INTO vehicles (bus_id, license_plate, model, capacity, propulsion_type, status, assigned_route_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [
                    ('BUS-101', 'RJ-18-PA-0101', 'Tata Starbus EV', 45, 'ELECTRIC', 'ACTIVE', 'ROUTE-1'),
                    ('BUS-102', 'RJ-18-PA-0102', 'Tata Starbus EV', 45, 'ELECTRIC', 'ACTIVE', 'ROUTE-1'),
                    ('BUS-103', 'RJ-18-PA-0103', 'Ashok Leyland Electric', 50, 'ELECTRIC', 'ACTIVE', 'ROUTE-1'),
                    ('BUS-201', 'RJ-18-PB-0201', 'Volvo 9400 LowFloor', 60, 'DIESEL', 'ACTIVE', 'ROUTE-2'),
                    ('BUS-202', 'RJ-18-PB-0202', 'Volvo 9400 LowFloor', 60, 'DIESEL', 'ACTIVE', 'ROUTE-2'),
                    ('BUS-301', 'RJ-18-PC-0301', 'Eicher Skyline Pro', 35, 'CNG', 'ACTIVE', 'ROUTE-3'),
                    ('BUS-302', 'RJ-18-PC-0302', 'Eicher Skyline Pro', 35, 'CNG', 'MAINTENANCE', 'ROUTE-3'),
                    ('BUS-401', 'RJ-18-PD-0401', 'Tata Ultra Urban', 40, 'ELECTRIC', 'ACTIVE', 'ROUTE-2'),
                ])

    def _init_postgres(self):
        """Validates connection to Cloud SQL PostgreSQL."""
        pass

    def get_vehicle(self, bus_id: str) -> Optional[Dict[str, Any]]:
        if self.use_sqlite:
            cursor = self.conn.execute("SELECT * FROM vehicles WHERE bus_id = ?", (bus_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        else:
            import psycopg2
            with psycopg2.connect(self.pg_conn_str) as conn:
                with conn.cursor(cursor_factory=self.RealDictCursor) as cur:
                    cur.execute("SELECT * FROM vehicles WHERE bus_id = %s", (bus_id,))
                    row = cur.fetchone()
                    return dict(row) if row else None

    def list_vehicles(self, status: Optional[str] = None, route_id: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM vehicles WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?" if self.use_sqlite else " AND status = %s"
            params.append(status)
        if route_id:
            query += " AND assigned_route_id = ?" if self.use_sqlite else " AND assigned_route_id = %s"
            params.append(route_id)
        query += " ORDER BY bus_id ASC"

        if self.use_sqlite:
            cursor = self.conn.execute(query, tuple(params))
            return [dict(r) for r in cursor.fetchall()]
        else:
            import psycopg2
            with psycopg2.connect(self.pg_conn_str) as conn:
                with conn.cursor(cursor_factory=self.RealDictCursor) as cur:
                    cur.execute(query, tuple(params))
                    return [dict(r) for r in cur.fetchall()]

    def create_vehicle(self, vehicle: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.utcnow().isoformat()
        if self.use_sqlite:
            with self.conn:
                self.conn.execute("""
                    INSERT INTO vehicles (bus_id, license_plate, model, capacity, propulsion_type, status, assigned_route_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vehicle['bus_id'], vehicle['license_plate'], vehicle['model'],
                    vehicle['capacity'], vehicle.get('propulsion_type', 'ELECTRIC'),
                    vehicle.get('status', 'ACTIVE'), vehicle.get('assigned_route_id'),
                    now, now
                ))
            return self.get_vehicle(vehicle['bus_id'])
        else:
            import psycopg2
            with psycopg2.connect(self.pg_conn_str) as conn:
                with conn.cursor(cursor_factory=self.RealDictCursor) as cur:
                    cur.execute("""
                        INSERT INTO vehicles (bus_id, license_plate, model, capacity, propulsion_type, status, assigned_route_id, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING *;
                    """, (
                        vehicle['bus_id'], vehicle['license_plate'], vehicle['model'],
                        vehicle['capacity'], vehicle.get('propulsion_type', 'ELECTRIC'),
                        vehicle.get('status', 'ACTIVE'), vehicle.get('assigned_route_id'),
                        now, now
                    ))
                    conn.commit()
                    return dict(cur.fetchone())

    def update_vehicle(self, bus_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        now = datetime.utcnow().isoformat()
        fields = [f"{k} = ?" for k in updates.keys() if updates[k] is not None] if self.use_sqlite else [f"{k} = %s" for k in updates.keys() if updates[k] is not None]
        if not fields:
            return self.get_vehicle(bus_id)

        values = [v for v in updates.values() if v is not None]
        fields.append("updated_at = ?" if self.use_sqlite else "updated_at = %s")
        values.append(now)
        values.append(bus_id)

        set_clause = ", ".join(fields)
        query = f"UPDATE vehicles SET {set_clause} WHERE bus_id = {'?' if self.use_sqlite else '%s'}"

        if self.use_sqlite:
            with self.conn:
                self.conn.execute(query, tuple(values))
            return self.get_vehicle(bus_id)
        else:
            import psycopg2
            with psycopg2.connect(self.pg_conn_str) as conn:
                with conn.cursor(cursor_factory=self.RealDictCursor) as cur:
                    cur.execute(query, tuple(values))
                    conn.commit()
            return self.get_vehicle(bus_id)

    def delete_vehicle(self, bus_id: str) -> bool:
        if self.use_sqlite:
            with self.conn:
                cursor = self.conn.execute("DELETE FROM vehicles WHERE bus_id = ?", (bus_id,))
                return cursor.rowcount > 0
        else:
            import psycopg2
            with psycopg2.connect(self.pg_conn_str) as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM vehicles WHERE bus_id = %s", (bus_id,))
                    conn.commit()
                    return cur.rowcount > 0

# Shared repository singleton
repo = VehicleRepository()
