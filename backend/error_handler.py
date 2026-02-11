"""
统一错误处理和日志模块：提供标准化的异常处理和安全日志记录
"""
import logging
import json
import traceback
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
import os


class SecurityLogger:
    """安全日志记录器，避免敏感信息泄露"""
    
    def __init__(self):
        self.logger = logging.getLogger("security_audit")
        self.setup_logger()
        
    def setup_logger(self):
        """设置日志配置"""
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_format = os.getenv("LOG_FORMAT", "json").lower()
        
        # 创建日志目录
        log_dir = os.getenv("LOG_DIR", "./logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # 设置日志级别
        level = getattr(logging, log_level, logging.INFO)
        self.logger.setLevel(level)
        
        # 清除现有处理器
        self.logger.handlers.clear()
        
        # 文件处理器
        file_handler = logging.FileHandler(
            os.path.join(log_dir, "security.log"),
            encoding='utf-8'
        )
        
        if log_format == "json":
            formatter = JsonFormatter()
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # 控制台处理器（仅开发环境）
        if os.getenv("ENVIRONMENT") != "production":
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def audit(self, event_type: str, **kwargs):
        """记录审计事件，过滤敏感信息"""
        # 过滤敏感字段
        safe_data = self._filter_sensitive_data(kwargs)
        
        audit_record = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": safe_data
        }
        
        self.logger.info(f"AUDIT: {event_type}", extra={"audit": audit_record})
    
    def security_warning(self, message: str, **kwargs):
        """记录安全警告"""
        safe_data = self._filter_sensitive_data(kwargs)
        self.logger.warning(f"SECURITY: {message}", extra=safe_data)
    
    def error(self, message: str, exc_info=None, **kwargs):
        """记录错误，包含异常信息"""
        safe_data = self._filter_sensitive_data(kwargs)
        self.logger.error(message, exc_info=exc_info, extra=safe_data)
    
    def info(self, message: str, **kwargs):
        """记录信息"""
        safe_data = self._filter_sensitive_data(kwargs)
        self.logger.info(message, extra=safe_data)
    
    def _filter_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """过滤敏感数据，避免密码等信息泄露到日志"""
        sensitive_fields = {
            'password', 'hashed_password', 'token', 'secret', 'key',
            'authorization', 'cookie', 'session', 'verification_code',
            'smtp_password', 'email_code'
        }
        
        filtered = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_fields):
                filtered[key] = "[FILTERED]"
            elif isinstance(value, dict):
                filtered[key] = self._filter_sensitive_data(value)
            else:
                filtered[key] = value
                
        return filtered


class JsonFormatter(logging.Formatter):
    """JSON格式的日志格式化器"""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if hasattr(record, 'audit'):
            log_data["audit"] = record.audit
        
        return json.dumps(log_data, ensure_ascii=False)


class APIErrorHandler:
    """API错误处理器，提供统一的错误响应格式"""
    
    def __init__(self, logger: SecurityLogger):
        self.logger = logger
    
    def handle_validation_error(self, request: Request, exc):
        """处理参数验证错误"""
        error_detail = {
            "error_type": "validation_error",
            "message": "请求参数验证失败",
            "details": exc.errors() if hasattr(exc, 'errors') else str(exc)
        }
        
        self.logger.security_warning(
            "Parameter validation failed",
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else "unknown",
            error_details=error_detail["details"]
        )
        
        return JSONResponse(
            status_code=422,
            content=error_detail
        )
    
    def handle_http_exception(self, request: Request, exc: HTTPException):
        """处理HTTP异常"""
        error_detail = {
            "error_type": "http_exception",
            "message": exc.detail,
            "status_code": exc.status_code
        }
        
        # 记录4xx和5xx错误
        if exc.status_code >= 400:
            log_method = self.logger.error if exc.status_code >= 500 else self.logger.security_warning
            log_method(
                f"HTTP {exc.status_code}: {exc.detail}",
                path=request.url.path,
                method=request.method,
                client_ip=request.client.host if request.client else "unknown",
                status_code=exc.status_code
            )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_detail
        )
    
    def handle_unexpected_error(self, request: Request, exc: Exception):
        """处理未预期的系统错误"""
        error_detail = {
            "error_type": "internal_error",
            "message": "系统内部错误，请稍后重试",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.error(
            f"Unexpected error: {type(exc).__name__}",
            exc_info=exc,
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else "unknown",
            exception_type=type(exc).__name__
        )
        
        return JSONResponse(
            status_code=500,
            content=error_detail
        )


class RateLimitError(HTTPException):
    """自定义限流异常"""
    def __init__(self, detail: str = "请求过于频繁，请稍后重试"):
        super().__init__(status_code=429, detail=detail)


class SecurityError(HTTPException):
    """自定义安全异常"""
    def __init__(self, detail: str = "安全验证失败"):
        super().__init__(status_code=403, detail=detail)


# 全局实例
security_logger = SecurityLogger()
error_handler = APIErrorHandler(security_logger)
