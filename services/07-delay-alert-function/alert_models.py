# -*- coding: utf-8 -*-
"""Data models for Service 7: Delay Alert Service (Serverless)"""

import os
import sys
from typing import Optional, Dict, Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

from services.common.compat import BaseModel, Field

class TransitDelayAlert(BaseModel):
    alert_id: str = ""
    bus_id: str = ""
    route_id: str = ""
    stop_id: str = ""
    stop_name: str = ""
    delay_seconds: int = 0
    delay_minutes: float = 0.0
    severity: str = "MODERATE"     # MINOR, MODERATE, SEVERE
    trigger_type: str = "ETA_STREAM" # ETA_STREAM, INCIDENT_REPORT
    message: str = ""
    is_active: bool = True
    created_at: str = ""

class IncidentReport(BaseModel):
    incident_id: str = ""
    route_id: str = ""
    incident_type: str = "TRAFFIC_JAM" # TRAFFIC_JAM, ACCIDENT, ROADWORK, WEATHER
    severity: str = "SEVERE"
    affected_stops: list = []
    estimated_delay_minutes: float = 15.0
    description: str = ""

