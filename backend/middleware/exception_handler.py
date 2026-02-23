"""
全局异常处理器
捕获并处理所有未处理的异常
"""
from datetime import datetime
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError

from backend.logger import app_logger
from backend.middleware.context import get_request_id
from backend.exceptions import AppException


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """处理自定义应用异常"""
    request_id = get_request_id()
    
    # 记录异常
    app_logger.error(
        f"Application exception: {exc.message}",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
    )
    
    # 返回标准化错误响应
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "detail": exc.message,
            "request_id": request_id,
            "details": exc.details,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """处理 FastAPI 验证异常"""
    request_id = get_request_id()
    
    # 提取字段级错误，生成友好提示
    field_errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        field_errors[field] = error["msg"]

    # 生成用户友好的错误信息
    friendly_messages = []
    for field, msg in field_errors.items():
        friendly_messages.append(f"{field}: {msg}")
    friendly_msg = "; ".join(friendly_messages) if friendly_messages else "输入数据格式不正确"

    # 记录验证错误
    app_logger.warning(
        "Validation error",
        path=request.url.path,
        method=request.method,
        field_errors=field_errors,
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "ValidationError",
            "message": friendly_msg,
            "detail": friendly_msg,
            "request_id": request_id,
            "details": {"field_errors": field_errors},
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """处理 HTTP 异常"""
    request_id = get_request_id()
    
    # 记录 HTTP 异常
    app_logger.warning(
        f"HTTP exception: {exc.detail}",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail,
            "detail": exc.detail,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理器 - 捕获所有未处理的异常"""
    request_id = get_request_id()
    
    # 记录异常（包含完整堆栈跟踪）
    app_logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
    )
    
    # 返回标准化错误响应（生产环境不暴露详细错误信息）
    import os
    environment = os.getenv("ENVIRONMENT", "development").lower()
    
    error_detail = str(exc) if environment == "development" else "Internal server error"
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": error_detail,
            "detail": error_detail,
            "request_id": request_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    )
