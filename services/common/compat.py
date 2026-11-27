# -*- coding: utf-8 -*-
"""Compatibility shim for FastAPI and Pydantic.
Uses real FastAPI and Pydantic when installed; provides an in-memory zero-dependency fallback
so that services and unit tests can run anywhere on vanilla Python.
"""

import sys
import socket
import time

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
        def __init__(self, content: any = b"", status_code: int = 200, media_type: str = "text/plain", headers: any = None):
            self.body = content.encode("utf-8") if isinstance(content, str) else content
            self.status_code = status_code
            self.media_type = media_type
            self.headers = headers or {}

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


def run_server(app, host: str = "0.0.0.0", port: int = 8080):
    """Runs application with uvicorn if installed, or with Python standard library HTTPServer."""
    try:
        import uvicorn
        uvicorn.run(app, host=host, port=port)
    except ImportError:
        import json
        import urllib.parse
        from http.server import HTTPServer, BaseHTTPRequestHandler

        class FastApiCompatHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self._dispatch("GET")

            def do_POST(self):
                self._dispatch("POST")

            def do_PATCH(self):
                self._dispatch("PATCH")

            def do_PUT(self):
                self._dispatch("PUT")

            def do_DELETE(self):
                self._dispatch("DELETE")

            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _dispatch(self, method: str):
                import inspect
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path
                query_params = urllib.parse.parse_qs(parsed.query)

                # Parse body if present
                content_len = int(self.headers.get("Content-Length", 0))
                post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
                body_json = {}
                if post_body:
                    try:
                        body_json = json.loads(post_body.decode("utf-8"))
                    except Exception:
                        body_json = {}

                handler = None
                path_params = {}

                # 1. Exact route match
                if hasattr(app, "routes"):
                    handler = app.routes.get((method, path))

                # 2. Parameterized route match (e.g., /api/v1/vehicles/{bus_id})
                if not handler and hasattr(app, "routes"):
                    req_parts = [p for p in path.split("/") if p]
                    for (m, rpath), fn in app.routes.items():
                        if m == method and "{" in rpath:
                            pattern_parts = [p for p in rpath.split("/") if p]
                            if len(pattern_parts) == len(req_parts):
                                matched = True
                                current_params = {}
                                for pp, rp in zip(pattern_parts, req_parts):
                                    if pp.startswith("{") and pp.endswith("}"):
                                        param_name = pp[1:-1]
                                        current_params[param_name] = rp
                                    elif pp != rp:
                                        matched = False
                                        break
                                if matched:
                                    handler = fn
                                    path_params = current_params
                                    break

                if not handler:
                    self.send_response(404)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"detail": f"Path '{path}' with method '{method}' not found."}).encode("utf-8"))
                    return

                # Invoke handler
                try:
                    sig = inspect.signature(handler)
                    kwargs = {}

                    for p_name, param in sig.parameters.items():
                        if p_name in path_params:
                            kwargs[p_name] = path_params[p_name]
                        elif p_name in query_params:
                            val = query_params[p_name][0]
                            if param.annotation in (float, "float"):
                                try:
                                    val = float(val)
                                except Exception:
                                    pass
                            elif param.annotation in (int, "int"):
                                try:
                                    val = int(val)
                                except Exception:
                                    pass
                            kwargs[p_name] = val
                        elif param.annotation != inspect.Parameter.empty and callable(param.annotation):
                            try:
                                kwargs[p_name] = param.annotation(**body_json)
                            except Exception:
                                kwargs[p_name] = body_json
                        elif p_name in ("payload", "request", "data"):
                            kwargs[p_name] = body_json
                        elif p_name in body_json:
                            kwargs[p_name] = body_json[p_name]

                    if kwargs:
                        res = handler(**kwargs)
                    elif len(sig.parameters) == 1:
                        first_p = list(sig.parameters.values())[0]
                        if path_params:
                            res = handler(list(path_params.values())[0])
                        elif first_p.annotation != inspect.Parameter.empty and callable(first_p.annotation):
                            try:
                                res = handler(first_p.annotation(**body_json))
                            except Exception:
                                res = handler(body_json)
                        else:
                            res = handler(body_json)
                    else:
                        res = handler()

                    # Format response
                    status_code = 200
                    media_type = "application/json"
                    if res is None:
                        body = b""
                        status_code = 204
                    elif hasattr(res, "body"):
                        body = res.body
                        media_type = getattr(res, "media_type", "text/plain")
                        status_code = getattr(res, "status_code", 200)
                    elif isinstance(res, (dict, list)):
                        body = json.dumps(res).encode("utf-8")
                        media_type = "application/json"
                        status_code = 200
                    elif isinstance(res, str):
                        body = res.encode("utf-8")
                        media_type = "text/plain"
                        status_code = 200
                    else:
                        body = str(res).encode("utf-8")
                        media_type = "text/plain"
                        status_code = 200

                    self.send_response(status_code)
                    self.send_header("Content-Type", media_type)
                    self.send_header("Content-Length", str(len(body)))
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Expires", "0")
                    self.end_headers()
                    if body:
                        self.wfile.write(body)

                except HTTPException as he:
                    self.send_response(he.status_code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"detail": he.detail}).encode("utf-8"))
                except Exception as ex:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    self.wfile.write(json.dumps({"detail": str(ex)}).encode("utf-8"))

            def log_message(self, format, *args):
                pass

        # Trigger startup handlers if registered
        if hasattr(app, "startup_handlers"):
            for h in app.startup_handlers:
                try:
                    h()
                except Exception:
                    pass

        class ReuseHTTPServer(HTTPServer):
            allow_reuse_address = True

            def server_bind(self):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                if hasattr(socket, "SO_REUSEPORT"):
                    try:
                        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                    except Exception:
                        pass
                super().server_bind()

        httpd = None
        for attempt in range(8):
            try:
                httpd = ReuseHTTPServer((host, port), FastApiCompatHandler)
                break
            except OSError as e:
                if attempt == 7:
                    raise
                time.sleep(0.5)

        print(f"[*] Native HTTP Server running on http://{host}:{port}/ (Press Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()

