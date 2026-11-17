-- ==============================================================================
-- Realistic Seed Data for S11 Public Transportation System
-- Scenario: Campus & Smart City Transit Routes
-- ==============================================================================

-- 1. Seed Vehicles
INSERT INTO vehicles (bus_id, license_plate, model, capacity, propulsion_type, status, assigned_route_id) VALUES
('BUS-101', 'RJ-18-PA-0101', 'Tata Starbus EV', 45, 'ELECTRIC', 'ACTIVE', 'ROUTE-1'),
('BUS-102', 'RJ-18-PA-0102', 'Tata Starbus EV', 45, 'ELECTRIC', 'ACTIVE', 'ROUTE-1'),
('BUS-103', 'RJ-18-PA-0103', 'Ashok Leyland Electric', 50, 'ELECTRIC', 'ACTIVE', 'ROUTE-1'),
('BUS-201', 'RJ-18-PB-0201', 'Volvo 9400 LowFloor', 60, 'DIESEL', 'ACTIVE', 'ROUTE-2'),
('BUS-202', 'RJ-18-PB-0202', 'Volvo 9400 LowFloor', 60, 'DIESEL', 'ACTIVE', 'ROUTE-2'),
('BUS-301', 'RJ-18-PC-0301', 'Eicher Skyline Pro', 35, 'CNG', 'ACTIVE', 'ROUTE-3'),
('BUS-302', 'RJ-18-PC-0302', 'Eicher Skyline Pro', 35, 'CNG', 'MAINTENANCE', 'ROUTE-3'),
('BUS-401', 'RJ-18-PD-0401', 'Tata Ultra Urban', 40, 'ELECTRIC', 'ACTIVE', 'ROUTE-2');

-- 2. Seed Routes
INSERT INTO routes (route_id, route_short_name, route_long_name, start_terminal, end_terminal, total_distance_km, nominal_transit_time_min) VALUES
('ROUTE-1', '1A', 'Pilani Railway Station to BITS Main Campus', 'Pilani Station', 'BITS Clock Tower', 4.5, 15),
('ROUTE-2', '2B', 'Vidya Vihar Loop to Nutan Market', 'Vidya Vihar Terminal', 'Nutan Market Terminal', 8.2, 25),
('ROUTE-3', '3C', 'BITS Campus Express to CEERI Colony', 'BITS Student Activity Centre', 'CEERI Main Gate', 6.0, 20);

-- 3. Seed Stops (Accurate coordinates for Pilani area)
INSERT INTO stops (stop_id, stop_name, latitude, longitude, geofence_radius_meters, passenger_capacity) VALUES
('STOP-001', 'Pilani Railway Station', 28.3752, 75.6021, 60, 100),
('STOP-002', 'Bus Stand Circle', 28.3711, 75.5985, 50, 80),
('STOP-003', 'Birla Museum Stop', 28.3664, 75.5921, 50, 60),
('STOP-004', 'BITS Main Gate', 28.3638, 75.5872, 70, 120),
('STOP-005', 'BITS Clock Tower', 28.3591, 75.5879, 60, 150),
('STOP-006', 'Vidya Vihar Terminal', 28.3550, 75.5930, 80, 100),
('STOP-007', 'VFAST Guest House', 28.3580, 75.5910, 50, 40),
('STOP-008', 'Shiv Ganga Park', 28.3615, 75.5840, 50, 50),
('STOP-009', 'Nutan Market Terminal', 28.3690, 75.6050, 70, 90),
('STOP-010', 'CEERI Main Gate', 28.3730, 75.5810, 60, 70);

-- 4. Route 1 Sequence: Pilani Station -> Bus Stand -> Birla Museum -> BITS Main Gate -> BITS Clock Tower
INSERT INTO route_stops (route_id, stop_id, stop_sequence, expected_travel_sec_from_prev, distance_meters_from_prev, scheduled_dwell_time_sec) VALUES
('ROUTE-1', 'STOP-001', 1, 0, 0, 60),
('ROUTE-1', 'STOP-002', 2, 240, 1100, 30),
('ROUTE-1', 'STOP-003', 3, 210, 950, 30),
('ROUTE-1', 'STOP-004', 4, 180, 850, 45),
('ROUTE-1', 'STOP-005', 5, 150, 700, 60);

-- 5. Route 2 Sequence: Vidya Vihar -> VFAST -> Clock Tower -> Main Gate -> Nutan Market
INSERT INTO route_stops (route_id, stop_id, stop_sequence, expected_travel_sec_from_prev, distance_meters_from_prev, scheduled_dwell_time_sec) VALUES
('ROUTE-2', 'STOP-006', 1, 0, 0, 60),
('ROUTE-2', 'STOP-007', 2, 180, 800, 30),
('ROUTE-2', 'STOP-005', 3, 200, 900, 45),
('ROUTE-2', 'STOP-004', 4, 150, 700, 30),
('ROUTE-2', 'STOP-009', 5, 450, 2400, 60);

