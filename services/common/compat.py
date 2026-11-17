# -*- coding: utf-8 -*-
"""Compatibility shim for FastAPI and Pydantic.
Uses real FastAPI and Pydantic when installed; provides an in-memory zero-dependency fallback
so that services and unit tests can run anywhere on vanilla Python.
"""

import sys

try:
    from pydantic import BaseModel as RealBaseModel, Field as RealField, validator as real_validator
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

if HAS_PYDANTIC:
    BaseModel = RealBaseModel
    Field = RealField
    validator = real_validator
else:
    class BaseModel:
        def __init__(self, **kwargs):
            # Assign class defaults first
            for k in dir(self.__class__):
                if not k.startswith("_") and not callable(getattr(self.__class__, k)):
                    setattr(self, k, getattr(self.__class__, k))
            # Assign passed kwargs
            for k, v in kwargs.items():
                setattr(self, k, v)

        def dict(self, exclude_unset: bool = False):
            result = {}
            for k in dir(self):
                if not k.startswith("_") and not callable(getattr(self, k)) and k != "Config":
                    val = getattr(self, k)
                    if hasattr(val, "dict"):
                        result[k] = val.dict()
                    elif isinstance(val, list):
                        result[k] = [item.dict() if hasattr(item, "dict") else item for item in val]
                    else:
                        result[k] = val
            return result

        model_dump = dict

        def __repr__(self):
            return f"{self.__class__.__name__}({self.dict()})"

    def Field(default=None, **kwargs):
        return default

    def validator(*fields, **kwargs):
        def decorator(fn):
            return fn
        return decorator


try:
    from fastapi import FastAPI as RealFastAPI, HTTPException as RealHTTPException, status as real_status, Query as RealQuery, Response as RealResponse, Request as RealRequest
    from fastapi.responses import JSONResponse as RealJSONResponse
    from fastapi.middleware.cors import CORSMiddleware as RealCORSMiddleware
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

if HAS_FASTAPI:
    FastAPI = RealFastAPI
    HTTPException = RealHTTPException
    status = real_status
    Query = RealQuery
    CORSMiddleware = RealCORSMiddleware
    Response = RealResponse
    JSONResponse = RealJSONResponse
    Request = RealRequest
else:
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: any = None):
            self.status_code = status_code
            self.detail = detail
            super().__init__(f"HTTP {status_code}: {detail}")

    class status:
        HTTP_200_OK = 200
        HTTP_201_CREATED = 201
        HTTP_202_ACCEPTED = 202
        HTTP_204_NO_CONTENT = 204
        HTTP_400_BAD_REQUEST = 400
        HTTP_404_NOT_FOUND = 404
        HTTP_409_CONFLICT = 409
        HTTP_500_INTERNAL_SERVER_ERROR = 500

    def Query(default=None, **kwargs):
        return default

    class CORSMiddleware:
        pass

    class Response:
        def __init__(self, content: any = b"", status_code: int = 200, media_type: str = "text/plain"):
            self.body = content.encode("utf-8") if isinstance(content, str) else content
            self.status_code = status_code
            self.media_type = media_type

    class JSONResponse(Response):
        def __init__(self, content: any = None, status_code: int = 200):
            import json
            super().__init__(content=json.dumps(content), status_code=status_code, media_type="application/json")

    class Request:
        pass

    class FastAPI:
        def __init__(self, title: str = "", description: str = "", version: str = ""):
            self.title = title
            self.description = description
            self.version = version
            self.routes = {}
            self.startup_handlers = []
            self.shutdown_handlers = []

        def add_middleware(self, middleware_class, **options):
            pass

        def middleware(self, middleware_type):
            def decorator(fn):
                return fn
            return decorator

        def on_event(self, event_type: str):
            def decorator(fn):
                if event_type == "startup":
                    self.startup_handlers.append(fn)
                elif event_type == "shutdown":
                    self.shutdown_handlers.append(fn)
                return fn
            return decorator

        def get(self, path: str, **kwargs):
            def decorator(fn):
                self.routes[("GET", path)] = fn
                return fn
            return decorator

        def post(self, path: str, **kwargs):
            def decorator(fn):
                self.routes[("POST", path)] = fn
                return fn
            return decorator

        def patch(self, path: str, **kwargs):
            def decorator(fn):
                self.routes[("PATCH", path)] = fn
                return fn
            return decorator

        def delete(self, path: str, **kwargs):
            def decorator(fn):
                self.routes[("DELETE", path)] = fn
                return fn
            return decorator

