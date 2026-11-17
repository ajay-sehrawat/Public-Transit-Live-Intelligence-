# -*- coding: utf-8 -*-
"""Client and server classes corresponding to protobuf-defined services."""

import sys
from typing import Any

try:
    import grpc
    HAS_GRPC = True
except ImportError:
    HAS_GRPC = False


class VehicleRegistryServiceServicer(object):
    """Base Servicer interface for Service 1: Vehicle Registry Service."""

    def ValidateVehicle(self, request, context=None):
        raise NotImplementedError('Method not implemented!')

    def GetVehicleDetails(self, request, context=None):
        raise NotImplementedError('Method not implemented!')

    def ListActiveVehicles(self, request, context=None):
        raise NotImplementedError('Method not implemented!')


class VehicleRegistryServiceStub(object):
    """Client stub for calling Service 1: Vehicle Registry."""

    def __init__(self, channel=None, direct_servicer=None):
        self.channel = channel
        self.direct_servicer = direct_servicer

    def ValidateVehicle(self, request, timeout=None):
        if self.direct_servicer:
            return self.direct_servicer.ValidateVehicle(request)
        if HAS_GRPC and self.channel:
            return self.channel.unary_unary(
                '/transit.VehicleRegistryService/ValidateVehicle',
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, timeout=timeout)
        raise RuntimeError("No active gRPC channel or direct servicer available")

    def GetVehicleDetails(self, request, timeout=None):
        if self.direct_servicer:
            return self.direct_servicer.GetVehicleDetails(request)
        if HAS_GRPC and self.channel:
            return self.channel.unary_unary(
                '/transit.VehicleRegistryService/GetVehicleDetails',
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, timeout=timeout)
        raise RuntimeError("No active gRPC channel or direct servicer available")

    def ListActiveVehicles(self, request, timeout=None):
        if self.direct_servicer:
            return self.direct_servicer.ListActiveVehicles(request)
        if HAS_GRPC and self.channel:
            return self.channel.unary_unary(
                '/transit.VehicleRegistryService/ListActiveVehicles',
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, timeout=timeout)
        raise RuntimeError("No active gRPC channel or direct servicer available")


class RouteGeometryServiceServicer(object):
    """Base Servicer interface for Service 3: Route Geometry Service."""

    def GetRouteDetails(self, request, context=None):
        raise NotImplementedError('Method not implemented!')

    def FindNearestStop(self, request, context=None):
        raise NotImplementedError('Method not implemented!')

    def ListRoutes(self, request, context=None):
        raise NotImplementedError('Method not implemented!')


class RouteGeometryServiceStub(object):
    """Client stub for calling Service 3: Route Geometry Service."""

    def __init__(self, channel=None, direct_servicer=None):
        self.channel = channel
        self.direct_servicer = direct_servicer

    def GetRouteDetails(self, request, timeout=None):
        if self.direct_servicer:
            return self.direct_servicer.GetRouteDetails(request)
        if HAS_GRPC and self.channel:
            return self.channel.unary_unary(
                '/transit.RouteGeometryService/GetRouteDetails',
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, timeout=timeout)
        raise RuntimeError("No active gRPC channel or direct servicer available")

    def FindNearestStop(self, request, timeout=None):
        if self.direct_servicer:
            return self.direct_servicer.FindNearestStop(request)
        if HAS_GRPC and self.channel:
            return self.channel.unary_unary(
                '/transit.RouteGeometryService/FindNearestStop',
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, timeout=timeout)
        raise RuntimeError("No active gRPC channel or direct servicer available")

    def ListRoutes(self, request, timeout=None):
        if self.direct_servicer:
            return self.direct_servicer.ListRoutes(request)
        if HAS_GRPC and self.channel:
            return self.channel.unary_unary(
                '/transit.RouteGeometryService/ListRoutes',
                request_serializer=lambda x: x,
                response_deserializer=lambda x: x,
            )(request, timeout=timeout)
        raise RuntimeError("No active gRPC channel or direct servicer available")


def add_VehicleRegistryServiceServicer_to_server(servicer, server):
    if HAS_GRPC:
        # Standard grpc.server registration
        rpc_method_handlers = {
            'ValidateVehicle': grpc.unary_unary_rpc_method_handler(
                servicer.ValidateVehicle,
                request_deserializer=lambda x: x,
                response_serializer=lambda x: x,
            ),
            'GetVehicleDetails': grpc.unary_unary_rpc_method_handler(
                servicer.GetVehicleDetails,
                request_deserializer=lambda x: x,
                response_serializer=lambda x: x,
            ),
            'ListActiveVehicles': grpc.unary_unary_rpc_method_handler(
                servicer.ListActiveVehicles,
                request_deserializer=lambda x: x,
                response_serializer=lambda x: x,
            ),
        }
        generic_handler = grpc.method_handlers_generic_handler(
            'transit.VehicleRegistryService', rpc_method_handlers
        )
        server.add_generic_rpc_handlers((generic_handler,))


def add_RouteGeometryServiceServicer_to_server(servicer, server):
    if HAS_GRPC:
        rpc_method_handlers = {
            'GetRouteDetails': grpc.unary_unary_rpc_method_handler(
                servicer.GetRouteDetails,
                request_deserializer=lambda x: x,
                response_serializer=lambda x: x,
            ),
            'FindNearestStop': grpc.unary_unary_rpc_method_handler(
                servicer.FindNearestStop,
                request_deserializer=lambda x: x,
                response_serializer=lambda x: x,
            ),
            'ListRoutes': grpc.unary_unary_rpc_method_handler(
                servicer.ListRoutes,
                request_deserializer=lambda x: x,
                response_serializer=lambda x: x,
            ),
        }
        generic_handler = grpc.method_handlers_generic_handler(
            'transit.RouteGeometryService', rpc_method_handlers
        )
        server.add_generic_rpc_handlers((generic_handler,))

