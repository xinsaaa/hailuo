# 日志系统文档

## 概述

本项目使用 **loguru** 实现了结构化日志记录和全局异常处理系统。

## 功能特性

- ✅ 结构化 JSON 日志格式
- ✅ 请求追踪 ID (Request ID)
- ✅ 全局异常处理
- ✅ 审计日志
- ✅ 自动日志轮转和压缩
- ✅ 敏感信息自动脱敏
- ✅ 异步日志写入

## 配置

在 `.env` 文件中配置日志系统：

```bash
# 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO

# 日志格式 (json, text)
LOG_FORMAT=json

# 日志目录
LOG_DIR=./logs

# 日志轮转大小 (MB)
LOG_ROTATION_SIZE=100

# 日志保留天数
LOG_RETENTION_DAYS=30

# 启用审计日志
ENABLE_AUDIT_LOG=true

# 环境 (development, production)
ENVIRONMENT=development
```

## 使用方法

### 基本日志记录

```python
from backend.logger import app_logger

# INFO 级别
app_logger.info("User created", user_id=123, username="john")

# DEBUG 级别
app_logger.debug("Processing request", data={"key": "value"})

# WARNING 级别
app_logger.warning("Rate limit approaching", requests=95, limit=100)

# ERROR 级别
app_logger.error("Database connection failed", exc_info=exception)

# CRITICAL 级别
app_logger.critical("System failure", exc_info=exception)
```

### 审计日志

```python
# 记录关键业务操作
app_logger.audit(
    "user.register",
    user_id=user.id,
    username=user.username,
    email=user.email,
    register_ip=client_ip
)

app_logger.audit(
    "payment.completed",
    user_id=user.id,
    amount=100.0,
    payment_method="alipay",
    transaction_id="TXN123456"
)
```

### 自定义异常

```python
from backend.exceptions import (
    ValidationException,
    AuthenticationException,
    NotFoundException,
    InsufficientBalanceException
)

# 验证错误
raise ValidationException(
    "Invalid input",
    field_errors={"email": "Invalid email format"}
)

# 认证错误
raise AuthenticationException("Invalid credentials")

# 资源不存在
raise NotFoundException("User", user_id=123)

# 余额不足
raise InsufficientBalanceException(required=10.0, available=5.0)
```

## 日志文件结构

```
logs/
├── app_2024-01-15.log          # 所有日志
├── app_2024-01-15.log.gz       # 压缩的旧日志
├── error_2024-01-15.log        # 仅错误日志
└── audit_2024-01-15.log        # 审计日志
```

## 日志格式

### JSON 格式（生产环境）

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

### 彩色格式（开发环境）

```
2024-01-15 10:30:45 | INFO     | backend.main:create_order:123 | Order created successfully
```

## 错误响应格式

所有 API 错误响应都遵循统一格式：

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

## 请求追踪

每个 HTTP 请求都会自动分配一个唯一的 `request_id`：

- 自动添加到所有日志条目
- 包含在响应头 `X-Request-ID`
- 包含在错误响应中

使用 request_id 可以追踪单个请求的完整生命周期。

## 敏感信息脱敏

以下字段会自动脱敏：

- `password`, `hashed_password`
- `token`, `access_token`, `refresh_token`
- `api_key`, `secret_key`
- `credit_card`, `cvv`, `ssn`

脱敏后显示为：`***MASKED***`

## 中间件顺序

中间件按以下顺序执行（重要）：

1. `CORSMiddleware` - CORS 处理
2. `LoggingMiddleware` - 请求日志
3. `RequestIDMiddleware` - 请求 ID 生成
4. `RateLimitMiddleware` - 频率限制

## 性能考虑

- 日志写入是异步的（`enqueue=True`），不会阻塞请求处理
- 日志文件自动轮转和压缩，避免磁盘空间问题
- 敏感信息脱敏在序列化时进行，性能影响最小

## 故障排查

### 查看最新日志

```bash
# 查看所有日志
tail -f logs/app_$(date +%Y-%m-%d).log

# 仅查看错误日志
tail -f logs/error_$(date +%Y-%m-%d).log

# 查看审计日志
tail -f logs/audit_$(date +%Y-%m-%d).log
```

### 搜索特定请求

```bash
# 使用 request_id 搜索
grep "550e8400-e29b-41d4-a716-446655440000" logs/app_*.log
```

### 分析错误

```bash
# 统计错误类型
grep '"level":"ERROR"' logs/app_*.log | jq -r '.message' | sort | uniq -c
```

## 下一步

- [ ] 添加日志查询 API
- [ ] 实现动态日志级别管理
- [ ] 添加日志统计和分析
- [ ] 集成日志聚合系统（ELK/Loki）
