"""
Request ID 中间件
为每个请求生成唯一的追踪 ID
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from backend.middleware.context import generate_request_id, set_request_id, clear_context


class RequestIDMiddleware(BaseHTTPMiddleware):
    """为每个请求生成唯一 ID 并添加到响应头"""
    
    async def dispatch(self, request: Request, call_next):
        # 生成请求 ID
        request_id = generate_request_id()
        set_request_id(request_id)
        
        try:
            # 处理请求
            response: Response = await call_next(request)
            
            # 添加请求 ID 到响应头
            response.headers["X-Request-ID"] = request_id
            
            return response
        finally:
            # 清理上下文
            clear_context()
