"""
日志中间件
记录所有 HTTP 请求和响应信息
"""
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from backend.logger import app_logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """记录请求和响应的中间件 - 只记录错误"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        try:
            response: Response = await call_next(request)
            # 只记录5xx服务器错误
            if response.status_code >= 500:
                duration = time.time() - start_time
                app_logger.error(
                    f"请求失败 {request.method} {request.url.path} → {response.status_code}",
                    duration_ms=round(duration * 1000, 2),
                )
            return response
        except Exception as e:
            duration = time.time() - start_time
            app_logger.error(
                f"请求异常 {request.method} {request.url.path}: {e}",
                exc_info=e,
                duration_ms=round(duration * 1000, 2),
            )
            raise
