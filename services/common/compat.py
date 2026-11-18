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
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path
                handler = None

                # Exact route match
                if hasattr(app, "routes"):
                    handler = app.routes.get(("GET", path))
                    if not handler:
                        # Parameterized route match e.g. /api/v1/analytics/arrivals/{stop_id}
                        for (method, rpath), fn in app.routes.items():
                            if method == "GET" and "{" in rpath:
                                prefix = rpath.split("{")[0]
                                if path.startswith(prefix):
                                    param = path[len(prefix):]
                                    handler = lambda: fn(param)
                                    break

                if handler:
                    try:
                        res = handler()
                        if hasattr(res, "body"):
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
                        self.end_headers()
                        self.wfile.write(body)
                    except Exception as e:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(str(e).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"404 Not Found")

            def do_POST(self):
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path
                content_len = int(self.headers.get("Content-Length", 0))
                post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
                body_json = {}
                try:
                    body_json = json.loads(post_body.decode("utf-8")) if post_body else {}
                except Exception:
                    body_json = {}

                handler = None
                if hasattr(app, "routes"):
                    handler = app.routes.get(("POST", path))

                if handler:
                    try:
                        import inspect
                        sig = inspect.signature(handler)
                        if len(sig.parameters) > 0:
                            first_param = list(sig.parameters.values())[0]
                            param_type = first_param.annotation
                            if param_type != inspect.Parameter.empty and callable(param_type):
                                try:
                                    arg = param_type(**body_json)
                                except Exception:
                                    arg = body_json
                            else:
                                arg = body_json
                            res = handler(arg)
                        else:
                            res = handler()

                        body = json.dumps(res).encode("utf-8") if isinstance(res, (dict, list)) else (res.body if hasattr(res, "body") else str(res).encode("utf-8"))
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.end_headers()
                        self.wfile.write(body)
                    except Exception as e:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(str(e).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(b"404 Not Found")

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

        httpd = ReuseHTTPServer((host, port), FastApiCompatHandler)
        print(f"[*] Native HTTP Server running on http://{host}:{port}/ (Press Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()

