-- ==============================================================================
-- S11 Public Transportation: Relational PostgreSQL Schema (Cloud SQL)
-- Powers: Service 1 (Vehicle Registry) & Service 3 (Route Service)
-- ==============================================================================

-- Drop tables if resetting
DROP TABLE IF EXISTS trip_schedules CASCADE;
DROP TABLE IF EXISTS route_stops CASCADE;
DROP TABLE IF EXISTS stops CASCADE;
DROP TABLE IF EXISTS routes CASCADE;
DROP TABLE IF EXISTS vehicles CASCADE;

-- ------------------------------------------------------------------------------
-- 1. VEHICLE REGISTRY TABLE (Service 1)
-- ------------------------------------------------------------------------------
CREATE TABLE vehicles (
    bus_id VARCHAR(50) PRIMARY KEY,
    license_plate VARCHAR(30) NOT NULL UNIQUE,
    model VARCHAR(50) NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    propulsion_type VARCHAR(20) DEFAULT 'ELECTRIC', -- ELECTRIC, DIESEL, HYBRID, CNG
    status VARCHAR(20) DEFAULT 'ACTIVE',            -- ACTIVE, MAINTENANCE, RETIRED, OUT_OF_SERVICE
    assigned_route_id VARCHAR(50),
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_vehicles_status ON vehicles(status);
CREATE INDEX idx_vehicles_route ON vehicles(assigned_route_id);

-- ------------------------------------------------------------------------------
-- 2. TRANSIT ROUTES TABLE (Service 3)
-- ------------------------------------------------------------------------------
CREATE TABLE routes (
    route_id VARCHAR(50) PRIMARY KEY,
    route_short_name VARCHAR(20) NOT NULL,
    route_long_name VARCHAR(150) NOT NULL,
    start_terminal VARCHAR(100) NOT NULL,
    end_terminal VARCHAR(100) NOT NULL,
    total_distance_km NUMERIC(6, 2) NOT NULL,
    nominal_transit_time_min INT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- 3. TRANSIT STOPS TABLE (Service 3)
-- ------------------------------------------------------------------------------
CREATE TABLE stops (
    stop_id VARCHAR(50) PRIMARY KEY,
    stop_name VARCHAR(120) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geofence_radius_meters INT DEFAULT 60, -- Radius within which a bus is considered "Arrived"
    has_shelter BOOLEAN DEFAULT TRUE,
    passenger_capacity INT DEFAULT 50,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stops_coords ON stops(latitude, longitude);

-- ------------------------------------------------------------------------------
-- 4. ROUTE STOPS & EXPECTED SEGMENTS (Service 3)
-- ------------------------------------------------------------------------------
CREATE TABLE route_stops (
    route_id VARCHAR(50) REFERENCES routes(route_id) ON DELETE CASCADE,
    stop_id VARCHAR(50) REFERENCES stops(stop_id) ON DELETE RESTRICT,
    stop_sequence INT NOT NULL CHECK (stop_sequence > 0),
    expected_travel_sec_from_prev INT DEFAULT 180,  -- Nominal runtime in seconds
    distance_meters_from_prev INT DEFAULT 1000,     -- Segment distance in meters
    scheduled_dwell_time_sec INT DEFAULT 30,        -- Waiting time at the stop
    PRIMARY KEY (route_id, stop_sequence)
);

CREATE INDEX idx_route_stops_route ON route_stops(route_id);

-- ------------------------------------------------------------------------------
-- 5. SCHEDULED TIMETABLE / TRIPS TABLE (Service 3)
-- ------------------------------------------------------------------------------
CREATE TABLE trip_schedules (
    trip_id VARCHAR(50) PRIMARY KEY,
    route_id VARCHAR(50) REFERENCES routes(route_id) ON DELETE CASCADE,
    bus_id VARCHAR(50) REFERENCES vehicles(bus_id) ON DELETE SET NULL,
    scheduled_start_time TIME NOT NULL,
    direction VARCHAR(10) DEFAULT 'OUTBOUND', -- OUTBOUND, INBOUND
    day_of_week VARCHAR(20) DEFAULT 'WEEKDAY'
);

