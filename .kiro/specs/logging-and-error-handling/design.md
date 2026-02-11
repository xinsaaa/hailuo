# Design Document

## Overview

本设计文档描述了为 AI 视频生成平台添加全局异常处理器和结构化日志系统的技术方案。我们将使用 **loguru** 作为日志库（相比标准 logging 模块更简洁易用），并实现 FastAPI 的全局异常处理中间件。

### Key Design Goals

1. **零侵入性**: 最小化对现有代码的修改
2. **高性能**: 异步日志写入，不阻塞请求处理
3. **易于调试**: 结构化日志 + 请求追踪 ID
4. **生产就绪**: 自动日志轮转、压缩、清理
5. **安全合规**: 敏感信息自动脱敏，审计日志

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Request ID Middleware                         │  │
│  │  - Generate unique request_id                         │  │
│  │  - Store in contextvars                               │  │
│  │  - Add to response headers                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Logging Middleware                            │  │
│  │  - Log request start/end                              │  │
│  │  - Measure request duration                           │  │
│  │  - Log response status                                │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Global Exception Handler                      │  │
│  │  - Catch all unhandled exceptions                     │  │
│  │  - Log with full stack trace                          │  │
│  │  - Return standardized error response                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Route Handlers                                │  │
│  │  - Use logger for business logic                      │  │
│  │  - Raise custom exceptions                            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                      Logger System                           │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Loguru Logger (Singleton)                     │  │
│  │  - Structured JSON logging                            │  │
│  │  - Colored console output (dev mode)                  │  │
│  │  - Automatic context injection                        │  │
│  │  - Sensitive data masking                             │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Log Handlers                                  │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │  │  Console   │  │   File     │  │   Audit    │     │  │
│  │  │  Handler   │  │  Handler   │  │   File     │     │  │
│  │  └────────────┘  └────────────┘  └────────────┘     │  │
│  └──────────────────────────────────────────────────────┘  │
│                          ↓                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Log Rotation & Cleanup                        │  │
│  │  - Size-based rotation (100MB)                        │  │
│  │  - Gzip compression                                   │  │
│  │  - Time-based cleanup (30 days)                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                      Log Storage                             │
├─────────────────────────────────────────────────────────────┤
│  logs/                                                        │
│  ├── app_2024-01-15.log                                     │
│  ├── app_2024-01-15.log.gz                                  │
│  ├── audit_2024-01-15.log                                   │
│  └── error_2024-01-15.log                                   │
└─────────────────────────────────────────────────────────────┘
```

## Components and Interfaces

### 1. Logger Module (`backend/logger.py`)

核心日志模块，提供统一的日志接口。

```python
from loguru import logger
from typing import Optional
import sys
import os

class AppLogger:
    """应用日志器单例"""
    
    def __init__(self):
        self._configure_logger()
    
    def _configure_logger(self):
        """配置 loguru"""
        # 移除默认处理器
        logger.remove()
        
        # 添加控制台处理器（开发模式）
        # 添加文件处理器（生产模式）
        # 添加审计日志处理器
        pass
    
    def info(self, message: str, **kwargs):
        """记录 INFO 级别日志"""
        pass
    
    def error(self, message: str, exc_info: Optional[Exception] = None, **kwargs):
        """记录 ERROR 级别日志"""
        pass
    
    def audit(self, event: str, **kwargs):
        """记录审计日志"""
        pass

# 全局单例
app_logger = AppLogger()
```

### 2. Request Context Module (`backend/middleware/context.py`)

管理请求上下文，存储 request_id 等信息。

```python
from contextvars import ContextVar
from typing import Optional
import uuid

# 上下文变量
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar('user_id', default=None)

def get_request_id() -> Optional[str]:
    """获取当前请求 ID"""
    return request_id_var.get()

def set_request_id(request_id: str):
    """设置请求 ID"""
    request_id_var.set(request_id)

def generate_request_id() -> str:
    """生成唯一请求 ID"""
    return str(uuid.uuid4())
```

### 3. Request ID Middleware (`backend/middleware/request_id.py`)

为每个请求生成唯一 ID。

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from backend.middleware.context import generate_request_id, set_request_id

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = generate_request_id()
        set_request_id(request_id)
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        
        return response
```

### 4. Logging Middleware (`backend/middleware/logging.py`)

记录请求和响应信息。

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
import time
from backend.logger import app_logger

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # 记录请求开始
        app_logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host
        )
        
        response = await call_next(request)
        
        # 记录请求结束
        duration = time.time() - start_time
        app_logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration * 1000, 2)
        )
        
        return response
```

### 5. Exception Handler (`backend/middleware/exception_handler.py`)

全局异常处理器。

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from backend.logger import app_logger
from backend.middleware.context import get_request_id

class AppException(Exception):
    """应用自定义异常基类"""
    def __init__(self, message: str, status_code: int = 500, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    request_id = get_request_id()
    
    # 记录异常
    app_logger.error(
        f"Unhandled exception: {type(exc).__name__}",
        exc_info=exc,
        path=request.url.path,
        method=request.method
    )
    
    # 返回标准化错误响应
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc),
            "request_id": request_id
        }
    )
```

### 6. Custom Exceptions (`backend/exceptions.py`)

自定义异常类型。

```python
class ValidationException(AppException):
    """验证异常"""
    def __init__(self, message: str, field_errors: dict = None):
        super().__init__(message, status_code=400, details={"field_errors": field_errors})

class AuthenticationException(AppException):
    """认证异常"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401)

class AuthorizationException(AppException):
    """授权异常"""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=403)

class NotFoundException(AppException):
    """资源不存在异常"""
    def __init__(self, resource: str, resource_id: any):
        message = f"{resource} with id {resource_id} not found"
        super().__init__(message, status_code=404, details={"resource": resource, "id": resource_id})
```

## Data Models

### Log Entry Structure (JSON)

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "module": "backend.main",
  "function": "create_order",
  "line": 123,
  "message": "Order created successfully",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": 42,
  "extra": {
    "order_id": 1001,
    "model_name": "Hailuo 2.3",
    "cost": 0.99
  }
}
```

### Audit Log Entry Structure

```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "event": "user.register",
  "user_id": 42,
  "username": "john_doe",
  "email": "john@example.com",
  "ip_address": "192.168.1.100",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "invite_code": "ABC123",
    "device_fingerprint": "xyz789"
  }
}
```

### Error Response Structure

```json
{
  "error": "ValidationError",
  "message": "Invalid input data",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "details": {
    "field_errors": {
      "email": "Invalid email format",
      "password": "Password too short"
    }
  },
  "timestamp": "2024-01-15T10:30:45.123Z"
}
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Structured Log Format

*For any* log message written by the system, the output SHALL be valid JSON containing at minimum the fields: timestamp, level, module, and message.

**Validates: Requirements 1.2**

### Property 2: Request ID Propagation

*For any* HTTP request processed by the system, all log entries generated during that request SHALL contain the same request_id value.

**Validates: Requirements 3.3**

### Property 3: Request ID Uniqueness

*For any* two concurrent HTTP requests, their generated request_id values SHALL be different.

**Validates: Requirements 3.1**

### Property 4: Exception Logging

*For any* unhandled exception that occurs in an API endpoint, the system SHALL log an ERROR level entry containing the full stack trace.

**Validates: Requirements 2.2**

### Property 5: Standardized Error Response

*For any* exception caught by the global exception handler, the HTTP response SHALL contain the fields: error, message, request_id, and timestamp.

**Validates: Requirements 2.1**

### Property 6: Response Header Inclusion

*For any* HTTP response returned by the system, the response headers SHALL include X-Request-ID.

**Validates: Requirements 3.4**

### Property 7: Error Response Request ID

*For any* error response returned by the system, the response body SHALL include the request_id field matching the X-Request-ID header.

**Validates: Requirements 3.5**

### Property 8: Validation Error Format

*For any* validation error (HTTP 400), the response SHALL include a details.field_errors object mapping field names to error messages.

**Validates: Requirements 2.3**

### Property 9: Module Name Detection

*For any* log entry, the module field SHALL correctly identify the Python module that generated the log.

**Validates: Requirements 6.2**

### Property 10: Searchable Log Fields

*For any* log entry written in JSON format, it SHALL include all searchable fields: timestamp, level, module, request_id (if in request context), and user_id (if authenticated).

**Validates: Requirements 8.1**

### Property 11: Invalid Log Level Rejection

*For any* attempt to set an invalid log level via the admin API, the system SHALL return HTTP 400 with a validation error.

**Validates: Requirements 4.5**

## Error Handling

### Error Categories

1. **Validation Errors** (HTTP 400)
   - Invalid input data
   - Missing required fields
   - Format violations

2. **Authentication Errors** (HTTP 401)
   - Invalid credentials
   - Expired tokens
   - Missing authentication

3. **Authorization Errors** (HTTP 403)
   - Insufficient permissions
   - Resource access denied

4. **Not Found Errors** (HTTP 404)
   - Resource does not exist
   - Invalid resource ID

5. **Server Errors** (HTTP 500)
   - Unhandled exceptions
   - Database errors
   - External service failures

### Error Handling Strategy

1. **Catch at the highest level**: Global exception handler catches all unhandled exceptions
2. **Log with context**: Include request_id, user_id, and full stack trace
3. **Return standardized response**: Consistent error response format
4. **Mask sensitive data**: Never expose internal details in production
5. **Provide request_id**: Allow users to reference specific errors

## Testing Strategy

### Unit Tests

1. **Logger Configuration Tests**
   - Test logger initialization with different environment variables
   - Verify log level configuration
   - Test console and file handler setup

2. **Context Management Tests**
   - Test request_id generation and storage
   - Verify context isolation between requests
   - Test context cleanup after request

3. **Exception Handler Tests**
   - Test handling of different exception types
   - Verify error response format
   - Test request_id inclusion in error responses

### Integration Tests

1. **End-to-End Request Tests**
   - Make HTTP requests and verify logs are generated
   - Verify request_id propagation through entire request lifecycle
   - Test error scenarios and verify error responses

2. **Audit Log Tests**
   - Trigger audit events (register, login, etc.)
   - Verify audit log entries are created with correct format
   - Test audit log querying and filtering

### Property-Based Tests

We will use **pytest** with **hypothesis** for property-based testing.

1. **Property Test: Log Format Consistency**
   - Generate random log messages
   - Verify all outputs are valid JSON with required fields
   - **Feature: logging-and-error-handling, Property 1: Structured Log Format**

2. **Property Test: Request ID Uniqueness**
   - Generate multiple concurrent requests
   - Verify all request_ids are unique
   - **Feature: logging-and-error-handling, Property 3: Request ID Uniqueness**

3. **Property Test: Exception Logging**
   - Generate random exceptions in different endpoints
   - Verify all are logged with ERROR level and stack trace
   - **Feature: logging-and-error-handling, Property 4: Exception Logging**

4. **Property Test: Module Name Detection**
   - Log from different modules
   - Verify module names are correctly detected
   - **Feature: logging-and-error-handling, Property 9: Module Name Detection**

### Manual Tests

1. **Log Rotation Test**
   - Write logs until file size exceeds 100MB
   - Verify automatic rotation occurs
   - Verify old files are compressed

2. **Log Cleanup Test**
   - Create log files with old timestamps
   - Verify files older than 30 days are deleted

3. **Dynamic Log Level Test**
   - Change log level via admin API
   - Verify new level takes effect immediately
   - Verify logs are filtered according to new level

## Implementation Notes

### Why Loguru?

We chose **loguru** over the standard `logging` module because:

1. **Simpler API**: No need to configure handlers, formatters, etc.
2. **Better defaults**: Colored output, exception catching, rotation built-in
3. **Async support**: Native support for async/await
4. **Context management**: Easy to add custom context to logs
5. **Less boilerplate**: One-line configuration vs. dozens of lines

### Sensitive Data Masking

The logger will automatically mask sensitive fields:

- `password`, `hashed_password`
- `token`, `access_token`, `refresh_token`
- `api_key`, `secret_key`
- `credit_card`, `ssn`

Masking strategy: Replace with `***MASKED***`

### Performance Considerations

1. **Async logging**: Use loguru's async mode to avoid blocking
2. **Buffered writes**: Buffer log entries before writing to disk
3. **Lazy formatting**: Only format log messages if they will be written
4. **Sampling**: In high-traffic scenarios, sample logs (e.g., 1 in 100)

### Backward Compatibility

To minimize code changes, we provide a compatibility layer:

```python
# Old code (print statements)
print(f"[INFO] User {user_id} logged in")

# New code (minimal change)
from backend.logger import app_logger as logger
logger.info(f"User {user_id} logged in", user_id=user_id)
```

### Configuration

All configuration via environment variables:

```bash
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# Log format (json, text)
LOG_FORMAT=json

# Log directory
LOG_DIR=./logs

# Log rotation size (MB)
LOG_ROTATION_SIZE=100

# Log retention days
LOG_RETENTION_DAYS=30

# Enable audit logging
ENABLE_AUDIT_LOG=true
```

## Security Considerations

1. **File Permissions**: Log files created with 600 permissions (owner read/write only)
2. **Sensitive Data**: Automatic masking of passwords, tokens, etc.
3. **Audit Trail**: Immutable audit logs for compliance
4. **Access Control**: Admin API for log management requires authentication
5. **Log Injection**: Sanitize user input before logging to prevent log injection attacks

## Deployment Considerations

1. **Log Aggregation**: In production, consider shipping logs to centralized logging (e.g., ELK, Loki)
2. **Monitoring**: Set up alerts for ERROR and CRITICAL level logs
3. **Disk Space**: Monitor disk usage and adjust retention policy as needed
4. **Performance**: In high-traffic scenarios, consider async logging and sampling
5. **Compliance**: Ensure audit logs meet regulatory requirements (GDPR, HIPAA, etc.)
