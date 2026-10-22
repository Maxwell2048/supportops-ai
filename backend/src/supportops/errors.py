from uuid import uuid4
from datetime import datetime, timezone
import json
import logging
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException


request_logger = logging.getLogger('supportops.requests')
request_logger.setLevel(logging.INFO)
if not request_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    request_logger.addHandler(handler)


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, headers: dict | None = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}


def error_response(request: Request, status: int, code: str, message: str, *, headers=None, details=None):
    request.state.error_code = code
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "request_id": request_id, "details": details or {}}},
        headers={"X-Request-ID": request_id, "Cache-Control": "no-store", **(headers or {})},
    )


def install_error_handlers(app: FastAPI):
    @app.middleware("http")
    async def request_metadata(request: Request, call_next):
        started = perf_counter()
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception:
            # The dependency Session context has unwound/rolled back before this
            # response. Exception text/tracebacks may contain SQL parameters.
            response = error_response(request, 500, 'internal_error', 'The service is temporarily unavailable; please try again later')
        response.headers["X-Request-ID"] = request.state.request_id
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        route = request.scope.get('route')
        request_logger.info(json.dumps({
            'event': 'http_request', 'timestamp': datetime.now(timezone.utc).isoformat(),
            'request_id': request.state.request_id,
            'method': request.method if request.method in {'GET', 'POST', 'PATCH', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'} else 'OTHER',
            'route': getattr(route, 'path', 'unmatched'), 'status': response.status_code,
            'duration_ms': round((perf_counter() - started) * 1000, 2),
            'actor_id': getattr(request.state, 'actor_id', None),
            'actor_role': getattr(request.state, 'actor_role', None),
            'error_code': getattr(request.state, 'error_code', None),
        }, separators=(',', ':')))
        return response

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return error_response(request, exc.status_code, exc.code, exc.message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        # Never serialize exc.body or error input: login failures could expose passwords.
        return error_response(request, 422, "validation_error", "Invalid request fields")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return error_response(request, 503, "database_unavailable", "The service is temporarily unavailable; please try again later")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = "not_found" if exc.status_code == 404 else "http_error"
        return error_response(request, exc.status_code, code, "The request could not be completed", headers=exc.headers)
