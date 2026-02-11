"""
自定义异常类
定义应用中使用的各种异常类型
"""
from typing import Dict, Optional, Any


class AppException(Exception):
    """应用自定义异常基类"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationException(AppException):
    """验证异常 (HTTP 400)"""
    
    def __init__(self, message: str, field_errors: Optional[Dict[str, str]] = None):
        super().__init__(
            message,
            status_code=400,
            details={"field_errors": field_errors or {}}
        )


class AuthenticationException(AppException):
    """认证异常 (HTTP 401)"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)


class AuthorizationException(AppException):
    """授权异常 (HTTP 403)"""
    
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=403)


class NotFoundException(AppException):
    """资源不存在异常 (HTTP 404)"""
    
    def __init__(self, resource: str, resource_id: Any):
        message = f"{resource} with id {resource_id} not found"
        super().__init__(
            message,
            status_code=404,
            details={"resource": resource, "id": str(resource_id)}
        )


class ConflictException(AppException):
    """资源冲突异常 (HTTP 409)"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=409, details=details)


class RateLimitException(AppException):
    """请求频率限制异常 (HTTP 429)"""
    
    def __init__(self, message: str = "Too many requests", retry_after: Optional[int] = None):
        details = {"retry_after": retry_after} if retry_after else {}
        super().__init__(message, status_code=429, details=details)


class InsufficientBalanceException(AppException):
    """余额不足异常 (HTTP 402)"""
    
    def __init__(self, required: float, available: float):
        message = f"Insufficient balance. Required: {required}, Available: {available}"
        super().__init__(
            message,
            status_code=402,
            details={"required": required, "available": available}
        )
