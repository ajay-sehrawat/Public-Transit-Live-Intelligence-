from .transit_pb2 import (
    VehicleValidationRequest,
    VehicleValidationResponse,
    VehicleDetailsRequest,
    VehicleDetailsResponse,
    ListVehiclesRequest,
    ListVehiclesResponse,
    StopInfo,
    RouteDetailsRequest,
    RouteDetailsResponse,
    NearestStopRequest,
    NearestStopResponse,
    ListRoutesRequest,
    ListRoutesResponse,
    RouteSummary,
)

from .transit_pb2_grpc import (
    VehicleRegistryServiceServicer,
    VehicleRegistryServiceStub,
    RouteGeometryServiceServicer,
    RouteGeometryServiceStub,
    add_VehicleRegistryServiceServicer_to_server,
    add_RouteGeometryServiceServicer_to_server,
)

