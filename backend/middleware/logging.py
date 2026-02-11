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
    """记录请求和响应的中间件"""
    
    async def dispatch(self, request: Request, call_next):
        # 记录请求开始
        start_time = time.time()
        
        # 获取客户端信息
        client_ip = request.client.host if request.client else "unknown"
        
        app_logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
            query_params=str(request.query_params) if request.query_params else None,
        )
        
        try:
            # 处理请求
            response: Response = await call_next(request)
            
            # 计算请求处理时间
            duration = time.time() - start_time
            
            # 记录请求完成
            app_logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )
            
            return response
        except Exception as e:
            # 记录请求失败
            duration = time.time() - start_time
            app_logger.error(
                "Request failed",
                exc_info=e,
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration * 1000, 2),
            )
            raise
