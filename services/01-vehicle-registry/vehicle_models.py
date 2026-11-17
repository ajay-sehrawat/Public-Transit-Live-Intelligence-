# -*- coding: utf-8 -*-
"""Data models for Vehicle Registry Microservice (Pydantic & In-Memory Schemas)"""

from datetime import datetime
from typing import Optional, List
import sys
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(REPO_ROOT)

from services.common.compat import BaseModel, Field

class VehicleBase(BaseModel):
    bus_id: str = Field(..., example="BUS-101", description="Unique vehicle identifier")
    license_plate: str = Field(..., example="RJ-18-PA-0101", description="Vehicle registration plate")
    model: str = Field(..., example="Tata Starbus EV", description="Bus model and make")
    capacity: int = Field(..., gt=0, example=45, description="Passenger seating and standing capacity")
    propulsion_type: str = Field("ELECTRIC", example="ELECTRIC", description="ELECTRIC, DIESEL, HYBRID, CNG")
    status: str = Field("ACTIVE", example="ACTIVE", description="ACTIVE, MAINTENANCE, RETIRED, OUT_OF_SERVICE")
    assigned_route_id: Optional[str] = Field(None, example="ROUTE-1", description="Currently scheduled transit route")

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    model: Optional[str] = None
    capacity: Optional[int] = None
    propulsion_type: Optional[str] = None
    status: Optional[str] = None
    assigned_route_id: Optional[str] = None

class VehicleResponse(VehicleBase):
    last_heartbeat: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class VehicleValidationResult(BaseModel):
    is_valid: bool
    bus_id: str
    status: str
    assigned_route_id: Optional[str] = None
    message: str

