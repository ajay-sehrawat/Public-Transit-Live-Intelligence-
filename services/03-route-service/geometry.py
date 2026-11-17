# -*- coding: utf-8 -*-
"""Geospatial calculations and geofencing utilities for Route Service"""

import math

EARTH_RADIUS_METERS = 6371000.0  # WGS-84 mean radius of Earth in meters

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the great-circle distance between two points in meters using Haversine formula."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return EARTH_RADIUS_METERS * c

def is_within_geofence(bus_lat: float, bus_lon: float,
                       stop_lat: float, stop_lon: float,
                       radius_meters: float = 60.0) -> bool:
    """Determines whether a bus GPS coordinate is inside a transit stop's geofence boundary."""
    distance = haversine_distance(bus_lat, bus_lon, stop_lat, stop_lon)
    return distance <= radius_meters

