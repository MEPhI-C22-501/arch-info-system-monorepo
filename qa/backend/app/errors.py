"""Формат ошибок и X-Request-Id по 130, разделы 2 и 5."""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-Id"

HTTP_CODES = {
    401: "UNAUTHENTICATED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
}


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.errors = errors or []


def not_found(what: str) -> ApiError:
    return ApiError(404, "NOT_FOUND", f"{what} не найден")


def conflict(code: str, message: str, errors: list[dict[str, str]] | None = None) -> ApiError:
    return ApiError(409, code, message, errors)


def validation_failed(errors: list[dict[str, str]], message: str = "Некорректные поля") -> ApiError:
    return ApiError(422, "VALIDATION_FAILED", message, errors)


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    body = {
        "code": code,
        "message": message,
        "correlationId": getattr(request.state, "request_id", None),
        "errors": errors or [],
    }
    return JSONResponse(status_code=status_code, content=body)


def install_error_handling(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        request.state.request_id = incoming if 0 < len(incoming) <= 128 else str(uuid.uuid4())
        try:
            response = await call_next(request)
        except Exception:
            log.exception("Необработанная ошибка, request_id=%s", request.state.request_id)
            response = error_response(request, 500, "INTERNAL", "Внутренняя ошибка")
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError):
        return error_response(request, exc.status_code, exc.code, exc.message, exc.errors)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = [
            {
                "field": ".".join(str(part) for part in e["loc"][1:]) or str(e["loc"][0]),
                "reason": e["msg"],
            }
            for e in exc.errors()
        ]
        return error_response(request, 422, "VALIDATION_FAILED", "Некорректные поля", errors)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = HTTP_CODES.get(exc.status_code, "HTTP_ERROR")
        return error_response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(OperationalError)
    async def database_unavailable(request: Request, exc: OperationalError):
        log.warning("БД недоступна: %s", exc)
        return error_response(request, 503, "DATABASE_UNAVAILABLE", "База данных недоступна")
